"""Small regression tests for Web assistant helpers and action validation."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from src.web.assistant_support import (
    parse_executable_intent_and_reply,
    parse_suggested_action_from_reply,
)
from src.web.routers import assistant as assistant_router


def test_parse_suggested_action_from_config_patch_reply():
    reply = """可以修改配置。

```json
{"type":"config_patch","platform_key":"huya","list_key":"rooms","operation":"add","value":"123"}
```
"""

    cleaned, action = parse_suggested_action_from_reply(reply)

    assert "```json" not in cleaned
    assert action == {
        "type": "confirm_execute",
        "action": "config_patch",
        "platform_key": "huya",
        "list_key": "rooms",
        "operation": "add",
        "value": "123",
        "title": "添加配置项",
        "description": "将从 huya 的 rooms 中添加「123」",
    }


@pytest.mark.asyncio
async def test_parse_toggle_monitor_intent_to_confirm_action():
    reply, action = await parse_executable_intent_and_reply("关闭虎牙监控")

    assert reply == "好的，关闭虎牙监控。请确认执行："
    assert action is not None
    assert action["type"] == "confirm_execute"
    assert action["action"] == "toggle_monitor"
    assert action["platform_key"] == "huya"
    assert action["enable"] is False


def test_apply_action_rejects_unknown_config_patch_platform(monkeypatch):
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(assistant_router.router)
    client = TestClient(app)

    monkeypatch.setattr(assistant_router, "assistant_require_auth", lambda request: None)
    monkeypatch.setattr(assistant_router, "check_login", lambda session_id: True)

    response = client.post(
        "/api/assistant/apply-action",
        json={
            "action": "config_patch",
            "platform_key": "unknown",
            "list_key": "rooms",
            "operation": "add",
            "value": "123",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "不支持的平台: unknown"
