"""SPA deep links and asset routing replace the former Jinja template tests."""

import httpx
import pytest

from src.web import app


@pytest.mark.asyncio
async def test_spa_deep_links_and_unknown_api(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text('<html lang="zh-CN"><div id="app"></div></html>')
    (tmp_path / "assets/app-hash.js").write_text('console.log("fixture")')
    monkeypatch.setattr(app, "FRONTEND_DIST_DIR", tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app.create_web_app()), base_url="http://test"
    ) as client:
        for path in ("/", "/login", "/tasks", "/data", "/logs", "/config", "/account"):
            response = await client.get(path)
            assert response.status_code == 200
            assert 'id="app"' in response.text
            assert response.headers["cache-control"] == "no-cache"
        assert (await client.get("/api/v1/nonexistent")).status_code == 404
        asset = await client.get("/assets/app-hash.js")
        assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
