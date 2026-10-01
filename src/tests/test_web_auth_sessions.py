from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.middleware.sessions import SessionMiddleware

from src.web import auth
from src.web.app import create_web_app
from src.web.routers import auth as auth_routes


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


def test_session_file_is_read_once_until_changed(monkeypatch):
    auth.register_session("cached")
    reads = []
    read_text = Path.read_text

    def counted_read(path, *args, **kwargs):
        if path == auth.WEB_SESSION_FILE:
            reads.append(path)
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted_read)
    for _ in range(5):
        assert auth.check_login("cached")
    assert len(reads) == 1
    auth.WEB_SESSION_FILE.write_text('{"sessions": {}}', encoding="utf-8")
    assert auth.check_login("cached") is False
    assert len(reads) == 2


def test_session_cache_rejects_deleted_or_corrupt_authoritative_file():
    auth.register_session("cached")
    assert auth.check_login("cached")
    auth.WEB_SESSION_FILE.write_text("invalid json", encoding="utf-8")
    assert auth.check_login("cached") is False
    auth.WEB_SESSION_FILE.unlink()
    assert auth.check_login("cached") is False


def test_cached_session_expires_without_file_modification(monkeypatch):
    now = 1000
    monkeypatch.setattr(auth, "_now_ts", lambda: now)
    expires = auth.register_session("cached")
    assert auth.check_login("cached")
    now = expires
    assert auth.check_login("cached") is False


def test_atomic_auth_write_failure_preserves_existing_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "auth.json")
    assert auth.save_auth({"username": "test", "password_hash": auth.hash_password("first")})
    before = auth.AUTH_FILE.read_bytes()

    def fail_replace(*args):
        raise OSError("replace failed")

    monkeypatch.setattr(auth.os, "replace", fail_replace)
    assert auth.save_auth({"password_hash": auth.hash_password("second")}) is False
    assert auth.AUTH_FILE.read_bytes() == before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["auth.json"]


@pytest.mark.parametrize("password_hash", [None, 123, [], {}, b"hash", "异常散列", "", "wrong"])
def test_invalid_password_hash_is_rejected_without_error(password_hash):
    assert auth.verify_password("sample-password", password_hash) is False


@pytest.mark.asyncio
async def test_invalid_stored_hash_preserves_login_and_password_error_contract(monkeypatch):
    monkeypatch.setattr(
        auth_routes, "load_auth", lambda: {"username": "test", "password_hash": None}
    )
    request = SimpleNamespace(session={"session_id": "test-session"})
    result = await auth_routes.login(request, username="test", password="sample-password")
    assert result.status_code == 401
    assert json.loads(result.body) == {"success": False, "message": "用户名或密码错误"}
    monkeypatch.setattr(auth_routes, "check_login", lambda session_id: True)
    result = await auth_routes.change_password(
        request,
        old_password="sample-password",
        new_password="new-password",
        confirm_password="new-password",
    )
    assert result.status_code == 400
    assert json.loads(result.body) == {"success": False, "message": "当前密码错误"}


def test_auth_cleanup_failure_does_not_override_save_result(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "auth.json")
    assert auth.save_auth({"password_hash": auth.hash_password("first")})
    before = auth.AUTH_FILE.read_bytes()
    original_unlink = Path.unlink

    def fail_replace(*args):
        raise OSError("replace failed")

    def fail_unlink(*args, **kwargs):
        raise PermissionError("cleanup failed")

    monkeypatch.setattr(auth.os, "replace", fail_replace)
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    try:
        assert auth.save_auth({"password_hash": auth.hash_password("second")}) is False
        assert auth.AUTH_FILE.read_bytes() == before
        assert "清理认证临时文件失败: PermissionError" in caplog.text
    finally:
        for path in tmp_path.iterdir():
            if path != auth.AUTH_FILE:
                original_unlink(path)
