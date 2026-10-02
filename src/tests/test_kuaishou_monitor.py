"""快手响应夹具为合成数据；不代表真实站点验证通过。"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
import pytest_asyncio

from src.monitors import kuaishou_monitor as module
from src.monitors.kuaishou_monitor import KuaishouMonitor, parse_live_page
from src.monitors.kuaishou_targets import (
    checked_url,
    principal_from_target,
    prune_targets,
    target_key,
)
from src.settings.config import AppConfig, load_config_from_yml
from src.storage import database as db_module
from src.storage.mysql_backend import TABLE_SPECS
from src.web.data_support import _row_to_item
from src.web.routers import data as data_routes


def page(living=False, **overrides):
    item = {
        "author": {"id": "alice", "name": "主播"},
        "isLiving": living,
        "status": {"forbiddenState": 1},
    }
    item.update(overrides)
    return (
        "<script>window.__INITIAL_STATE__="
        + json.dumps({"liveroom": {"playList": [item]}})
        + ";</script>"
    )


@pytest.mark.parametrize("living", [True, False])
def test_explicit_live_state(living):
    assert parse_live_page(page(living), "alice")["is_live"] == str(int(living))


@pytest.mark.parametrize("code", [606, 69101, 67601, 67606, 60200, 109, 2, 15, None, True, "1"])
def test_restricted_or_missing_result_code_cannot_report_offline(code):
    with pytest.raises(module.KuaishouStateError):
        parse_live_page(page(False, status={"forbiddenState": code}), "alice")


def test_explicit_not_living_code_must_agree_with_state():
    assert parse_live_page(page(False, status={"forbiddenState": 671}), "alice")["is_live"] == "0"
    with pytest.raises(module.KuaishouStateError, match="冲突"):
        parse_live_page(page(True, status={"forbiddenState": 671}), "alice")
    with pytest.raises(module.KuaishouStateError):
        parse_live_page(page(False, status=None), "alice")


@pytest.mark.parametrize(
    "html",
    [
        "<html>请登录</html>",
        page(None),
        page("false"),
        page(errorType={"title": "请求过快"}),
        page(author={"id": "recommended", "name": "推荐主播"}),
        '<script>window.__INITIAL_STATE__={"liveroom":{"playList":[]}};</script>',
    ],
)
def test_unknown_or_wrong_room_is_never_offline(html):
    with pytest.raises(ValueError):
        parse_live_page(html, "alice")


def test_undefined_conversion_preserves_names():
    html = page(author={"id": "alice", "name": "undefined"}, unused=None).replace(
        '"unused": null', '"unused": undefined'
    )
    assert parse_live_page(html, "alice")["name"] == "undefined"


@pytest.mark.parametrize(
    "target",
    [
        "alice",
        "https://live.kuaishou.com/u/alice?x=1",
        "https://www.kuaishou.com/profile/alice",
        "https://v.m.chenzhongtech.com/fw/live/alice?x=1",
        "https://c.kuaishou.com/fw/user/alice?x=1",
    ],
)
def test_target_normalization(target):
    assert principal_from_target(target) == "alice"


@pytest.mark.parametrize(
    "url",
    [
        "https://live.kuaishou.com.evil.test/u/alice",
        "http://127.0.0.1/u/alice",
        "https://user:password@live.kuaishou.com/u/alice",
        "file:///tmp/a",
        "https://live.kuaishou.com:8080/u/alice",
        "https://evil.test@live.kuaishou.com/u/alice",
    ],
)
def test_untrusted_urls_rejected(url):
    with pytest.raises(ValueError):
        checked_url(url)


@pytest_asyncio.fixture
async def database(tmp_path, monkeypatch):
    await db_module.close_shared_connection()
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "monitor.db")
    monkeypatch.setattr(db_module, "_ensure_hybrid_runtime", AsyncMock())
    async with db_module.AsyncDatabase() as db:
        yield db
    await db_module.close_shared_connection()


@pytest.mark.asyncio
async def test_baseline_transitions_dedup_and_failure(database):
    monitor = KuaishouMonitor(AppConfig())
    monitor.db = database
    monitor.send_push_news = AsyncMock()
    monitor.get_info = AsyncMock(
        return_value={"principal_id": "alice", "name": "主播", "is_live": "0"}
    )
    await monitor.process_room("alice")
    monitor.send_push_news.assert_not_awaited()
    monitor.get_info.return_value["is_live"] = "1"
    await monitor.process_room("alice")
    await monitor.process_room("alice")
    assert monitor.send_push_news.await_count == 1
    monitor.get_info.side_effect = ValueError("风控")
    with pytest.raises(ValueError):
        await monitor.process_room("alice")
    assert await database.execute_query("SELECT is_live FROM kuaishou") == [("1",)]
    monitor.get_info.side_effect = None
    monitor.get_info.return_value["is_live"] = "0"
    await monitor.process_room("alice")
    assert monitor.send_push_news.await_count == 2


@pytest.mark.asyncio
async def test_quiet_hours_update_state_without_push(database, monkeypatch):
    monitor = KuaishouMonitor(AppConfig())
    monitor.db = database
    monitor.send_push_news = AsyncMock()
    monitor.get_info = AsyncMock(
        return_value={"principal_id": "alice", "name": "主播", "is_live": "0"}
    )
    await monitor.process_room("alice")
    monitor.get_info.return_value["is_live"] = "1"
    monkeypatch.setattr(module, "is_in_quiet_hours", lambda config: True)
    await monitor.process_room("alice")
    assert await database.execute_query("SELECT is_live FROM kuaishou") == [("1",)]
    monitor.send_push_news.assert_not_awaited()


@pytest.mark.asyncio
async def test_data_routes_use_persisted_state_and_auth(database, monkeypatch):
    await database.execute_insert(
        "INSERT INTO kuaishou VALUES (:principal_id, :name, :is_live)",
        {"principal_id": "alice", "name": "主播", "is_live": "1"},
    )
    monkeypatch.setattr(data_routes, "check_login", lambda session: session == "ok")
    request = SimpleNamespace(session={"session_id": "ok"})
    response = await data_routes.get_table_data(request, "kuaishou", id="alice")
    assert response.status_code == 200
    body = json.loads(response.body)
    assert body["total"] == 1
    assert body["data"][0]["principal_id"] == "alice"
    response = await data_routes.get_monitor_status_item(request, "kuaishou", "alice")
    assert json.loads(response.body)["data"]["is_live"] == "1"
    request.session.clear()
    assert (await data_routes.get_table_data(request, "kuaishou")).status_code == 401


@pytest.mark.asyncio
async def test_http_error_never_parsed_as_offline(monkeypatch):
    class Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def text(self):
            return page(True)

    response = Response()
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    monkeypatch.setenv("WEBMONITER_KUAISHOU_COOKIE", "test-only")
    monitor = KuaishouMonitor(AppConfig(), session=SimpleNamespace(get=get))
    assert (await monitor.get_info("alice"))["is_live"] == "1"
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["headers"]["Cookie"] == "test-only"
    response.status = 403
    with pytest.raises(module.KuaishouStateError, match="HTTP 403"):
        await monitor.get_info("alice")
    response.status = 401
    with pytest.raises(module.CookieExpiredError):
        await monitor.get_info("alice")


@pytest.mark.asyncio
async def test_alias_cache_dedup_hot_reload_and_reference_cleanup(database, monkeypatch):
    short = "https://v.kuaishou.com/abc"
    cfg = AppConfig(kuaishou_enable=True, kuaishou_targets=f"alice,{short}")
    monkeypatch.setattr(module, "get_config", lambda **kwargs: cfg)
    monitor = KuaishouMonitor(cfg)
    monitor.db = database
    monitor.resolve_target = AsyncMock(return_value="alice")
    monitor.process_room = AsyncMock()
    await monitor.run()
    monitor.process_room.assert_awaited_once_with("alice")
    await monitor.run()
    assert monitor.resolve_target.await_count == 2  # 第二轮复用两个目标的持久化映射
    await database.execute_insert(
        "INSERT INTO kuaishou VALUES (:principal_id, :name, :is_live)",
        {"principal_id": "alice", "name": "主播", "is_live": "1"},
    )
    await prune_targets(database, [short])
    assert await database.execute_query("SELECT principal_id FROM kuaishou") == [("alice",)]
    await prune_targets(database, ["https://v.kuaishou.com/new"])
    assert await database.execute_query("SELECT principal_id FROM kuaishou") == [("alice",)]
    cfg.kuaishou_targets = ""
    await monitor.run()
    assert await database.execute_query("SELECT principal_id FROM kuaishou") == []


@pytest.mark.asyncio
async def test_target_deleted_during_fetch_does_not_leave_restored_records(database, monkeypatch):
    cfg = AppConfig(kuaishou_enable=True, kuaishou_targets="alice")
    monkeypatch.setattr(module, "get_config", lambda **kwargs: cfg)
    monitor = KuaishouMonitor(cfg)
    monitor.db = database
    monitor.send_push_news = AsyncMock()

    async def fetch(principal):
        cfg.kuaishou_targets = ""
        await prune_targets(database, [])
        return {"principal_id": principal, "name": "主播", "is_live": "1"}

    monitor.get_info = fetch
    await monitor.run()
    assert await database.execute_query("SELECT principal_id FROM kuaishou") == []
    assert await database.execute_query("SELECT target FROM kuaishou_targets") == []


@pytest.mark.asyncio
async def test_short_link_redirect_validation_and_no_cookie():
    calls = []

    class Response:
        status = 302
        headers = {"Location": "https://v.m.chenzhongtech.com/fw/live/alice"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class Session(Response):
        def __init__(self, **kwargs):
            assert "Cookie" not in kwargs["headers"]

        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return Response()

    monitor = KuaishouMonitor(AppConfig(kuaishou_cookie="test-only"))
    with patch.object(module.aiohttp, "ClientSession", Session):
        assert await monitor.resolve_target("https://v.kuaishou.com/abc") == "alice"
        Response.headers = {"Location": "https://c.kuaishou.com/fw/user/alice"}
        assert await monitor.resolve_target("https://v.kuaishou.com/abc") == "alice"
        Response.headers = {"Location": "http://localhost/private"}
        with pytest.raises(ValueError):
            await monitor.resolve_target("https://v.kuaishou.com/abc")
        Response.headers = {"Location": "/loop"}
        with pytest.raises(ValueError, match="跳转次数"):
            await monitor.resolve_target("https://v.kuaishou.com/abc")
    assert len(calls) == 8
    assert all(kwargs == {"allow_redirects": False} for _, kwargs in calls)


def test_config_yaml_list_env_override_and_api_row(tmp_path, monkeypatch):
    path = tmp_path / "config.yml"
    path.write_text(
        "kuaishou:\n  targets: [alice, 'https://v.kuaishou.com/a']\n  cookie: yaml-cookie\n"
    )
    cfg = AppConfig(**load_config_from_yml(str(path)))
    assert not cfg.kuaishou_enable
    monkeypatch.setenv("WEBMONITER_KUAISHOU_COOKIE", "env-cookie")
    parsed = cfg.get_kuaishou_config()
    assert parsed.targets == ["alice", "https://v.kuaishou.com/a"]
    assert parsed.cookie == "env-cookie"
    assert cfg.kuaishou_cookie == "yaml-cookie"  # 环境变量不写回配置或 Web 表单
    assert (
        _row_to_item("kuaishou", ("alice", "主播", "1"))["url"]
        == "https://live.kuaishou.com/u/alice"
    )


@pytest.mark.asyncio
async def test_new_tables_upgrade_and_offline_outbox(tmp_path):
    async with aiosqlite.connect(tmp_path / "old.db") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("CREATE TABLE old_user_data (value TEXT)")
        await conn.execute("INSERT INTO old_user_data VALUES ('keep')")
        await db_module.AsyncDatabase()._init_tables(conn)
        await db_module.AsyncDatabase()._init_tables(conn)
        assert await db_module._sqlite_query(conn, "SELECT * FROM old_user_data") == [("keep",)]
        for table, values in [
            ("kuaishou", {"principal_id": "alice", "name": "主播", "is_live": "1"}),
            (
                "kuaishou_targets",
                {"target_key": target_key("alice"), "target": "alice", "principal_id": "alice"},
            ),
        ]:
            spec = TABLE_SPECS[table]
            assert tuple(values) == spec.columns
            columns = ", ".join(values)
            placeholders = ", ".join(f":{key}" for key in values)
            await db_module._sqlite_update_with_outbox(
                conn, f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values
            )
            await db_module._sqlite_update_with_outbox(
                conn,
                f"DELETE FROM {table} WHERE {spec.primary_key}=:pk",
                {"pk": values[spec.primary_key]},
            )
        events = await db_module._load_outbox(conn)
        assert [event["operation"] for event in events] == ["upsert", "delete", "upsert", "delete"]
