"""微博图片前端展示契约。"""

import re
from pathlib import Path

STYLE_PATH = Path("src/webUI/static/css/style.css")
SCRIPT_PATH = Path("src/webUI/static/js/data.js")


def _css_rule(css: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>[^}}]+)\}}", css)
    assert match is not None, f"未找到 CSS 规则: {selector}"
    return match.group("body")


def test_weibo_thumbnails_and_lightbox_keep_complete_image_visible():
    css = STYLE_PATH.read_text(encoding="utf-8")

    for selector in (
        ".weibo-media-item .weibo-media-img",
        ".weibo-lightbox-image",
        ".weibo-lightbox-thumb img",
    ):
        assert "object-fit: contain" in _css_rule(css, selector)


def test_weibo_lightbox_uses_original_image_with_accessible_loading_states():
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "const src = lightboxImages[expectedIndex]" in script
    assert "lightboxImageEl.src = src" in script
    assert "lightboxEl.setAttribute('aria-modal', 'true')" in script
    assert 'class="weibo-lightbox-loading"' in script
    assert 'class="weibo-lightbox-error"' in script


def test_weibo_structured_content_badges_tags_and_video_cover_contract():
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    css = STYLE_PATH.read_text(encoding="utf-8")

    assert "function renderWeiboContentSegments" in script
    assert "function stripWeiboTagsFromText" in script
    assert "new RegExp(`#${escapeRegExp(tag)}#`, 'g')" in script
    assert 'class="weibo-content-link"' in script
    assert 'target="_blank" rel="noopener noreferrer"' in script
    assert "function renderWeiboContentType" in script
    assert "repost: ['转发', 'repost']" in script
    assert "function renderWeiboTags" in script
    assert "function renderWeiboVideoCover" in script
    assert 'class="weibo-video-cover-img"' in script
    assert "target.closest('a[href]')" in script
    assert ".weibo-content-type-video" in css
    assert ".weibo-tag-list" in css
    assert ".weibo-video-cover" in css


def test_weibo_video_cover_adapts_to_portrait_without_cropping():
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    css = STYLE_PATH.read_text(encoding="utf-8")

    assert "videoCover.classList.toggle('is-portrait', isPortrait)" in script
    assert "--weibo-video-aspect" in script
    assert "aspect-ratio: var(--weibo-video-aspect, 16 / 9)" in _css_rule(css, ".weibo-video-cover")
    assert "width: min(100%, 360px)" in _css_rule(css, ".weibo-video-cover.is-portrait")
    assert "object-fit: contain" in _css_rule(css, ".weibo-video-cover > .weibo-video-cover-img")
