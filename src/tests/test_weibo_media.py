"""Tests for Weibo post image persistence and API shape."""

import json
import logging

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
async def test_weibo_table_migration_adds_images_and_retweeted_columns(tmp_path):
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
    assert "转发微博" in columns


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


def test_weibo_row_to_item_parses_retweeted_status_json():
    row = (
        "1",
        "name",
        "verified",
        "intro",
        "10",
        "20",
        "text",
        "123",
        "[]",
        json.dumps(
            {
                "user_id": "2",
                "user_name": "source",
                "verified": "source verified",
                "text": "原微博正文",
                "created_at": "Tue Jun 23 18:57:39 +0800 2026",
                "mid": "456",
                "images": ["/weibo_img/name/posts/123/retweeted/456/01.jpg"],
            },
            ensure_ascii=False,
        ),
    )

    item = _weibo_row_to_item(row)

    assert item["retweeted_status"]["user_name"] == "source"
    assert item["retweeted_status"]["text"] == "原微博正文"
    assert item["retweeted_status"]["url"] == "https://m.weibo.cn/detail/456"
    assert item["retweeted_status"]["images"] == ["/weibo_img/name/posts/123/retweeted/456/01.jpg"]
    assert item["retweeted_status"]["image_thumbs"] == [
        "/weibo_img/name/posts/123/retweeted/456/01.thumb.jpg"
    ]


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

    assert (
        await monitor._fetch_long_text_content({"isLongText": "false", "mblogid": "R5tnnuAYY"})
        is None
    )
    assert (
        await monitor._fetch_long_text_content({"isLongText": "0", "mblogid": "R5tnnuAYY"}) is None
    )
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
async def test_get_info_collects_candidate_new_posts_since_old_mid(monkeypatch):
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
                        "statuses_count": 23,
                    }
                },
            },
            "statuses/mymblog": {
                "ok": 1,
                "data": {
                    "list": [
                        {
                            "isTop": 0,
                            "isLongText": False,
                            "text_raw": "第三条",
                            "pic_ids": [],
                            "pic_infos": {},
                            "pics": [],
                            "url_struct": [],
                            "created_at": "Tue Jun 23 19:03:39 +0800 2026",
                            "mid": "103",
                        },
                        {
                            "isTop": 0,
                            "isLongText": False,
                            "text_raw": "第二条",
                            "pic_ids": [],
                            "pic_infos": {},
                            "pics": [],
                            "url_struct": [],
                            "created_at": "Tue Jun 23 19:02:39 +0800 2026",
                            "mid": "102",
                        },
                        {
                            "isTop": 0,
                            "isLongText": False,
                            "text_raw": "旧微博",
                            "pic_ids": [],
                            "pic_infos": {},
                            "pics": [],
                            "url_struct": [],
                            "created_at": "Tue Jun 23 19:01:39 +0800 2026",
                            "mid": "101",
                        },
                    ]
                },
            },
        }
    )
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"), session=session)

    async def skip_save_user_images(user_info):
        return None

    monkeypatch.setattr(monitor, "_save_user_images", skip_save_user_images)

    data = await monitor.get_info("1", old_mid="101")

    assert data["mid"] == "103"
    assert data["_old_mid_found"] is True
    assert [post["mid"] for post in data["_candidate_new_posts"]] == ["103", "102"]


@pytest.mark.asyncio
async def test_get_info_stores_retweeted_status_with_long_text_and_images(monkeypatch):
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
                            "isLongText": False,
                            "mblogid": "self",
                            "text_raw": "转发理由",
                            "pic_ids": [],
                            "pic_infos": {},
                            "pics": [],
                            "url_struct": [],
                            "created_at": "Tue Jun 23 18:57:39 +0800 2026",
                            "mid": "5313045657292004",
                            "retweeted_status": {
                                "isLongText": True,
                                "mblogid": "source-long",
                                "text_raw": "原微博截断...",
                                "created_at": "Tue Jun 23 18:55:39 +0800 2026",
                                "mid": "5313045657292000",
                                "pic_ids": ["pic1"],
                                "pic_infos": {
                                    "pic1": {
                                        "largest": {"url": "https://wx1.sinaimg.cn/large/pic1.jpg"}
                                    }
                                },
                                "pics": [],
                                "user": {
                                    "idstr": "2",
                                    "screen_name": "source",
                                    "verified_reason": "source verified",
                                },
                            },
                        }
                    ]
                },
            },
            "statuses/longtext": {
                "ok": 1,
                "data": {"longTextContent_raw": "原微博完整正文"},
            },
        }
    )
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"), session=session)

    async def skip_save_user_images(user_info):
        return None

    monkeypatch.setattr(monitor, "_save_user_images", skip_save_user_images)

    data = await monitor.get_info("1")
    retweeted = json.loads(data["转发微博"])

    assert retweeted["user_name"] == "source"
    assert retweeted["verified"] == "source verified"
    assert retweeted["text"] == "原微博完整正文"
    assert retweeted["mid"] == "5313045657292000"
    assert data["_retweeted_pic_url_candidates"] == [["https://wx1.sinaimg.cn/large/pic1.jpg"]]


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
    assert (
        params["文本"]
        == "          完整长微博正文\n          #网页链接#\n\nTue Jun 23 18:57:39 +0800 2026"
    )
    assert params["图片"] == '["/weibo_img/name/posts/5313045657292004/01.jpg"]'
    assert monitor.old_data_dict["1"][6] == params["文本"]
    assert len(push_calls) == 1
    pushed_data, pushed_diff = push_calls[0]
    assert pushed_data["文本"] == params["文本"]
    assert pushed_diff == 1


@pytest.mark.asyncio
async def test_process_user_pushes_each_new_post_and_keeps_latest(monkeypatch):
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
            "          旧微博\n\nTue Jun 23 18:57:39 +0800 2026",
            "101",
            "[]",
            "{}",
        )
    }

    older_post = {
        "UID": "1",
        "用户名": "name",
        "认证信息": "verified",
        "简介": "intro",
        "粉丝数": "10",
        "微博数": "22",
        "文本": "          第二条\n\nTue Jun 23 19:02:39 +0800 2026",
        "mid": "102",
        "图片": "[]",
        "转发微博": "{}",
        "_pic_url_candidates": [],
        "_retweeted_pic_url_candidates": [],
    }
    latest_post = {
        "UID": "1",
        "用户名": "name",
        "认证信息": "verified",
        "简介": "intro",
        "粉丝数": "10",
        "微博数": "22",
        "文本": "          第三条\n\nTue Jun 23 19:03:39 +0800 2026",
        "mid": "103",
        "图片": "[]",
        "转发微博": "{}",
        "_pic_url_candidates": [],
        "_retweeted_pic_url_candidates": [],
    }
    latest_post["_candidate_new_posts"] = [latest_post, older_post]
    latest_post["_old_mid_found"] = True

    async def fake_get_info(uid, old_mid=None):
        assert uid == "1"
        assert old_mid == "101"
        return latest_post

    async def mark_cookie_valid():
        return None

    async def skip_save_images(data, keep_existing=False):
        return []

    push_calls = []

    async def record_push(data, diff):
        push_calls.append((dict(data), diff))

    monkeypatch.setattr(monitor, "get_info", fake_get_info)
    monkeypatch.setattr(monitor, "mark_cookie_valid", mark_cookie_valid)
    monkeypatch.setattr(monitor, "_save_post_images", skip_save_images)
    monkeypatch.setattr(monitor, "_save_retweeted_images", skip_save_images)
    monkeypatch.setattr(monitor, "push_notification", record_push)

    await monitor.process_user("1")

    assert len(monitor.db.update_calls) == 1
    _, params = monitor.db.update_calls[0]
    assert params["mid"] == "103"
    assert monitor.old_data_dict["1"][7] == "103"
    assert [(call[0]["mid"], call[1]) for call in push_calls] == [("102", 1), ("103", 1)]


@pytest.mark.asyncio
async def test_process_user_logs_count_delta_and_detected_count_when_mismatch(
    monkeypatch, caplog
):
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
            "          旧微博\n\nTue Jun 23 18:57:39 +0800 2026",
            "101",
            "[]",
            "{}",
        )
    }

    older_post = {
        "UID": "1",
        "用户名": "name",
        "认证信息": "verified",
        "简介": "intro",
        "粉丝数": "10",
        "微博数": "23",
        "文本": "          第二条\n\nTue Jun 23 19:02:39 +0800 2026",
        "mid": "102",
        "图片": "[]",
        "转发微博": "{}",
        "_created_at": "Tue Jun 23 19:02:39 +0800 2026",
        "_pic_url_candidates": [],
        "_retweeted_pic_url_candidates": [],
    }
    latest_post = {
        "UID": "1",
        "用户名": "name",
        "认证信息": "verified",
        "简介": "intro",
        "粉丝数": "10",
        "微博数": "23",
        "文本": "          第三条\n\nTue Jun 23 19:03:39 +0800 2026",
        "mid": "103",
        "图片": "[]",
        "转发微博": "{}",
        "_created_at": "Tue Jun 23 19:03:39 +0800 2026",
        "_pic_url_candidates": [],
        "_retweeted_pic_url_candidates": [],
    }
    latest_post["_candidate_new_posts"] = [latest_post, older_post]
    latest_post["_old_mid_found"] = False

    async def fake_get_info(uid, old_mid=None):
        assert uid == "1"
        assert old_mid == "101"
        return latest_post

    async def mark_cookie_valid():
        return None

    async def skip_save_images(data, keep_existing=False):
        return []

    async def record_push(data, diff):
        return None

    monkeypatch.setattr(monitor, "get_info", fake_get_info)
    monkeypatch.setattr(monitor, "mark_cookie_valid", mark_cookie_valid)
    monkeypatch.setattr(monitor, "_save_post_images", skip_save_images)
    monkeypatch.setattr(monitor, "_save_retweeted_images", skip_save_images)
    monkeypatch.setattr(monitor, "push_notification", record_push)
    caplog.set_level(logging.INFO, logger="WeiboMonitor")

    await monitor.process_user("1")

    assert "name 微博数增加 3，本次识别到 2 条新微博" in caplog.text


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


def test_build_description_for_retweeted_status_includes_source_user_and_text():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    data = {
        "用户名": "name",
        "认证信息": "verified",
        "简介": "intro",
        "文本": "          转发理由\n\nTue Jun 23 18:57:39 +0800 2026",
        "转发微博": json.dumps(
            {
                "user_name": "source",
                "text": "原微博正文",
                "mid": "456",
                "images": ["/weibo_img/name/posts/123/retweeted/456/01.jpg"],
            },
            ensure_ascii=False,
        ),
    }

    description = monitor._build_description_for_channel(None, data)

    assert "转发理由:👇\n转发理由" in description
    assert "原微博 @source:\n原微博正文" in description
    assert "[原微博图片] * 1" in description


def test_check_info_treats_mid_change_with_same_count_as_new_post():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    old_info = (
        "1",
        "name",
        "verified",
        "intro",
        "10",
        "20",
        "          旧微博\n\nTue Jun 23 18:57:39 +0800 2026",
        "101",
        "[]",
        "{}",
    )
    data = {
        "UID": "1",
        "用户名": "name",
        "认证信息": "verified",
        "简介": "intro",
        "粉丝数": "10",
        "微博数": "20",
        "文本": "          新微博\n\nTue Jun 23 19:03:39 +0800 2026",
        "mid": "102",
    }

    assert monitor.check_info(data, old_info) == 1


def test_check_info_ignores_older_mid_even_when_count_increases():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    old_info = (
        "1",
        "name",
        "verified",
        "intro",
        "10",
        "20",
        "          较新的微博\n\nTue Jun 23 19:03:39 +0800 2026",
        "103",
        "[]",
        "{}",
    )
    data = {
        "UID": "1",
        "用户名": "name",
        "认证信息": "verified",
        "简介": "intro",
        "粉丝数": "10",
        "微博数": "21",
        "文本": "          更早的微博\n\nTue Jun 23 18:57:39 +0800 2026",
        "mid": "102",
        "_created_at": "Tue Jun 23 18:57:39 +0800 2026",
    }

    assert monitor.check_info(data, old_info) == 0


def test_check_info_treats_same_second_higher_mid_as_new_post():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    old_info = (
        "1",
        "name",
        "verified",
        "intro",
        "10",
        "20",
        "          旧微博\n\nTue Jun 23 19:03:39 +0800 2026",
        "102",
        "[]",
        "{}",
    )
    data = {
        "UID": "1",
        "用户名": "name",
        "认证信息": "verified",
        "简介": "intro",
        "粉丝数": "10",
        "微博数": "20",
        "文本": "          同秒新微博\n\nTue Jun 23 19:03:39 +0800 2026",
        "mid": "103",
        "_created_at": "Tue Jun 23 19:03:39 +0800 2026",
    }

    assert monitor.check_info(data, old_info) == 1


@pytest.mark.asyncio
async def test_process_user_skips_older_mid_without_overwriting_snapshot(monkeypatch):
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
            "          较新的微博\n\nTue Jun 23 19:03:39 +0800 2026",
            "103",
            "[]",
            "{}",
        )
    }

    async def fake_get_info(uid, old_mid=None):
        assert uid == "1"
        assert old_mid == "103"
        return {
            "UID": "1",
            "用户名": "name",
            "认证信息": "verified",
            "简介": "intro",
            "粉丝数": "10",
            "微博数": "21",
            "文本": "          更早的微博\n\nTue Jun 23 18:57:39 +0800 2026",
            "mid": "102",
            "图片": "[]",
            "转发微博": "{}",
            "_created_at": "Tue Jun 23 18:57:39 +0800 2026",
            "_candidate_new_posts": [],
            "_old_mid_found": False,
            "_pic_url_candidates": [],
            "_retweeted_pic_url_candidates": [],
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

    assert monitor.db.update_calls == []
    assert monitor.old_data_dict["1"][7] == "103"
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
    assert not any(
        path.name.startswith(".") for path in (root_dir / safe_username / "posts").iterdir()
    )


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
