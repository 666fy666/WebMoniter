import json

import httpx
import pytest

from src.web import auth
from src.web.app import create_web_app
from src.web.routers import v1


@pytest.mark.asyncio
async def test_session_csrf_login_rotation_and_validation_redaction(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "auth.json")
    monkeypatch.setattr(auth, "WEB_SESSION_FILE", tmp_path / "sessions.json")
    monkeypatch.setenv("WEBMONITER_ADMIN_PASSWORD", "test-only-initial-password")
    v1._attempts.clear()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_web_app()), base_url="http://test"
    ) as client:
        assert (await client.get("/api/v1/tasks")).status_code == 401
        before = (await client.get("/api/v1/session")).json()
        assert not before["authenticated"]
        assert (
            await client.post(
                "/api/v1/login",
                json={"username": "admin", "password": "test-only-initial-password"},
            )
        ).status_code == 403
        headers = {"X-CSRF-Token": before["csrf_token"]}
        invalid = await client.post(
            "/api/v1/login", headers=headers, json={"username": "", "password": "sensitive-fixture"}
        )
        assert invalid.status_code == 422
        assert "sensitive-fixture" not in invalid.text
        response = await client.post(
            "/api/v1/login",
            headers=headers,
            json={"username": "admin", "password": "test-only-initial-password"},
        )
        assert response.status_code == 200
        token = response.json()["csrf_token"]
        assert token != before["csrf_token"]
        credentials = json.loads(auth.AUTH_FILE.read_text())
        assert credentials["password_hash"].startswith("$argon2id$")
        changed = await client.post(
            "/api/v1/password",
            headers={"X-CSRF-Token": token},
            json={"old_password": "test-only-initial-password", "new_password": "123"},
        )
        assert changed.status_code == 200
        assert auth.verify_password("123", auth.load_auth()["password_hash"])
        assert (await client.post("/api/v1/logout", headers=headers)).status_code == 403
        assert (
            await client.post(
                "/api/v1/logout",
                headers={"X-CSRF-Token": token, "Origin": "https://untrusted.example"},
            )
        ).status_code == 403
        assert (
            await client.post("/api/v1/logout", headers={"X-CSRF-Token": token})
        ).status_code == 200
        assert not (await client.get("/api/v1/session")).json()["authenticated"]


@pytest.mark.asyncio
async def test_login_rate_limit_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "auth.json")
    monkeypatch.setenv("WEBMONITER_ADMIN_PASSWORD", "test-only-initial-password")
    v1._attempts.clear()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_web_app()), base_url="http://test"
    ) as client:
        token = (await client.get("/api/v1/session")).json()["csrf_token"]
        for _ in range(5):
            response = await client.post(
                "/api/v1/login",
                headers={"X-CSRF-Token": token},
                json={"username": "admin", "password": "wrong"},
            )
            assert response.status_code == 401
        response = await client.post(
            "/api/v1/login",
            headers={"X-CSRF-Token": token},
            json={"username": "admin", "password": "wrong"},
        )
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "300"
    v1._attempts.clear()


@pytest.mark.parametrize("initial_password", [None, "", "123", "custom-password"])
def test_initial_password_defaults_and_optional_override(tmp_path, monkeypatch, initial_password):
    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "auth.json")
    monkeypatch.delenv("WEBMONITER_ADMIN_USERNAME", raising=False)
    if initial_password is None:
        monkeypatch.delenv("WEBMONITER_ADMIN_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("WEBMONITER_ADMIN_PASSWORD", initial_password)
    credentials = auth.load_auth()
    assert credentials["username"] == "admin"
    assert auth.verify_password(initial_password or "123", credentials["password_hash"])
    monkeypatch.setenv("WEBMONITER_ADMIN_PASSWORD", "different-password")
    assert auth.load_auth() == credentials


def test_corrupt_auth_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "auth.json")
    monkeypatch.delenv("WEBMONITER_ADMIN_PASSWORD", raising=False)
    auth.AUTH_FILE.write_text("{}")
    with pytest.raises(RuntimeError):
        auth.load_auth()
    auth.AUTH_FILE.write_text("invalid")
    monkeypatch.setenv("WEBMONITER_ADMIN_PASSWORD", "test-only-initial-password")
    with pytest.raises(RuntimeError):
        auth.load_auth()
