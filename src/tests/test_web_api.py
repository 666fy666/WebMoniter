"""任务结果、分页和日志读取的关键 Web 回归测试。"""

import json
from types import SimpleNamespace

import pytest

from src.jobs.log_manager import _current_job_id
from src.web.routers import data, logs, tasks


@pytest.fixture
def web_request(monkeypatch):
    for module in (data, logs, tasks):
        monkeypatch.setattr(module, "check_login", lambda session_id: session_id == "ok")
    monkeypatch.setattr(tasks, "discover_and_import", lambda: None)
    monkeypatch.setattr(tasks, "MONITOR_JOBS", [])
    monkeypatch.setattr(tasks, "TASK_JOBS", [])
    return SimpleNamespace(session={"session_id": "ok"})


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", [True, False, None, RuntimeError("test failure")])
async def test_manual_task_reports_outcome_and_releases_log_context(
    web_request, monkeypatch, outcome
):
    async def run():
        assert _current_job_id.get() == "test_task"
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(
        tasks, "TASK_JOBS", [SimpleNamespace(job_id="test_task", original_run_func=run)]
    )
    response = await tasks.run_task_api(web_request, "test_task")
    body = json.loads(response.body)
    assert response.status_code == (500 if isinstance(outcome, Exception) else 200)
    assert body["success"] is (outcome is not False and not isinstance(outcome, Exception))
    assert _current_job_id.get() is None


@pytest.mark.asyncio
async def test_manual_task_requires_login_and_existing_task(web_request):
    assert (await tasks.run_task_api(web_request, "missing")).status_code == 404
    web_request.session.clear()
    assert (await tasks.run_task_api(web_request, "missing")).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(("page", "page_size"), [(0, 100), (-1, 100), (1, 0), (1, -1)])
async def test_data_rejects_nonpositive_pagination(web_request, page, page_size):
    response = await data.get_table_data(web_request, "huya", page=page, page_size=page_size)
    assert response.status_code == 400
    assert "error" in json.loads(response.body)


@pytest.mark.asyncio
async def test_weibo_paginates_before_conversion_and_keeps_stable_order(web_request, monkeypatch):
    rows = [
        (uid, "", "", "", "", "", f"正文\n\n{timestamp}")
        for uid, timestamp in [
            ("old", "2026-01-01 10:00:00"),
            ("tie-a", "2026-02-01 10:00:00"),
            ("invalid", "unknown"),
            ("new", "2026-03-01 10:00:00"),
            ("tie-b", "2026-02-01 10:00:00"),
        ]
    ]

    class Database:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute_query(self, sql, params):
            if sql.startswith("SELECT UID, 文本"):
                return [(row[0], row[6]) for row in rows]
            return [row for row in reversed(rows) if row[0] in params.values()]

    converted = []

    def convert(platform, row):
        converted.append(row[0])
        return {"UID": row[0]}

    monkeypatch.setattr(data, "AsyncDatabase", Database)
    monkeypatch.setattr(data, "_row_to_item", convert)
    response = await data.get_table_data(web_request, "weibo", page=2, page_size=2)
    body = json.loads(response.body)
    assert body == {
        "data": [{"UID": "tie-b"}, {"UID": "old"}],
        "total": 5,
        "page": 2,
        "page_size": 2,
        "total_pages": 3,
    }
    assert converted == ["tie-b", "old"]


@pytest.mark.asyncio
async def test_weibo_large_page_filters_and_refreshes_updated_data(
    web_request, monkeypatch, tmp_path
):
    from src.storage import database

    await database.close_shared_connection()
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "data.db")
    try:
        async with database.AsyncDatabase() as db:
            async with db.get_connection() as conn:
                await conn.executemany(
                    "INSERT INTO weibo (UID, 用户名, 文本, 图片) VALUES (?, ?, ?, ?)",
                    [
                        (str(i), "test", "正文\n\n2026-01-01 10:00:00", '["/image.jpg"]')
                        for i in range(600)
                    ],
                )
                await conn.commit()
            response = await data.get_table_data(web_request, "weibo", page_size=600)
            body = json.loads(response.body)
            assert body["total"] == 600
            assert [row["UID"] for row in body["data"]] == [str(i) for i in range(600)]
            assert body["data"][0]["images"] == ["/image.jpg"]

            assert await db.execute_update(
                "UPDATE weibo SET 文本=:text WHERE UID=:pk",
                {"text": "更新正文\n\n2026-12-01 10:00:00", "pk": "599"},
            )
            response = await data.get_table_data(web_request, "weibo", page_size=1)
            assert json.loads(response.body)["data"][0]["UID"] == "599"
            import aiosqlite

            async with aiosqlite.connect(str(database.DB_PATH)) as external:
                await external.execute(
                    "UPDATE weibo SET 文本=? WHERE UID=?", ("外部更新\n\n2027-01-01 10:00:00", "1")
                )
                await external.commit()
            external_response = await data.get_table_data(web_request, "weibo", page_size=1)
            assert json.loads(external_response.body)["data"][0]["UID"] == "1"
            filtered = json.loads((await data.get_table_data(web_request, "weibo", uid="5")).body)
            assert filtered["total"] == 1
            assert [row["UID"] for row in filtered["data"]] == ["5"]
            empty = json.loads(
                (await data.get_table_data(web_request, "weibo", page=601, page_size=1)).body
            )
            assert empty["data"] == []
            assert empty["total"] == 600
    finally:
        await database.close_shared_connection()


@pytest.mark.asyncio
async def test_huya_images_batches_many_ids_without_changing_response(web_request, monkeypatch):
    batches = []

    class Database:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute_query(self, sql, params):
            batches.append(len(params))
            return [(room, " cover ", " avatar ") for room in params.values()]

    monkeypatch.setattr(data, "AsyncDatabase", Database)
    rooms = ",".join(str(i) for i in range(1200)) + ",0,1"
    body = json.loads((await data.get_huya_images(web_request, rooms)).body)
    assert len(body["data"]) == 1200
    assert body["data"]["1199"] == {"room_pic": "cover", "avatar_url": "avatar"}
    assert batches == [500, 500, 200]


@pytest.mark.asyncio
@pytest.mark.parametrize("lines", [0, -1])
async def test_logs_rejects_nonpositive_line_count(web_request, lines):
    assert (await logs.get_logs(web_request, lines=lines)).status_code == 400


@pytest.mark.parametrize("ending", ["\n", "\r\n", ""])
def test_large_utf8_log_tail_returns_requested_lines(tmp_path, ending):
    line_separator = ending or "\n"
    expected = [f"{index}: {'日志内容' * 80}" for index in range(3500)]
    path = tmp_path / "large.log"
    path.write_bytes((line_separator.join(expected) + ending).encode("utf-8"))
    recent, total = logs._read_log_file_sync(path, 500)
    expected_tail = [line + "\n" for line in expected[-500:]]
    if not ending:
        expected_tail[-1] = expected[-1]
    assert recent == expected_tail
    assert total >= 500


@pytest.mark.parametrize(
    "content",
    ["", "一行", "一行\n两行\n", "长" * 400000],
    ids=["empty", "no-newline", "two-lines", "long-line"],
)
def test_log_tail_handles_short_files_and_single_long_line(tmp_path, content):
    path = tmp_path / "test.log"
    path.write_text(content, encoding="utf-8")
    recent, total = logs._read_log_file_sync(path, 3)
    assert recent == content.splitlines(keepends=True)[-3:]
    assert total == len(content.splitlines())
