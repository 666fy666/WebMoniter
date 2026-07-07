from __future__ import annotations

import json

import pytest
from starlette.middleware.sessions import SessionMiddleware

from src.web import auth
from src.web.app import create_web_app


@pytest.fixture(autouse=True)
def isolated_session_store(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "WEB_SESSION_FILE", tmp_path / "web_sessions.json")
    auth.active_sessions.clear()
    yield
    auth.active_sessions.clear()


def _read_sessions() -> dict:
    return json.loads(auth.WEB_SESSION_FILE.read_text(encoding="utf-8"))["sessions"]


def test_login_session_persists_across_process_memory_reset(monkeypatch):
    monkeypatch.setattr(auth, "_now_ts", lambda: 1_000)

    expires_at = auth.register_session("session-1")
    auth.active_sessions.clear()

    assert auth.check_login("session-1") is True
    assert "session-1" in auth.active_sessions
    assert _read_sessions()["session-1"]["expires_at"] == expires_at


def test_expired_session_is_rejected_and_purged(monkeypatch):
    monkeypatch.setattr(auth, "_now_ts", lambda: 2_000)
    auth.WEB_SESSION_FILE.write_text(
        json.dumps(
            {
                "version": 1,
                "sessions": {
                    "expired": {"expires_at": 1_999},
                    "valid": {"expires_at": 3_000},
                },
            }
        ),
        encoding="utf-8",
    )

    assert auth.check_login("expired") is False
    assert "expired" not in _read_sessions()
    assert auth.check_login("valid") is True


def test_session_renews_when_close_to_expiration(monkeypatch):
    now = 5_000
    monkeypatch.setattr(auth, "_now_ts", lambda: now)
    auth.WEB_SESSION_FILE.write_text(
        json.dumps(
            {
                "version": 1,
                "sessions": {
                    "session-1": {"expires_at": now + auth.WEB_SESSION_RENEW_WITHIN_SECONDS - 1},
                },
            }
        ),
        encoding="utf-8",
    )

    assert auth.check_login("session-1") is True
    assert _read_sessions()["session-1"]["expires_at"] == now + auth.WEB_SESSION_MAX_AGE_SECONDS


def test_replace_sessions_keeps_only_current_session(monkeypatch):
    monkeypatch.setattr(auth, "_now_ts", lambda: 10_000)
    auth.register_session("old-session")

    auth.replace_sessions_with("current-session")

    sessions = _read_sessions()
    assert set(sessions) == {"current-session"}
    assert auth.check_login("old-session") is False
    assert auth.check_login("current-session") is True


def test_session_cookie_lasts_one_year():
    app = create_web_app()
    middleware = next(item for item in app.user_middleware if item.cls is SessionMiddleware)

    assert middleware.kwargs["max_age"] == auth.WEB_SESSION_MAX_AGE_SECONDS
