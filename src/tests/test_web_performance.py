"""预热生命周期、缓存边界与响应头的回归验证。"""

import asyncio
import gzip
import json
from types import SimpleNamespace

import pytest

from src.core import http
from src.web import warmup
from src.web.app import create_web_app
from src.web.middleware import WebPerformanceMiddleware
from src.web.static_files import STATIC_ASSET_VERSION, VersionedStaticFiles


async def _request(app, path, query=b"", headers=()):
    messages = []
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "root_path": "",
        "scheme": "http",
        "query_string": query,
        "headers": list(headers),
        "http_version": "1.1",
        "server": ("test", 80),
        "client": ("test", 1),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    return messages


@pytest.mark.asyncio
async def test_api_no_store_and_timing_preserve_auth_contract():
    messages = await _request(create_web_app(), "/api/v1/tasks")
    assert messages[0]["status"] == 401
    headers = dict(messages[0]["headers"])
    assert headers[b"cache-control"] == b"no-store"
    assert headers[b"server-timing"].startswith(b"app;dur=")
    assert "detail" in json.loads(messages[1]["body"])


@pytest.mark.asyncio
async def test_compressed_static_file_and_versioned_cache_preserve_content():
    messages = await _request(
        create_web_app(),
        "/static/icons.svg",
        f"v={STATIC_ASSET_VERSION}".encode(),
        [(b"accept-encoding", b"gzip")],
    )
    headers = dict(messages[0]["headers"])
    assert headers[b"cache-control"] == b"public, max-age=31536000, immutable"
    assert headers[b"content-encoding"] == b"gzip"
    content = gzip.decompress(b"".join(message.get("body", b"") for message in messages[1:]))
    assert b"<symbol" in content


@pytest.mark.asyncio
async def test_missing_media_does_not_get_immutable_cache_headers():
    messages = await _request(create_web_app(), "/weibo_img/missing-image.jpg")
    assert messages[0]["status"] == 404
    assert b"cache-control" not in dict(messages[0]["headers"])


@pytest.mark.asyncio
async def test_binary_images_skip_redundant_compression():
    messages = await _request(
        create_web_app(),
        "/static/images/liquid-landscape.webp",
        headers=[(b"accept-encoding", b"gzip")],
    )
    assert messages[0]["status"] == 200
    headers = dict(messages[0]["headers"])
    assert b"content-encoding" not in headers
    assert messages[1]["body"].startswith(b"RIFF")


def test_versionless_or_wrong_version_assets_are_revalidated():
    handler = VersionedStaticFiles(directory=".", asset_version="3")
    for query in (b"", b"v=2", b"v=3&v=2"):
        assert handler._cache_control_for_scope({"query_string": query}) == "no-cache"


@pytest.mark.asyncio
async def test_slow_request_logs_route_template_without_query_or_item_id(caplog):
    async def app(scope, receive, send):
        scope["route"] = SimpleNamespace(path="/api/data/{platform}/{item_id}")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    await _request(
        WebPerformanceMiddleware(app, slow_request_seconds=0),
        "/api/data/weibo/private-user",
        b"token=private-token",
    )
    assert "route=/api/data/{platform}/{item_id}" in caplog.text
    assert "private-user" not in caplog.text
    assert "private-token" not in caplog.text


@pytest.mark.asyncio
async def test_tls_warmup_failure_is_isolated(monkeypatch, caplog):
    def fail_tls():
        raise RuntimeError("test")

    monkeypatch.setattr(warmup, "get_certifi_ssl_context", fail_tls)
    await warmup.warmup_web_resources()
    assert "stage=tls error=RuntimeError" in caplog.text


@pytest.mark.asyncio
async def test_warmup_can_be_cancelled():
    task = asyncio.create_task(asyncio.sleep(100))
    await warmup.stop_web_warmup(task)
    assert task.done()
    await warmup.stop_web_warmup(None)


def test_tls_context_reuses_verified_ca_configuration():
    context = http.get_certifi_ssl_context()
    assert http.get_certifi_ssl_context() is context
    assert context.check_hostname is True
    assert context.verify_mode == http.ssl.CERT_REQUIRED
