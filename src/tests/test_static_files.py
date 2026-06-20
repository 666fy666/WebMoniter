"""Tests for cached static file handler."""

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
