"""Tests for Weibo post image persistence and API shape."""

import aiosqlite
import pytest
from PIL import Image

from src.monitors.weibo_monitor import WeiboMonitor
from src.settings.config import AppConfig
from src.storage.database import AsyncDatabase
from src.web.data_support import _weibo_row_to_item


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
