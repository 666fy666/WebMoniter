"""预热生命周期、缓存边界与响应头的回归验证。"""

import asyncio
import gzip
from types import SimpleNamespace

import pytest

from src.core import http
from src.web import warmup
from src.web.app import create_web_app
from src.web.data_support import _cached_weibo_order, _weibo_page_ids
from src.web.middleware import WebPerformanceMiddleware
from src.web.static_files import VersionedStaticFiles


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
    messages = await _request(create_web_app(), "/api/check-auth")
    assert messages[0]["status"] == 401
    headers = dict(messages[0]["headers"])
    assert headers[b"cache-control"] == b"no-store"
    assert headers[b"server-timing"].startswith(b"app;dur=")
    assert messages[1]["body"] == b'{"authenticated":false}'


@pytest.mark.asyncio
async def test_compressed_static_file_and_versioned_cache_preserve_content():
    messages = await _request(
        create_web_app(), "/static/js/common.js", b"v=3", [(b"accept-encoding", b"gzip")]
    )
    headers = dict(messages[0]["headers"])
    assert headers[b"cache-control"] == b"public, max-age=31536000, immutable"
    assert headers[b"content-encoding"] == b"gzip"
    content = gzip.decompress(b"".join(message.get("body", b"") for message in messages[1:]))
    assert b"async function fetchJSON" in content


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
async def test_warmup_failure_isolated_and_later_stages_run(monkeypatch):
    stages = []

    def fail_templates():
        raise RuntimeError("template failed")

    async def dates():
        stages.append("dates")

    monkeypatch.setattr(warmup, "_warm_templates", fail_templates)
    monkeypatch.setattr(warmup, "get_certifi_ssl_context", lambda: stages.append("tls"))
    monkeypatch.setattr(warmup, "_warm_weibo_dates", dates)
    await warmup.warmup_web_resources()
    assert stages == ["tls", "dates"]


@pytest.mark.asyncio
async def test_warmup_can_be_cancelled_without_leaving_background_task(monkeypatch):
    started = asyncio.Event()

    async def blocked_dates():
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(warmup, "_warm_templates", lambda: None)
    monkeypatch.setattr(warmup, "get_certifi_ssl_context", lambda: None)
    monkeypatch.setattr(warmup, "_warm_weibo_dates", blocked_dates)
    task = asyncio.create_task(warmup.warmup_web_resources())
    await asyncio.wait_for(started.wait(), timeout=1)
    await warmup.stop_web_warmup(task)
    assert task.done()
    await warmup.stop_web_warmup(None)


@pytest.mark.asyncio
async def test_warmup_stage_has_deadline(monkeypatch, caplog):
    async def blocked_dates():
        await asyncio.Event().wait()

    monkeypatch.setattr(warmup, "_warm_templates", lambda: None)
    monkeypatch.setattr(warmup, "get_certifi_ssl_context", lambda: None)
    monkeypatch.setattr(warmup, "_warm_weibo_dates", blocked_dates)
    monkeypatch.setattr(warmup, "WARMUP_STAGE_TIMEOUT_SECONDS", 0.01)
    await asyncio.wait_for(warmup.warmup_web_resources(), timeout=1)
    assert "stage=weibo_dates error=TimeoutError" in caplog.text


def test_tls_context_reuses_verified_ca_configuration():
    context = http.get_certifi_ssl_context()
    assert http.get_certifi_ssl_context() is context
    assert context.check_hostname is True
    assert context.verify_mode == http.ssl.CERT_REQUIRED


def test_weibo_sort_cache_is_bounded_and_skips_oversized_indices():
    _cached_weibo_order.cache_clear()
    for uid in ("first", "second", "third"):
        assert _weibo_page_ids([(uid, "正文\n\n2026-01-01 10:00:00")], 0, 1) == [uid]
    assert _cached_weibo_order.cache_info().currsize == 2
    misses = _cached_weibo_order.cache_info().misses
    _weibo_page_ids([(str(i), "unknown") for i in range(4097)], 0, 25)
    _weibo_page_ids([("x" * 256, "unknown")], 0, 1)
    assert _cached_weibo_order.cache_info().misses == misses
    _cached_weibo_order.cache_clear()
