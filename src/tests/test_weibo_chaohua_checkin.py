from __future__ import annotations

from typing import Any

import pytest

from src.tasks import weibo_chaohua_checkin as chaohua


class _FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = "{}"

    def json(self) -> object:
        return self._payload


class _FakeSession:
    def __init__(self, spa_payload: dict, list_payload: dict, sign_payload: dict | None = None):
        self.headers: dict[str, str] = {}
        self.spa_payload = spa_payload
        self.list_payload = list_payload
        self.sign_payload = sign_payload or {"code": "382004", "msg": "已签到"}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs) -> _FakeResponse:
        self.calls.append((url, kwargs))
        if url == chaohua.WEIBO_SPA_CONFIG_URL:
            return _FakeResponse(self.spa_payload)
        if url == chaohua.WEIBO_CHAOHUA_LIST_URL:
            return _FakeResponse(self.list_payload)
        if url == chaohua.CHAOHUA_SIGN_URL:
            return _FakeResponse(self.sign_payload)
        raise AssertionError(f"unexpected URL: {url}")


def test_anonymous_ok_response_is_not_reported_as_success(monkeypatch) -> None:
    secret = "do-not-log"
    session = _FakeSession(
        {"ok": 1, "data": {"isNormal": False}},
        {"ok": 1, "data": {"list": [], "total_number": 0}},
    )
    monkeypatch.setattr(chaohua.requests, "Session", lambda: session)

    result = chaohua._run_weibo_chaohua_sign_sync(
        f"SUB={secret}; XSRF-TOKEN=token"
    )

    assert result[0] is False
    assert "未识别到完整微博登录账号" in result[1]
    assert secret not in str(result)
    assert [url for url, _ in session.calls] == [chaohua.WEIBO_SPA_CONFIG_URL]


def test_valid_login_with_no_followed_topics_is_a_real_empty_success(monkeypatch) -> None:
    session = _FakeSession(
        {"ok": 1, "data": {"uid": "1234567890", "isNormal": True}},
        {
            "ok": 1,
            "data": {"list": [], "total_number": 0, "max_page": 1},
        },
    )
    monkeypatch.setattr(chaohua.requests, "Session", lambda: session)

    result = chaohua._run_weibo_chaohua_sign_sync(
        "SUB=valid; XSRF-TOKEN=token"
    )

    assert result == (True, "UID 12***90", 0, 0, 0, 0)
    list_call = session.calls[1][1]
    assert list_call["params"]["uid"] == "1234567890"
    assert list_call["headers"]["Referer"].endswith(
        "/1234567890/231093_-_chaohua"
    )


def test_followed_topic_is_parsed_and_signed(monkeypatch) -> None:
    session = _FakeSession(
        {"ok": 1, "data": {"uid": "1234567890"}},
        {
            "ok": 1,
            "data": {
                "list": [
                    {
                        "oid": "1022:100808example",
                        "topic_name": "示例超话",
                    }
                ],
                "total_number": 1,
                "max_page": 1,
            },
        },
        {"code": "382004", "msg": "已签到"},
    )
    monkeypatch.setattr(chaohua.requests, "Session", lambda: session)

    result = chaohua._run_weibo_chaohua_sign_sync(
        "SUB=valid; XSRF-TOKEN=token"
    )

    assert result == (True, "UID 12***90", 0, 1, 0, 1)
    sign_call = session.calls[2][1]
    assert sign_call["params"]["id"] == "100808example"


def test_nonzero_total_with_empty_list_is_rejected(monkeypatch) -> None:
    session = _FakeSession(
        {"ok": 1, "data": {"uid": "1234567890"}},
        {
            "ok": 1,
            "data": {"list": [], "total_number": 2, "max_page": 1},
        },
    )
    monkeypatch.setattr(chaohua.requests, "Session", lambda: session)

    result = chaohua._run_weibo_chaohua_sign_sync(
        "SUB=valid; XSRF-TOKEN=token"
    )

    assert result[0] is False
    assert "总数非零但列表为空" in result[1]


@pytest.mark.asyncio
async def test_push_body_never_contains_cookie_fragments(monkeypatch) -> None:
    class _FakePush:
        payload: dict[str, Any] | None = None

        async def send_news(self, **kwargs) -> None:
            self.payload = kwargs

    secret = "SUB=super-secret-value; XSRF-TOKEN=secret-token"
    config = chaohua.WeiboChaohuaCheckinConfig(
        enable=True,
        cookie=secret,
        cookies=[secret],
        time="22:45",
        push_channels=[],
    )
    push = _FakePush()
    monkeypatch.setattr(chaohua, "get_config", lambda: object())
    monkeypatch.setattr(chaohua, "is_in_quiet_hours", lambda _config: False)

    await chaohua._send_weibo_chaohua_push(
        push,
        title="微博超话签到完成",
        description="完成",
        success=True,
        cfg=config,
        detail="账号: UID 12***90",
    )

    assert push.payload is not None
    body = push.payload["description"]
    assert secret not in body
    assert "super-secret" not in body
    assert "secret-token" not in body
    assert "Cookie:" not in body
    assert "UID 12***90" in body
