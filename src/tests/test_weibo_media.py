"""Tests for Weibo post image persistence and API shape."""

import json
import logging

import aiosqlite
import pytest
from PIL import Image

from src.monitors.base import CookieExpiredError
from src.monitors.weibo_monitor import WeiboMonitor
from src.push_channel.rich_text import RichText
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
async def test_weibo_table_migration_adds_weibo_display_columns(tmp_path):
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
        await conn.execute(
            "INSERT INTO weibo (UID, 用户名, 文本, mid) VALUES (?, ?, ?, ?)",
            ("1", "name", "旧正文", "123"),
        )
        await conn.commit()

        await AsyncDatabase()._init_tables(conn)

        async with conn.execute("PRAGMA table_info(weibo)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
        async with conn.execute("SELECT 用户名, 文本, mid FROM weibo WHERE UID='1'") as cursor:
            old_row = await cursor.fetchone()

    assert "图片" in columns
    assert "转发微博" in columns
    assert "正文结构" in columns
    assert "标签" in columns
    assert "内容类型" in columns
    assert "视频封面" in columns
    assert tuple(old_row) == ("name", "旧正文", "123")


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
    damaged = _weibo_row_to_item((*base_row, "[]", "{}", "not-json", "not-json", "unknown", ""))
    assert damaged["content_segments"] == []
    assert damaged["tags"] == []
    assert damaged["content_type"] == "text"


def test_weibo_row_to_item_exposes_segments_tags_type_and_video_cover():
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
        "{}",
        json.dumps(
            [
                {"type": "text", "text": "看看 "},
                {"type": "link", "text": "网页链接", "url": "https://example.com/a"},
                {"type": "link", "text": "坏链接", "url": "javascript:alert(1)"},
            ],
            ensure_ascii=False,
        ),
        '["话题一", "话题二", "话题一"]',
        "video",
        "/weibo_img/name/posts/123/video_cover.jpg",
    )

    item = _weibo_row_to_item(row)

    assert item["content_segments"] == [
        {"type": "text", "text": "看看 "},
        {"type": "link", "text": "网页链接", "url": "https://example.com/a"},
        {"type": "text", "text": "坏链接"},
    ]
    assert item["tags"] == ["话题一", "话题二"]
    assert item["content_type"] == "video"
    assert item["video_cover_thumb"].endswith("/video_cover.thumb.jpg")


def test_weibo_html_parser_preserves_order_and_hides_actual_urls():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    status = {
        "text": (
            "第一行<br><img alt='[开心]'>"
            "<a href='https://weibo.com/n/abc'>@abc</a> "
            "<a href='https://s.weibo.com/weibo?q=x'>#话题#</a> "
            "<a href='https://t.cn/A1'>https://t.cn/A1</a> "
            "<a href='javascript:alert(1)'>坏链接</a>"
            "<script>alert('x')</script>"
        ),
        "url_struct": [
            {
                "short_url": "https://t.cn/A1",
                "long_url": "https://example.com/article?id=1",
                "url_title": "网页链接",
            }
        ],
    }

    rich = monitor._get_status_rich_text(status)

    assert rich.plain_text() == "第一行\n[开心]@abc #话题# 网页链接 坏链接"
    assert "http://" not in rich.plain_text()
    assert "https://" not in rich.plain_text()
    assert rich.to_dicts()[1] == {
        "type": "link",
        "text": "网页链接",
        "url": "https://example.com/article?id=1",
    }
    assert "javascript:" not in json.dumps(rich.to_dicts())


def test_weibo_parser_unwraps_sinaurl_and_extracts_ordered_tags():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    rich = monitor._get_status_rich_text(
        {
            "text": (
                "<a href='https://weibo.cn/sinaurl?u=https%3A%2F%2Fexample.com%2Ffull'>"
                "微博视频</a> #标签一# #标签二# #标签一#"
            )
        }
    )

    assert rich.to_dicts()[0]["url"] == "https://example.com/full"
    assert monitor._extract_weibo_tags(rich.plain_text()) == ["标签一", "标签二"]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ({"retweeted_status": {"mid": "2"}}, "repost"),
        ({"page_info": {"type": "video"}}, "video"),
        (
            {
                "mix_media_info": {
                    "items": [
                        {"type": "pic", "data": {"large": {"url": "https://img/pic.jpg"}}},
                        {
                            "type": "video",
                            "data": {
                                "object_type": "video",
                                "page_pic": "https://img/video.jpg",
                            },
                        },
                    ]
                }
            },
            "video",
        ),
        ({"pic_ids": ["p1"]}, "image"),
        ({"text_raw": "正文"}, "text"),
    ],
)
def test_weibo_content_type(status, expected):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    assert monitor._get_weibo_content_type(status) == expected


def test_extract_video_cover_candidates_prefers_large_page_pic():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    candidates = monitor._extract_video_cover_candidates(
        {
            "page_info": {
                "type": "video",
                "page_pic": {
                    "pid": "cover-id",
                    "url": "https://wx1.sinaimg.cn/orj480/cover-id.jpg",
                },
            }
        }
    )

    assert candidates[0] == "https://wx1.sinaimg.cn/large/cover-id"
    assert "https://wx1.sinaimg.cn/orj480/cover-id.jpg" in candidates


def test_extract_mixed_media_images_and_video_cover_separately():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    mix_media_info = {
        "items": [
            {
                "type": "pic",
                "data": {
                    "largest": {"url": "https://wx1.sinaimg.cn/large/photo-1.jpg"},
                    "thumbnail": {"url": "https://wx1.sinaimg.cn/thumb150/photo-1.jpg"},
                },
            },
            {
                "type": "video",
                "data": {
                    "object_type": "video",
                    "page_pic": "https://wx2.sinaimg.cn/large/video-cover.jpg",
                    "pic_info": {
                        "pic_big": {"url": "https://wx2.sinaimg.cn/bmiddle/video-cover.jpg"}
                    },
                    "media_info": {
                        "stream_url": "https://video.example/video.mp4",
                        "big_pic_info": {
                            "pic_small": {"url": "https://wx2.sinaimg.cn/thumb150/video-cover.jpg"}
                        },
                    },
                },
            },
        ]
    }

    image_candidates = monitor._extract_pic_url_candidates(
        ["photo-1"],
        {},
        [],
        mix_media_info,
    )
    cover_candidates = monitor._extract_video_cover_candidates(
        {"pic_ids": ["photo-1"], "mix_media_info": mix_media_info}
    )

    assert image_candidates == [
        [
            "https://wx1.sinaimg.cn/large/photo-1.jpg",
            "https://wx1.sinaimg.cn/thumb150/photo-1.jpg",
        ]
    ]
    assert cover_candidates == [
        "https://wx2.sinaimg.cn/large/video-cover.jpg",
        "https://wx2.sinaimg.cn/bmiddle/video-cover.jpg",
        "https://wx2.sinaimg.cn/thumb150/video-cover.jpg",
    ]
    assert all("video.mp4" not in candidate for candidate in cover_candidates)


@pytest.mark.asyncio
async def test_build_status_data_keeps_mixed_video_cover_out_of_image_count():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    base_data = {
        "UID": "1",
        "用户名": "name",
        "认证信息": "",
        "简介": "",
        "粉丝数": "1",
        "微博数": "1",
    }
    status = {
        "mid": "123",
        "text": "混合媒体正文",
        "created_at": "Fri Jul 17 12:00:00 +0800 2026",
        "pic_ids": ["photo-1"],
        "mix_media_info": {
            "items": [
                {
                    "type": "pic",
                    "data": {"large": {"url": "https://wx1.sinaimg.cn/large/photo-1.jpg"}},
                },
                {
                    "type": "video",
                    "data": {
                        "object_type": "video",
                        "page_pic": "https://wx2.sinaimg.cn/large/video-cover.jpg",
                        "media_info": {"stream_url": "https://video.example/video.mp4"},
                    },
                },
            ]
        },
    }

    data = await monitor._build_status_data(base_data, status)

    assert data["内容类型"] == "video"
    assert len(data["_pic_url_candidates"]) == 1
    assert data["_video_cover_url_candidates"] == ["https://wx2.sinaimg.cn/large/video-cover.jpg"]
    assert "[图片]  *  1" in data["文本"]
    assert "[图片]  *  2" not in data["文本"]


@pytest.mark.asyncio
async def test_fetch_long_text_content_uses_mblogid_and_html_body():
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

    assert content == "完整正文"
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
async def test_fetch_long_text_content_falls_back_to_mobile_without_mblogid():
    session = _FakeWeiboSession(
        {
            "statuses/extend": {
                "ok": 1,
                "data": {"longTextContent": "移动端完整正文"},
            }
        }
    )
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"), session=session)

    status = {"isLongText": True, "mid": "5313045657292004", "text_raw": "截断正文..."}

    assert await monitor._fetch_long_text_content(status) == "移动端完整正文"
    assert session.requests[0][0] == "https://m.weibo.cn/statuses/extend"
    assert session.requests[0][1]["params"] == {"id": "5313045657292004"}


@pytest.mark.asyncio
async def test_fetch_long_text_content_falls_back_after_empty_desktop_response():
    session = _FakeWeiboSession(
        {
            "statuses/longtext": {"ok": 1, "data": {}},
            "statuses/extend": {
                "ok": 1,
                "data": {"longTextContent": "移动端补全正文"},
            },
        }
    )
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"), session=session)

    content = await monitor._fetch_long_text_content(
        {"pic_num": 10, "mblogid": "desktop-id", "mid": "mobile-id"}
    )

    assert content == "移动端补全正文"
    assert [url for url, _ in session.requests] == [
        "https://www.weibo.com/ajax/statuses/longtext",
        "https://m.weibo.cn/statuses/extend",
    ]


@pytest.mark.asyncio
async def test_fetch_long_text_content_does_not_fallback_when_cookie_expired():
    session = _FakeWeiboSession({"statuses/longtext": {"ok": -100}})
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"), session=session)

    with pytest.raises(CookieExpiredError):
        await monitor._fetch_long_text_content(
            {"isLongText": True, "mblogid": "desktop-id", "mid": "mobile-id"}
        )

    assert len(session.requests) == 1


@pytest.mark.asyncio
async def test_fetch_long_text_content_returns_none_when_both_interfaces_fail():
    session = _FakeWeiboSession(
        {
            "statuses/longtext": {"ok": 0, "data": {}},
            "statuses/extend": {"ok": 0, "data": {}},
        }
    )
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"), session=session)

    content = await monitor._fetch_long_text_content(
        {"isLongText": True, "mblogid": "desktop-id", "mid": "mobile-id"}
    )

    assert content is None
    assert len(session.requests) == 2


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

    async def record_push(data, diff, notification_reason="status"):
        push_calls.append((dict(data), diff, notification_reason))

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
    pushed_data, pushed_diff, notification_reason = push_calls[0]
    assert pushed_data["文本"] == params["文本"]
    assert pushed_diff == 1
    assert notification_reason == "long_text_backfill"


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
async def test_process_user_logs_count_delta_and_detected_count_when_mismatch(monkeypatch, caplog):
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


@pytest.mark.asyncio
async def test_process_user_silently_updates_structured_link_metadata(monkeypatch):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    monitor.db = _FakeWeiboDatabase()
    old_segments = json.dumps(
        [{"type": "link", "text": "网页链接", "url": "https://example.com/old"}],
        ensure_ascii=False,
    )
    monitor.old_data_dict = {
        "1": (
            "1",
            "name",
            "verified",
            "intro",
            "10",
            "20",
            "          网页链接\n\nTue Jun 23 18:57:39 +0800 2026",
            "5313045657292004",
            "[]",
            "{}",
            old_segments,
            "[]",
            "text",
            "",
        )
    }
    new_segments = json.dumps(
        [{"type": "link", "text": "网页链接", "url": "https://example.com/new"}],
        ensure_ascii=False,
    )

    async def fake_get_info(uid):
        return {
            "UID": uid,
            "用户名": "name",
            "认证信息": "verified",
            "简介": "intro",
            "粉丝数": "10",
            "微博数": "20",
            "文本": "          网页链接\n\nTue Jun 23 18:57:39 +0800 2026",
            "mid": "5313045657292004",
            "图片": "[]",
            "转发微博": "{}",
            "正文结构": new_segments,
            "标签": "[]",
            "内容类型": "text",
            "视频封面": "",
            "_pic_url_candidates": [],
        }

    async def mark_cookie_valid():
        return None

    push_calls = []

    async def record_push(data, diff, notification_reason="status"):
        push_calls.append((data, diff, notification_reason))

    monkeypatch.setattr(monitor, "get_info", fake_get_info)
    monkeypatch.setattr(monitor, "mark_cookie_valid", mark_cookie_valid)
    monkeypatch.setattr(monitor, "push_notification", record_push)

    await monitor.process_user("1")

    assert len(monitor.db.update_calls) == 1
    assert monitor.db.update_calls[0][1]["正文结构"] == new_segments
    assert push_calls == []


def test_build_description_for_retweeted_status_uses_cute_copy():
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

    assert isinstance(description, RichText)
    plain_text = description.plain_text()
    assert "💬 转发时说：\n　　转发理由" in plain_text
    assert "🌷 原微博来自 @source\n　　原微博正文" in plain_text
    assert "🖼️ 原微博有 1 张图片" in plain_text
    assert "✨ 认证：verified" in plain_text
    assert "🌱 简介：intro" in plain_text


def test_build_description_uses_compact_main_image_count():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    data = {
        "用户名": "name",
        "认证信息": "",
        "简介": "",
        "文本": "正文",
        "正文结构": '[{"type":"text","text":"正文"}]',
        "标签": "[]",
        "内容类型": "image",
        "图片": '["01.jpg", "02.jpg"]',
        "转发微博": "{}",
    }

    visible = monitor._build_description_for_channel(None, data).plain_text()

    assert visible.startswith("💬 Ta说：\n　　正文")
    assert "🖼️ * 2" in visible
    assert "这条微博有 2 张图片" not in visible


def test_retweeted_long_text_backfill_is_detected_only_for_same_source_mid():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    old_status = json.dumps(
        {"user_name": "source", "mid": "456", "text": "原微博长正文..."},
        ensure_ascii=False,
    )
    new_data = {
        "_retweeted_long_text_fetched": True,
        "转发微博": json.dumps(
            {"user_name": "source", "mid": "456", "text": "原微博长正文已经补完整"},
            ensure_ascii=False,
        ),
    }

    assert monitor._is_retweeted_long_text_backfill(new_data, old_status) is True

    new_data["转发微博"] = json.dumps(
        {"user_name": "source", "mid": "789", "text": "原微博长正文已经补完整"},
        ensure_ascii=False,
    )
    assert monitor._is_retweeted_long_text_backfill(new_data, old_status) is False


def test_build_description_for_empty_repost_and_hidden_link():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    data = {
        "用户名": "name",
        "认证信息": "verified",
        "简介": "intro",
        "文本": "转发微博",
        "正文结构": '[{"type":"text","text":"转发微博"}]',
        "标签": "[]",
        "内容类型": "repost",
        "转发微博": json.dumps(
            {
                "user_name": "source",
                "mid": "456",
                "content_segments": [
                    {"type": "text", "text": "原文："},
                    {
                        "type": "link",
                        "text": "网页链接",
                        "url": "https://example.com/private-target",
                    },
                ],
                "tags": ["原话题"],
                "content_type": "video",
                "video_cover": "/weibo_img/name/posts/123/retweeted/456/video_cover.jpg",
                "images": [],
            },
            ensure_ascii=False,
        ),
    }

    description = monitor._build_description_for_channel(None, data)
    visible = description.plain_text()

    assert "💬 悄悄转发，没有留下文字～" in visible
    assert "原文：网页链接" in visible
    assert "🎬 原微博带了一个视频" in visible
    assert "🏷️ #原话题#" in visible
    assert "http://" not in visible
    assert "https://" not in visible
    assert 'href="https://example.com/private-target"' in description.render("html")


def test_push_topics_are_removed_from_bodies_and_shown_once():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    data = {
        "用户名": "name",
        "认证信息": "",
        "简介": "",
        "文本": "转发正文 #转发话题#",
        "正文结构": json.dumps(
            [
                {"type": "text", "text": "转发正文 #转发话题# "},
                {
                    "type": "link",
                    "text": "网页链接",
                    "url": "https://example.com/main",
                },
            ],
            ensure_ascii=False,
        ),
        "标签": '["转发话题"]',
        "内容类型": "repost",
        "图片": "[]",
        "转发微博": json.dumps(
            {
                "user_name": "source",
                "mid": "456",
                "content_segments": [
                    {"type": "text", "text": "原微博正文 #原话题#"},
                ],
                "tags": ["原话题"],
                "content_type": "text",
                "images": [],
            },
            ensure_ascii=False,
        ),
    }

    description = monitor._build_description_for_channel(None, data)
    visible = description.plain_text()

    assert visible.count("#转发话题#") == 1
    assert visible.count("#原话题#") == 1
    assert "🏷️ #转发话题#" in visible
    assert "🏷️ #原话题#" in visible
    assert 'href="https://example.com/main"' in description.render("html")


@pytest.mark.parametrize(
    ("source_status", "expected"),
    [
        (
            {"user_name": "source", "mid": "456", "text": "", "images": ["a", "b"]},
            "原微博没有写正文，留下了 2 张图片～",
        ),
        (
            {
                "user_name": "source",
                "mid": "456",
                "text": "旧正文",
                "source_unavailable": True,
            },
            "这条原微博暂时看不到啦～",
        ),
    ],
)
def test_build_description_for_special_retweet_states(source_status, expected):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    data = {
        "用户名": "name",
        "认证信息": "",
        "简介": "",
        "文本": "转发微博",
        "正文结构": '[{"type":"text","text":"转发微博"}]',
        "标签": "[]",
        "内容类型": "repost",
        "转发微博": json.dumps(source_status, ensure_ascii=False),
    }

    visible = monitor._build_description_for_channel(None, data).plain_text()

    assert expected in visible


@pytest.mark.parametrize(
    ("content_type", "expected"),
    [
        ("repost", "✨ 小鱼 转发了一条微博～"),
        ("video", "🎬 小鱼 分享了一条新视频～"),
        ("image", "🖼️ 小鱼 发来一条新图文～"),
        ("text", "💬 小鱼 发了条微博～"),
        ("unknown", "🌟 小鱼 有一条新微博～"),
    ],
)
def test_build_push_title_by_content_type(content_type, expected):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    assert monitor._build_push_title({"用户名": "小鱼", "内容类型": content_type}, 1) == expected


def test_build_push_title_for_long_text_and_deletion():
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    data = {"用户名": "小鱼", "内容类型": "text"}

    assert (
        monitor._build_push_title(data, 1, "long_text_backfill") == "📝 小鱼 的微博正文补充完整啦"
    )
    assert monitor._build_push_title(data, -2) == "🍃 小鱼 悄悄收起了 2 条微博"


@pytest.mark.asyncio
async def test_save_main_and_retweeted_video_covers_with_thumbnails(tmp_path, monkeypatch):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    monkeypatch.setattr(monitor, "_get_weibo_data_dir", lambda: tmp_path)

    async def fake_download(candidates, save_path):
        assert candidates
        save_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (80, 45), color="pink").save(save_path, "JPEG")
        return True

    monkeypatch.setattr(monitor, "_download_post_image", fake_download)
    data = {
        "用户名": "name",
        "mid": "123",
        "图片": '["/weibo_img/name/posts/123/01.jpg"]',
        "视频封面": "",
        "_video_cover_url_candidates": ["https://img.example/main.jpg"],
        "转发微博": json.dumps(
            {
                "user_name": "source",
                "mid": "456",
                "text": "原微博",
                "content_type": "video",
                "video_cover": "",
                "images": [],
            },
            ensure_ascii=False,
        ),
        "_retweeted_video_cover_url_candidates": ["https://img.example/source.jpg"],
    }

    await monitor._save_video_cover(data)
    await monitor._save_retweeted_video_cover(data)
    retweeted = monitor._parse_retweeted_status(data["转发微博"])

    assert data["图片"] == '["/weibo_img/name/posts/123/01.jpg"]'
    assert data["视频封面"] == "/weibo_img/name/posts/123/video_cover.jpg"
    assert retweeted["video_cover"].endswith("/posts/123/retweeted/456/video_cover.jpg")
    assert (tmp_path / "name/posts/123/video_cover.jpg").is_file()
    assert (tmp_path / "name/posts/123/video_cover.thumb.jpg").is_file()
    assert (tmp_path / "name/posts/123/retweeted/456/video_cover.thumb.jpg").is_file()


def test_push_cover_prefers_current_video_cover(tmp_path, monkeypatch):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1", base_url="https://monitor.example"))
    monkeypatch.setattr(monitor, "_get_weibo_data_dir", lambda: tmp_path)
    current = tmp_path / "name/posts/123/video_cover.jpg"
    source = tmp_path / "name/posts/123/retweeted/456/video_cover.jpg"
    current.parent.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    current.write_bytes(b"current")
    source.write_bytes(b"source")
    data = {
        "用户名": "name",
        "视频封面": "/weibo_img/name/posts/123/video_cover.jpg",
        "转发微博": json.dumps(
            {
                "user_name": "source",
                "mid": "456",
                "text": "原微博",
                "video_cover": "/weibo_img/name/posts/123/retweeted/456/video_cover.jpg",
            },
            ensure_ascii=False,
        ),
    }

    cover_url, local_path = monitor._select_push_cover(data)

    assert cover_url == "https://monitor.example/weibo_img/name/posts/123/video_cover.jpg"
    assert local_path == current


@pytest.mark.asyncio
async def test_push_notification_keeps_urls_hidden_from_visible_event_text(tmp_path, monkeypatch):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    monitor.push = object()
    monkeypatch.setattr(monitor, "_get_weibo_data_dir", lambda: tmp_path)
    captured = {}

    async def capture_push(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(monitor, "send_push_news", capture_push)
    data = {
        "用户名": "小鱼",
        "认证信息": "可爱博主",
        "简介": "简介里也有 https://example.com/profile",
        "文本": "看看网页链接",
        "mid": "123",
        "图片": "[]",
        "转发微博": "{}",
        "正文结构": json.dumps(
            [
                {"type": "text", "text": "看看 "},
                {
                    "type": "link",
                    "text": "网页链接",
                    "url": "https://example.com/hidden",
                },
            ],
            ensure_ascii=False,
        ),
        "标签": "[]",
        "内容类型": "text",
        "视频封面": "",
    }

    await monitor.push_notification(data, 1)

    assert captured["title"] == "💬 小鱼 发了条微博～"
    assert isinstance(captured["description"], RichText)
    assert "https://" not in captured["description"].plain_text()
    assert "https://" not in captured["event_data"]["text"]
    assert captured["extend_data"]["hide_visible_jump_url"] is True
    assert captured["to_url"] == "https://m.weibo.cn/detail/123"


@pytest.mark.asyncio
async def test_cookie_expired_notification_uses_cute_title_and_rich_text(monkeypatch):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    monitor.push = object()
    captured = {}

    async def capture_push(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(monitor, "send_push_news", capture_push)

    await monitor.push_cookie_expired_notification()

    assert captured["title"] == "🍪 微博 Cookie 失效啦"
    assert isinstance(captured["description"], RichText)
    assert captured["extend_data"]["hide_visible_jump_url"] is True


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
async def test_process_user_skips_older_mid_without_overwriting_snapshot(monkeypatch, caplog):
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

    caplog.set_level(logging.INFO, logger="WeiboMonitor")
    await monitor.process_user("1")

    assert monitor.db.update_calls == []
    assert monitor.old_data_dict["1"][7] == "103"
    assert push_calls == []
    assert "本次接口返回的微博时间未晚于已记录微博" not in caplog.text


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


def test_commit_post_image_dir_preserves_video_and_retweeted_media_on_retry(tmp_path):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    user_dir = tmp_path / "weibo" / "user"
    current_dir = user_dir / "posts" / "100"
    temp_dir = user_dir / "posts" / ".100.tmp"
    source_dir = current_dir / "retweeted" / "200"
    source_dir.mkdir(parents=True)
    temp_dir.mkdir(parents=True)
    (current_dir / "video_cover.jpg").write_bytes(b"cover")
    (current_dir / "video_cover.thumb.jpg").write_bytes(b"thumb")
    (source_dir / "video_cover.jpg").write_bytes(b"source")
    (temp_dir / "01.jpg").write_bytes(b"new image")

    target_dir = monitor._commit_post_image_dir(user_dir, "100", temp_dir)

    assert (target_dir / "01.jpg").read_bytes() == b"new image"
    assert (target_dir / "video_cover.jpg").read_bytes() == b"cover"
    assert (target_dir / "video_cover.thumb.jpg").read_bytes() == b"thumb"
    assert (target_dir / "retweeted/200/video_cover.jpg").read_bytes() == b"source"


def test_commit_retweeted_image_dir_preserves_video_cover_on_retry(tmp_path):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    user_dir = tmp_path / "weibo" / "user"
    current_dir = user_dir / "posts" / "100" / "retweeted" / "200"
    temp_dir = current_dir.parent / ".200.tmp"
    current_dir.mkdir(parents=True)
    temp_dir.mkdir(parents=True)
    (current_dir / "video_cover.jpg").write_bytes(b"cover")
    (current_dir / "video_cover.thumb.jpg").write_bytes(b"thumb")
    (temp_dir / "01.jpg").write_bytes(b"new image")

    target_dir = monitor._commit_retweeted_image_dir(user_dir, "100", "200", temp_dir)

    assert (target_dir / "01.jpg").read_bytes() == b"new image"
    assert (target_dir / "video_cover.jpg").read_bytes() == b"cover"
    assert (target_dir / "video_cover.thumb.jpg").read_bytes() == b"thumb"


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


def test_needs_video_cover_retry_until_local_file_exists(tmp_path, monkeypatch):
    monitor = WeiboMonitor(AppConfig(weibo_uids="1"))
    root_dir = tmp_path / "weibo"
    monkeypatch.setattr(monitor, "_get_weibo_data_dir", lambda: root_dir)
    cover_url = "/weibo_img/name/posts/123/video_cover.jpg"
    data = {
        "mid": "123",
        "_video_cover_url_candidates": ["https://img.example/cover.jpg"],
    }
    old_info = (
        "1",
        "name",
        "verified",
        "intro",
        "10",
        "20",
        "text",
        "123",
        "[]",
        "{}",
        "[]",
        "[]",
        "video",
        cover_url,
    )

    assert monitor._needs_video_cover_retry(data, old_info) is True

    cover_path = root_dir / "name/posts/123/video_cover.jpg"
    cover_path.parent.mkdir(parents=True)
    cover_path.write_bytes(b"cover")

    assert monitor._needs_video_cover_retry(data, old_info) is False


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
