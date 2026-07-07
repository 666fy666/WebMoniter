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
