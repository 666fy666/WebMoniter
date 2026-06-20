"""UnifiedPushManager 内容截断与调用链测试。"""

import asyncio
import inspect

from src.push_channel.manager import UnifiedPushManager, _truncate_content_to_bytes


class _FakeChannel:
    name = "fake"
    max_content_bytes = 20
    plain_text_max_content_bytes = 10


def test_truncate_content_to_bytes_adds_ellipsis() -> None:
    content = "这是一段超过字节限制的中文推送正文内容"
    result = _truncate_content_to_bytes(content, 20)
    assert len(result.encode("utf-8")) <= 20
    assert result.endswith("……")


def test_ensure_content_within_limit_is_synchronous() -> None:
    manager = UnifiedPushManager([])
    assert not inspect.iscoroutinefunction(manager._ensure_content_within_limit)


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
    assert (
        manager._ensure_content_within_limit(_FakeChannel(), content, None) is content
    )


def test_send_one_does_not_accept_app_config_parameter() -> None:
    params = inspect.signature(UnifiedPushManager._send_one).parameters
    assert "app_config" not in params
