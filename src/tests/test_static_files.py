"""Tests for cached static file handler."""

import httpx
import pytest
from starlette.applications import Starlette
from starlette.routing import Mount

from src.web.static_files import CachedStaticFiles


def test_cache_control_long_lived_for_post_images():
    handler = CachedStaticFiles(
        directory=".",
        short_cache_paths=("profile_image.jpg", "avatar_large.jpg"),
    )
    control = handler._cache_control_for_path("/user/posts/123456/01.thumb.jpg")
    assert control == "public, max-age=31536000, immutable"


def test_cache_control_short_lived_for_profile_avatar():
    handler = CachedStaticFiles(
        directory=".",
        short_cache_paths=("profile_image.jpg", "avatar_large.jpg"),
    )
    control = handler._cache_control_for_path("/user/profile_image.jpg")
    assert control == "public, max-age=86400"
    assert "immutable" not in control


@pytest.mark.asyncio
async def test_weibo_avatar_url_serves_local_file_with_short_cache(tmp_path, monkeypatch):
    from src.web import data_support

    folder = tmp_path / "中文 #1%"
    folder.mkdir()
    (folder / "profile_image.jpg").write_bytes(b"local-avatar")
    monkeypatch.setattr(data_support, "WEIBO_IMG_DIR", tmp_path)
    app = Starlette(
        routes=[
            Mount(
                "/weibo_img",
                app=CachedStaticFiles(directory=tmp_path, short_cache_paths=("profile_image.jpg",)),
            )
        ]
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(data_support._weibo_avatar_url(folder.name))
    assert response.status_code == 200
    assert response.content == b"local-avatar"
    assert response.headers["cache-control"] == "public, max-age=86400"
