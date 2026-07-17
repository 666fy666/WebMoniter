"""UnifiedPushManager 内容截断与调用链测试。"""

import asyncio
import logging

import pytest

from src.push_channel import manager as manager_module
from src.push_channel.manager import (
    UnifiedPushManager,
    _truncate_content_to_bytes,
    build_push_manager,
)
from src.push_channel.rich_text import RichTextBuilder


class _FakeChannel:
    name = "fake"
    max_content_bytes = 20
    plain_text_max_content_bytes = 10


class _RecordingChannel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.sent: list[dict] = []

    async def push(self, **kwargs) -> None:
        self.sent.append(kwargs)

    async def close(self) -> None:
        return None


def test_truncate_content_to_bytes_adds_ellipsis() -> None:
    content = "这是一段超过字节限制的中文推送正文内容"
    result = _truncate_content_to_bytes(content, 20)
    assert len(result.encode("utf-8")) <= 20
    assert result.endswith("……")


def test_ensure_content_within_limit_returns_str_not_coroutine() -> None:
    manager = UnifiedPushManager([_FakeChannel()])
    result = manager._ensure_content_within_limit(
        _FakeChannel(),
        "short",
        {"plain_text": True},
    )
    assert isinstance(result, str)
    assert not asyncio.iscoroutine(result)


def test_ensure_content_within_limit_uses_plain_text_limit() -> None:
    manager = UnifiedPushManager([_FakeChannel()])
    content = "这是一段超过纯文本字节限制的推送正文"
    result = manager._ensure_content_within_limit(
        _FakeChannel(),
        content,
        {"plain_text": True},
    )
    assert len(result.encode("utf-8")) <= _FakeChannel.plain_text_max_content_bytes


def test_ensure_content_within_limit_keeps_short_content() -> None:
    manager = UnifiedPushManager([_FakeChannel()])
    content = "ok"
    assert manager._ensure_content_within_limit(_FakeChannel(), content, None) is content


@pytest.mark.asyncio
async def test_build_push_manager_skips_and_closes_failed_initialized_channel(monkeypatch) -> None:
    class BrokenChannel:
        name = "broken"

        def __init__(self) -> None:
            self.closed = False

        async def initialize(self) -> None:
            raise RuntimeError("boom")

        async def close(self) -> None:
            self.closed = True

    class GoodChannel:
        name = "good"

        async def initialize(self) -> None:
            return None

        async def close(self) -> None:
            return None

    broken = BrokenChannel()
    good = GoodChannel()

    def fake_get_push_channel(config, session):
        return broken if config["name"] == "broken" else good

    monkeypatch.setattr(manager_module, "get_push_channel", fake_get_push_channel)

    push_manager = await build_push_manager(
        [{"name": "broken", "type": "demo"}, {"name": "good", "type": "demo"}],
        session=None,
        logger=logging.getLogger(__name__),
    )

    assert push_manager is not None
    assert push_manager.push_channels == [good]
    assert broken.closed is True


@pytest.mark.asyncio
async def test_description_func_error_does_not_block_other_channels() -> None:
    broken = _RecordingChannel("broken")
    good = _RecordingChannel("good")
    push_manager = UnifiedPushManager([broken, good])

    def description_for(channel):
        if channel.name == "broken":
            raise RuntimeError("bad description")
        return "ok content"

    result = await push_manager.send_news(
        title="title",
        description="fallback",
        to_url="",
        description_func=description_for,
    )

    assert "good" in result["results"]
    assert result["errors"] == ["broken: bad description"]
    assert broken.sent == []
    assert good.sent[0]["content"] == "ok content"


@pytest.mark.asyncio
async def test_manager_applies_cute_copy_to_task_notifications() -> None:
    channel = _RecordingChannel("recording")
    push_manager = UnifiedPushManager([channel])

    result = await push_manager.send_news(
        title="品赞签到成功",
        description="获得 10 积分",
        to_url="",
    )

    assert result["errors"] == []
    assert channel.sent[0]["title"] == "🎉 品赞签到成功啦～"
    assert channel.sent[0]["content"] == ("🎁 好耶，今天的任务顺利完成啦～\n\n获得 10 积分")


@pytest.mark.asyncio
async def test_rich_text_is_rendered_per_channel_without_visible_url() -> None:
    plain = _RecordingChannel("plain")
    markdown = _RecordingChannel("markdown")
    html = _RecordingChannel("html")
    markdown_images = _RecordingChannel("markdown-images")
    html_images = _RecordingChannel("html-images")
    plain.rich_text_format = "plain"
    markdown.rich_text_format = "markdown"
    html.rich_text_format = "html"
    markdown_images.rich_text_format = "markdown"
    markdown_images.supports_inline_emoji = True
    html_images.rich_text_format = "html"
    html_images.supports_inline_emoji = True
    push_manager = UnifiedPushManager([plain, markdown, html, markdown_images, html_images])
    description = (
        RichTextBuilder()
        .text("正文里的 ")
        .link("网页链接", "https://example.com/hidden-target")
        .text(" 可以点开，表情是 ")
        .emoji("[泪]", "https://face.t.sinajs.cn/expression/tear.png")
        .build()
    )

    result = await push_manager.send_news(
        title="title",
        description=description,
        to_url="https://example.com/detail",
    )

    assert result["errors"] == []
    assert plain.sent[0]["content"] == "正文里的 网页链接 可以点开，表情是 [泪]"
    assert "http://" not in plain.sent[0]["content"]
    assert "https://" not in plain.sent[0]["content"]
    assert "[网页链接](https://example.com/hidden-target)" in markdown.sent[0]["content"]
    assert '<a href="https://example.com/hidden-target">网页链接</a>' in html.sent[0]["content"]
    for channel in (plain, markdown, html):
        assert "face.t.sinajs.cn" not in channel.sent[0]["content"]
    assert "\\[泪\\]" in markdown.sent[0]["content"]
    assert "[泪]" in html.sent[0]["content"]
    assert (
        "![\\[泪\\]](https://face.t.sinajs.cn/expression/tear.png)"
        in markdown_images.sent[0]["content"]
    )
    assert (
        '<img src="https://face.t.sinajs.cn/expression/tear.png" alt="[泪]"'
        in html_images.sent[0]["content"]
    )
    assert description.to_dicts()[-1] == {
        "type": "emoji",
        "text": "[泪]",
        "src": "https://face.t.sinajs.cn/expression/tear.png",
    }
    assert plain.sent[0]["extend_data"]["_rich_text_format"] == "plain"
    assert markdown.sent[0]["extend_data"]["_rich_text_format"] == "markdown"
    assert html.sent[0]["extend_data"]["_rich_text_format"] == "html"


def test_rich_text_rejects_unsafe_url_and_truncates_without_broken_markup() -> None:
    description = (
        RichTextBuilder()
        .text("开头")
        .link("坏链接", "javascript:alert(1)")
        .link("网页链接", "https://example.com/a")
        .text("结尾")
        .build()
    )

    assert description.plain_text() == "开头坏链接网页链接结尾"
    assert "javascript:" not in description.render("html")
    truncated_html = description.render("html", max_bytes=36)
    truncated_markdown = description.render("markdown", max_bytes=36)
    assert len(truncated_html.encode("utf-8")) <= 36
    assert len(truncated_markdown.encode("utf-8")) <= 36
    assert truncated_html.count("<a ") == truncated_html.count("</a>")
    assert truncated_markdown.count("[") == truncated_markdown.count("](")


def test_rich_text_inline_emoji_truncation_falls_back_to_alt_text() -> None:
    description = (
        RichTextBuilder().emoji("[泪]", "https://face.t.sinajs.cn/expression/tear.png").build()
    )

    truncated = description.render("html", max_bytes=15, allow_inline_images=True)

    assert truncated == "[泪]……"
    assert "https://" not in truncated
