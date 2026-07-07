"""推送通道注册一致性测试。"""

import inspect
from types import SimpleNamespace

import pytest
from aiohttp import ClientResponseError

from src.push_channel import _channel_type_to_class, get_push_channel
from src.push_channel._push_channel import PushChannel


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


class _ConcretePushChannel(PushChannel):
    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        return None


class _FakeResponse:
    def __init__(self, payload: dict, http_exc: Exception | None = None) -> None:
        self.payload = payload
        self.http_exc = http_exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    def raise_for_status(self) -> None:
        if self.http_exc:
            raise self.http_exc

    async def json(self) -> dict:
        return self.payload


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


@pytest.mark.asyncio
async def test_post_json_success_uses_json_body_and_business_code() -> None:
    session = _FakeSession(_FakeResponse({"errcode": 0}))
    channel = _ConcretePushChannel({"name": "fake", "type": "demo"}, session=session)

    result = await channel._post_json(
        "https://example.test",
        {"hello": "世界"},
        code_key="errcode",
    )

    assert result == {"errcode": 0}
    assert session.calls[0][0] == "https://example.test"
    assert session.calls[0][1]["data"].decode("utf-8") == '{"hello": "\\u4e16\\u754c"}'
    assert session.calls[0][1]["headers"] == {"Content-Type": "application/json"}


@pytest.mark.asyncio
async def test_post_json_raises_for_business_error() -> None:
    session = _FakeSession(_FakeResponse({"errcode": 40001, "errmsg": "bad token"}))
    channel = _ConcretePushChannel({"name": "fake", "type": "demo"}, session=session)

    with pytest.raises(Exception, match="bad token"):
        await channel._post_json(
            "https://example.test",
            {"hello": "world"},
            code_key="errcode",
        )


@pytest.mark.asyncio
async def test_post_json_raises_for_http_error() -> None:
    http_exc = ClientResponseError(
        SimpleNamespace(real_url="https://example.test"),
        (),
        status=500,
        message="server error",
    )
    session = _FakeSession(_FakeResponse({}, http_exc=http_exc))
    channel = _ConcretePushChannel({"name": "fake", "type": "demo"}, session=session)

    with pytest.raises(ClientResponseError):
        await channel._post_json("https://example.test", {"hello": "world"})
