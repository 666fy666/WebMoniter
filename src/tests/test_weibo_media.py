"""Tests for Weibo post image persistence and API shape."""

import json

import aiosqlite
import pytest
from PIL import Image

from src.monitors.weibo_monitor import WeiboMonitor
from src.settings.config import AppConfig
from src.storage.database import AsyncDatabase
from src.web.data_support import _weibo_row_to_item


class _FakeWeiboResponse:
    def __init__(self, payload: dict, status: int = 200):
        self.payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    async def json(self):
        return self.payload


class _FakeWeiboSession:
    def __init__(self, payloads: dict[str, dict]):
        self.payloads = payloads
        self.headers = {}
        self.requests = []

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        for marker, payload in self.payloads.items():
            if marker in url:
                return _FakeWeiboResponse(payload)
        raise AssertionError(f"unexpected url: {url}")


class _FakeWeiboDatabase:
    def __init__(self):
        self.update_calls = []

    async def execute_update(self, sql, params):
        self.update_calls.append((sql, dict(params)))
        return True


@pytest.mark.asyncio
async def test_weibo_table_migration_adds_images_column(tmp_path):
    db_path = tmp_path / "old.db"
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            CREATE TABLE weibo (
                UID TEXT PRIMARY KEY,
                用户名 TEXT NOT NULL,
                认证信息 TEXT,
                简介 TEXT,
                粉丝数 TEXT,
                微博数 TEXT,
                文本 TEXT,
                mid TEXT
            )
            """
        )
        await conn.commit()

        await AsyncDatabase()._init_tables(conn)

        async with conn.execute("PRAGMA table_info(weibo)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]

    assert "图片" in columns


def test_weibo_row_to_item_parses_images_json():
    row = (
        "1",
        "name",
        "verified",
        "intro",
        "10",
        "20",
        "text",
        "123",
        '["/weibo_img/name/posts/123/01.jpg", "", 1]',
    )

    item = _weibo_row_to_item(row)

    assert item["images"] == ["/weibo_img/name/posts/123/01.jpg"]
    assert item["image_thumbs"] == ["/weibo_img/name/posts/123/01.thumb.jpg"]


def test_weibo_row_to_item_handles_empty_or_invalid_images():
    base_row = ("1", "name", "verified", "intro", "10", "20", "text", "123")

    assert _weibo_row_to_item(base_row)["images"] == []
    assert _weibo_row_to_item((*base_row, ""))["images"] == []
    assert _weibo_row_to_item((*base_row, "not-json"))["images"] == []


@pytest.mark.asyncio
async def test_fetch_long_text_content_uses_mblogid_and_raw_body():
    session = _FakeWeiboSession(
        {
            "statuses/longtext": {
                "ok": 1,
                "data": {
                    "longTextContent": "完整正文",
                    "longTextContent_raw": "完整原始正文",
                },
            }
        }
    )
    monitor = WeiboMonitor(
        AppConfig(weibo_cookie="SUB=abc; XSRF-TOKEN=token-1", weibo_uids="1"),
        session=session,
    )

    content = await monitor._fetch_long_text_content(
        {"isLongText": True, "mblogid": "R5tnnuAYY", "text_raw": "截断正文"}
    )

    assert content == "完整原始正文"
    assert session.requests == [
        (
            "https://www.weibo.com/ajax/statuses/longtext",
            {"params": {"id": "R5tnnuAYY"}, "headers": {"X-XSRF-TOKEN": "token-1"}},
        )
    ]


@pytest.mark.asyncio
async def test_fetch_long_text_content_skips_normal_status():
    session = _FakeWeiboSession({})
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"), session=session)

    assert await monitor._fetch_long_text_content({"isLongText": False}) is None
    assert session.requests == []


@pytest.mark.asyncio
async def test_fetch_long_text_content_skips_string_false_status():
    session = _FakeWeiboSession({})
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"), session=session)

    assert await monitor._fetch_long_text_content({"isLongText": "false", "mblogid": "R5tnnuAYY"}) is None
    assert await monitor._fetch_long_text_content({"isLongText": "0", "mblogid": "R5tnnuAYY"}) is None
    assert session.requests == []


@pytest.mark.asyncio
async def test_fetch_long_text_content_requires_mblogid():
    session = _FakeWeiboSession({})
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"), session=session)

    status = {"isLongText": True, "mid": "5313045657292004", "text_raw": "截断正文..."}

    assert await monitor._fetch_long_text_content(status) is None
    assert session.requests == []


@pytest.mark.asyncio
async def test_get_info_stores_full_long_text(monkeypatch):
    session = _FakeWeiboSession(
        {
            "profile/info": {
                "ok": 1,
                "data": {
                    "user": {
                        "idstr": "1",
                        "screen_name": "name",
                        "verified_reason": "verified",
                        "description": "intro",
                        "followers_count_str": "10",
                        "statuses_count": 20,
                    }
                },
            },
            "statuses/mymblog": {
                "ok": 1,
                "data": {
                    "list": [
                        {
                            "isTop": 0,
                            "isLongText": True,
                            "mblogid": "R5tnnuAYY",
                            "text_raw": "截断正文...",
                            "pic_ids": [],
                            "pic_infos": {},
                            "pics": [],
                            "url_struct": [],
                            "created_at": "Tue Jun 23 18:57:39 +0800 2026",
                            "mid": "5313045657292004",
                        }
                    ]
                },
            },
            "statuses/longtext": {
                "ok": 1,
                "data": {"longTextContent_raw": "完整长微博正文"},
            },
        }
    )
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"), session=session)

    async def skip_save_user_images(user_info):
        return None

    monkeypatch.setattr(monitor, "_save_user_images", skip_save_user_images)

    data = await monitor.get_info("1")

    assert "完整长微博正文" in data["文本"]
    assert "截断正文" not in data["文本"]
    assert data["_text_raw"] == "完整长微博正文"


@pytest.mark.asyncio
async def test_process_user_pushes_long_text_backfill(monkeypatch):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    monitor.db = _FakeWeiboDatabase()
    monitor.old_data_dict = {
        "1": (
            "1",
            "name",
            "verified",
            "intro",
            "10",
            "20",
            "          完整长微博...\n          #网页链接#\n\nTue Jun 23 18:57:39 +0800 2026",
            "5313045657292004",
            '["/weibo_img/name/posts/5313045657292004/01.jpg"]',
        )
    }

    async def fake_get_info(uid):
        return {
            "UID": uid,
            "用户名": "name",
            "认证信息": "verified",
            "简介": "intro",
            "粉丝数": "10",
            "微博数": "20",
            "文本": "          完整长微博正文\n          #网页链接#\n\nTue Jun 23 18:57:39 +0800 2026",
            "mid": "5313045657292004",
            "图片": "[]",
            "_long_text_fetched": True,
            "_list_text_raw": "完整长微博...",
            "_pic_url_candidates": [],
        }

    async def mark_cookie_valid():
        return None

    push_calls = []

    async def record_push(data, diff):
        push_calls.append((dict(data), diff))

    monkeypatch.setattr(monitor, "get_info", fake_get_info)
    monkeypatch.setattr(monitor, "mark_cookie_valid", mark_cookie_valid)
    monkeypatch.setattr(monitor, "push_notification", record_push)

    await monitor.process_user("1")

    assert len(monitor.db.update_calls) == 1
    _, params = monitor.db.update_calls[0]
    assert params["文本"] == "          完整长微博正文\n          #网页链接#\n\nTue Jun 23 18:57:39 +0800 2026"
    assert params["图片"] == '["/weibo_img/name/posts/5313045657292004/01.jpg"]'
    assert monitor.old_data_dict["1"][6] == params["文本"]
    assert len(push_calls) == 1
    pushed_data, pushed_diff = push_calls[0]
    assert pushed_data["文本"] == params["文本"]
    assert pushed_diff == 1


@pytest.mark.asyncio
async def test_process_user_skips_equivalent_long_text_backfill(monkeypatch):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    monitor.db = _FakeWeiboDatabase()
    monitor.old_data_dict = {
        "1": (
            "1",
            "name",
            "verified",
            "intro",
            "10",
            "20",
            "          完整长微博正文\n\nTue Jun 23 18:57:39 +0800 2026",
            "5313045657292004",
            "[]",
        )
    }

    async def fake_get_info(uid):
        return {
            "UID": uid,
            "用户名": "name",
            "认证信息": "verified",
            "简介": "intro",
            "粉丝数": "10",
            "微博数": "20",
            "文本": "          完整长微博正文\u200b\n\nTue Jun 23 18:57:39 +0800 2026",
            "mid": "5313045657292004",
            "图片": "[]",
            "_long_text_fetched": True,
            "_list_text_raw": "完整长微博...",
            "_pic_url_candidates": [],
        }

    push_calls = []

    async def mark_cookie_valid():
        return None

    async def record_push(data, diff):
        push_calls.append((dict(data), diff))

    monkeypatch.setattr(monitor, "get_info", fake_get_info)
    monkeypatch.setattr(monitor, "mark_cookie_valid", mark_cookie_valid)
    monkeypatch.setattr(monitor, "push_notification", record_push)

    await monitor.process_user("1")

    assert monitor.db.update_calls == []
    assert push_calls == []


@pytest.mark.asyncio
async def test_process_user_updates_non_backfill_text_without_push(monkeypatch):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    monitor.db = _FakeWeiboDatabase()
    monitor.old_data_dict = {
        "1": (
            "1",
            "name",
            "verified",
            "intro",
            "10",
            "20",
            "          另一段旧正文\n\nTue Jun 23 18:57:39 +0800 2026",
            "5313045657292004",
            "[]",
        )
    }

    async def fake_get_info(uid):
        return {
            "UID": uid,
            "用户名": "name",
            "认证信息": "verified",
            "简介": "intro",
            "粉丝数": "10",
            "微博数": "20",
            "文本": "          完整长微博正文\n\nTue Jun 23 18:57:39 +0800 2026",
            "mid": "5313045657292004",
            "图片": "[]",
            "_long_text_fetched": True,
            "_list_text_raw": "完整长微博...",
            "_pic_url_candidates": [],
        }

    push_calls = []

    async def mark_cookie_valid():
        return None

    async def record_push(data, diff):
        push_calls.append((dict(data), diff))

    monkeypatch.setattr(monitor, "get_info", fake_get_info)
    monkeypatch.setattr(monitor, "mark_cookie_valid", mark_cookie_valid)
    monkeypatch.setattr(monitor, "push_notification", record_push)

    await monitor.process_user("1")

    assert len(monitor.db.update_calls) == 1
    assert push_calls == []


def test_make_post_thumbnail_creates_small_jpeg(tmp_path):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    image_path = tmp_path / "01.jpg"
    thumb_path = monitor._get_post_thumbnail_path(image_path)
    Image.new("RGB", (1200, 800), (240, 120, 160)).save(image_path)

    assert monitor._make_post_thumbnail(image_path, thumb_path) is True

    with Image.open(thumb_path) as img:
        assert img.format == "JPEG"
        assert max(img.size) <= 480


def test_commit_post_image_dir_replaces_old_mid(tmp_path):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    user_dir = tmp_path / "weibo" / "user"
    old_dir = user_dir / "posts" / "100"
    temp_dir = user_dir / "posts" / ".200.tmp"
    old_dir.mkdir(parents=True)
    temp_dir.mkdir(parents=True)
    (old_dir / "01.jpg").write_bytes(b"old")
    (temp_dir / "01.jpg").write_bytes(b"new")

    target_dir = monitor._commit_post_image_dir(user_dir, "200", temp_dir)

    assert target_dir == user_dir / "posts" / "200"
    assert (target_dir / "01.jpg").read_bytes() == b"new"
    assert not old_dir.exists()
    assert not temp_dir.exists()


def test_commit_post_image_dir_keeps_same_mid(tmp_path):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    user_dir = tmp_path / "weibo" / "user"
    current_dir = user_dir / "posts" / "100"
    stale_dir = user_dir / "posts" / "99"
    current_dir.mkdir(parents=True)
    stale_dir.mkdir(parents=True)
    (current_dir / "01.jpg").write_bytes(b"current")
    (stale_dir / "01.jpg").write_bytes(b"stale")

    target_dir = monitor._commit_post_image_dir(user_dir, "100", None)

    assert target_dir == current_dir
    assert (current_dir / "01.jpg").read_bytes() == b"current"
    assert not stale_dir.exists()


def test_needs_post_image_retry_when_local_file_is_missing(tmp_path, monkeypatch):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    root_dir = tmp_path / "weibo"
    monkeypatch.setattr(monitor, "_get_weibo_data_dir", lambda: root_dir)

    safe_username = monitor._sanitize_username("name")
    post_dir = root_dir / safe_username / "posts" / "123"
    post_dir.mkdir(parents=True)
    (post_dir / "01.jpg").write_bytes(b"image")

    image_urls = [
        monitor._build_weibo_img_url(safe_username, "posts", "123", "01.jpg"),
        monitor._build_weibo_img_url(safe_username, "posts", "123", "02.jpg"),
    ]
    data = {"mid": "123", "_pic_url_candidates": [["a"], ["b"]]}
    old_info = ("1", "name", "verified", "intro", "10", "20", "text", "123", json.dumps(image_urls))

    assert monitor._needs_post_image_retry(data, old_info) is True

    (post_dir / "02.jpg").write_bytes(b"image")

    assert monitor._needs_post_image_retry(data, old_info) is False


@pytest.mark.asyncio
async def test_save_post_images_keeps_existing_images_when_retry_fails(tmp_path, monkeypatch):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    root_dir = tmp_path / "weibo"
    monkeypatch.setattr(monitor, "_get_weibo_data_dir", lambda: root_dir)

    safe_username = monitor._sanitize_username("name")
    post_dir = root_dir / safe_username / "posts" / "123"
    post_dir.mkdir(parents=True)
    (post_dir / "01.jpg").write_bytes(b"existing")
    existing_url = monitor._build_weibo_img_url(safe_username, "posts", "123", "01.jpg")

    async def fail_download(candidates, save_path):
        return False

    async def no_refreshed_links(uid, mid):
        return []

    monkeypatch.setattr(monitor, "_download_post_image", fail_download)
    monkeypatch.setattr(monitor, "_refresh_post_pic_url_candidates", no_refreshed_links)

    data = {
        "UID": "1",
        "用户名": "name",
        "mid": "123",
        "图片": json.dumps([existing_url]),
        "_pic_url_candidates": [["stale1"], ["stale2"]],
    }

    image_urls = await monitor._save_post_images(data, keep_existing=True)

    assert image_urls == [existing_url]
    assert json.loads(data["图片"]) == [existing_url]
    assert (post_dir / "01.jpg").read_bytes() == b"existing"
    assert not any(path.name.startswith(".") for path in (root_dir / safe_username / "posts").iterdir())


@pytest.mark.asyncio
async def test_save_post_images_retries_with_refreshed_links(tmp_path, monkeypatch):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    root_dir = tmp_path / "weibo"
    monkeypatch.setattr(monitor, "_get_weibo_data_dir", lambda: root_dir)
    monkeypatch.setattr(monitor, "_make_post_thumbnail", lambda image_path, thumb_path: True)

    async def fake_download(candidates, save_path):
        if str(candidates[0]).startswith("fresh"):
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(b"image")
            return True
        return False

    async def refreshed_links(uid, mid):
        return [["fresh1"], ["fresh2"]]

    monkeypatch.setattr(monitor, "_download_post_image", fake_download)
    monkeypatch.setattr(monitor, "_refresh_post_pic_url_candidates", refreshed_links)

    data = {
        "UID": "1",
        "用户名": "name",
        "mid": "123",
        "图片": "[]",
        "_pic_url_candidates": [["stale1"], ["stale2"]],
    }

    image_urls = await monitor._save_post_images(data)
    safe_username = monitor._sanitize_username("name")
    post_dir = root_dir / safe_username / "posts" / "123"

    assert image_urls == [
        monitor._build_weibo_img_url(safe_username, "posts", "123", "01.jpg"),
        monitor._build_weibo_img_url(safe_username, "posts", "123", "02.jpg"),
    ]
    assert json.loads(data["图片"]) == image_urls
    assert (post_dir / "01.jpg").read_bytes() == b"image"
    assert (post_dir / "02.jpg").read_bytes() == b"image"
