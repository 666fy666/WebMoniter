"""推送通道注册一致性测试。"""

import inspect
from types import SimpleNamespace

import pytest
from aiohttp import ClientResponseError

from src.push_channel import _channel_type_to_class, get_push_channel
from src.push_channel._push_channel import PushChannel
from src.push_channel.dingtalk_bot import DingtalkBot
from src.push_channel.email import Email
from src.push_channel.gotify import Gotify
from src.push_channel.pushplus import PushPlus
from src.push_channel.server_chan_3 import ServerChan3
from src.push_channel.server_chan_turbo import ServerChanTurbo
from src.push_channel.telegram_bot import TelegramBot
from src.push_channel.wxpusher import WxPusher


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


def test_dingtalk_sign_is_not_pre_url_encoded(monkeypatch) -> None:
    monkeypatch.setattr("src.push_channel.dingtalk_bot.time.time", lambda: 1_700_000_000.123)
    channel = DingtalkBot({"name": "dingtalk", "type": "dingtalk_bot", "secret": "secret"})

    timestamp, sign = channel._calculate_sign()

    assert timestamp == "1700000000123"
    assert "%" not in sign
    assert "+" in sign or "/" in sign or sign.endswith("=")


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


@pytest.mark.asyncio
async def test_wxpusher_plain_mode_can_hide_visible_jump_url() -> None:
    session = _FakeSession(_FakeResponse({"success": True}))
    channel = WxPusher(
        {
            "name": "wx",
            "type": "wxpusher",
            "app_token": "token",
            "uids": "uid",
            "content_type": "1",
        },
        session=session,
    )

    await channel.push(
        "标题",
        "正文只有网页链接标题",
        jump_url="https://example.com/detail",
        extend_data={"hide_visible_jump_url": True},
    )

    payload = session.calls[0][1]["json"]
    assert "https://" not in payload["content"]
    assert payload["url"] == "https://example.com/detail"


def test_wxpusher_accepts_string_markdown_content_type() -> None:
    channel = WxPusher(
        {
            "name": "wx",
            "type": "wxpusher",
            "app_token": "token",
            "uids": "uid",
            "content_type": "3",
        }
    )

    assert channel.content_type == 3
    assert channel.rich_text_format == "markdown"


def test_only_capable_channels_enable_inline_weibo_emoji() -> None:
    pushplus_html = PushPlus(
        {"name": "pushplus", "type": "pushplus", "token": "token", "template": "html"}
    )
    pushplus_text = PushPlus(
        {"name": "pushplus", "type": "pushplus", "token": "token", "template": "txt"}
    )
    wx_html = WxPusher({"name": "wx", "type": "wxpusher", "app_token": "token", "content_type": 2})
    wx_markdown = WxPusher(
        {"name": "wx", "type": "wxpusher", "app_token": "token", "content_type": 3}
    )
    wx_plain = WxPusher({"name": "wx", "type": "wxpusher", "app_token": "token", "content_type": 1})

    assert Email.supports_inline_emoji is True
    assert ServerChanTurbo.supports_inline_emoji is True
    assert ServerChan3.supports_inline_emoji is True
    assert Gotify.supports_inline_emoji is True
    assert pushplus_html.supports_inline_emoji is True
    assert pushplus_text.supports_inline_emoji is False
    assert wx_html.supports_inline_emoji is True
    assert wx_markdown.supports_inline_emoji is True
    assert wx_plain.supports_inline_emoji is False
    assert TelegramBot.supports_inline_emoji is False


@pytest.mark.asyncio
async def test_gotify_declares_markdown_for_rich_content_without_jump_url() -> None:
    session = _FakeSession(_FakeResponse({}))
    channel = Gotify(
        {
            "name": "gotify",
            "type": "gotify",
            "web_server_url": "https://gotify.example/message?token=token",
        },
        session=session,
    )

    await channel.push(
        "标题",
        "![表情](https://example.com/emoji.png)",
        extend_data={"_rich_text_format": "markdown"},
    )

    payload = session.calls[0][1]["json"]
    assert payload["extras"] == {"client::display": {"contentType": "text/markdown"}}

    await channel.push("标题", "普通任务文本")

    assert "extras" not in session.calls[1][1]["json"]
