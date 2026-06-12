"""推送通道注册一致性测试。"""

import inspect

from src.push_channel import _channel_type_to_class, get_push_channel


def test_push_channel_types_count() -> None:
    assert len(_channel_type_to_class) == 18


def test_each_push_channel_class_is_concrete() -> None:
    for channel_type, channel_cls in _channel_type_to_class.items():
        assert channel_type == channel_type.strip(), channel_type
        assert not inspect.isabstract(channel_cls), channel_type


def test_get_push_channel_rejects_unknown_type() -> None:
    try:
        get_push_channel({"type": "__not_a_real_channel__"})
        raised = False
    except ValueError as exc:
        raised = True
        assert "不支持的通道类型" in str(exc)
    assert raised
