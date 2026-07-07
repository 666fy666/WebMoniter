from __future__ import annotations

import base64
import logging

import pytest

from src.tasks import ikuuu_checkin


class _NoNetworkSession:
    def get(self, *args, **kwargs):
        raise AssertionError("session.get should not be called for an unresolvable host")


@pytest.mark.asyncio
async def test_fetch_discovery_page_skips_unresolvable_host(monkeypatch):
    async def unresolvable(host: str, port: int) -> bool:
        return False

    monkeypatch.setattr(ikuuu_checkin, "_ikuuu_host_resolves", unresolvable)

    result = await ikuuu_checkin._fetch_discovery_page(
        _NoNetworkSession(),
        "https://ikuuu.invalid",
    )

    assert result is None


@pytest.mark.asyncio
async def test_probe_domain_skips_unresolvable_host(monkeypatch):
    async def unresolvable(host: str, port: int) -> bool:
        return False

    monkeypatch.setattr(ikuuu_checkin, "_ikuuu_host_resolves", unresolvable)

    result = await ikuuu_checkin._probe_domain(_NoNetworkSession(), "ikuuu.invalid")

    assert result is None


@pytest.mark.asyncio
async def test_probe_recent_domains_returns_primary_without_fallback(monkeypatch):
    async def probe_domain(session, domain):
        assert domain == "ikuuu.win"
        return ikuuu_checkin._DomainProbeResult(domain, 100, 123, "login-form")

    async def unexpected_probe_domains(session, candidates):
        raise AssertionError("fallback candidates should not be probed when primary works")

    monkeypatch.setattr(ikuuu_checkin, "_probe_domain", probe_domain)
    monkeypatch.setattr(ikuuu_checkin, "_probe_domains", unexpected_probe_domains)

    result = await ikuuu_checkin._probe_recent_domains(object())

    assert result == "ikuuu.win"


@pytest.mark.asyncio
async def test_extract_domain_returns_recent_domain_before_fetching_notice(monkeypatch):
    async def recent_domain(session):
        return "ikuuu.win"

    async def unexpected_fetch(session, url):
        raise AssertionError("notice pages should not be fetched when a recent domain works")

    monkeypatch.setattr(ikuuu_checkin, "_load_cached_ikuuu_domain", lambda: None)
    monkeypatch.setattr(ikuuu_checkin, "_probe_recent_domains", recent_domain)
    monkeypatch.setattr(ikuuu_checkin, "_fetch_discovery_page", unexpected_fetch)

    result = await ikuuu_checkin._extract_ikuuu_domain()

    assert result == "ikuuu.win"


@pytest.mark.asyncio
async def test_extract_domain_uses_verified_cache_before_recent_probe(monkeypatch):
    async def probe_domain(session, domain):
        assert domain == "ikuuu.win"
        return ikuuu_checkin._DomainProbeResult(domain, 100, 88, "login-form")

    async def unexpected_recent(session):
        raise AssertionError("recent domains should not be probed when cache works")

    monkeypatch.setattr(ikuuu_checkin, "_load_cached_ikuuu_domain", lambda: "ikuuu.win")
    monkeypatch.setattr(ikuuu_checkin, "_probe_domain", probe_domain)
    monkeypatch.setattr(ikuuu_checkin, "_probe_recent_domains", unexpected_recent)
    monkeypatch.setattr(ikuuu_checkin, "_save_cached_ikuuu_domain", lambda domain, source: None)

    result = await ikuuu_checkin._extract_ikuuu_domain()

    assert result == "ikuuu.win"


@pytest.mark.asyncio
async def test_extract_domain_retry_intermediate_failures_are_not_warnings(caplog, monkeypatch):
    calls = 0

    async def discover():
        nonlocal calls
        calls += 1
        return "ikuuu.win" if calls == 2 else None

    async def sleep(seconds):
        return None

    monkeypatch.setattr(ikuuu_checkin, "_extract_ikuuu_domain", discover)
    monkeypatch.setattr(ikuuu_checkin.asyncio, "sleep", sleep)

    with caplog.at_level(logging.WARNING):
        result = await ikuuu_checkin._extract_ikuuu_domain_with_retry()

    assert result == "ikuuu.win"
    assert calls == 2
    assert "域名发现失败" not in caplog.text


def test_origin_body_domain_candidates_are_decoded():
    body = (
        '<script>arr = ["ikuuu.co", "ikuuu.win"];</script>'
        '<input id="email" name="email"><input id="password" name="password">'
    )
    encoded = base64.b64encode(body.encode()).decode()
    candidates = {}

    ikuuu_checkin._extract_domain_candidates_from_text(
        f'<script>var originBody = "{encoded}";</script>',
        candidates,
        source="origin-body",
        base_score=60,
    )

    assert candidates["ikuuu.co"] >= 1
    assert candidates["ikuuu.win"] >= 1


def test_auto_snap_chromedriver_stub_is_debug_only(caplog, monkeypatch):
    def exists(path):
        return path in {"/usr/bin/google-chrome", "/usr/bin/chromedriver"}

    def binary_version(path):
        if path == "/usr/bin/google-chrome":
            return True, "Google Chrome 150.0.7871.46"
        return False, "Command '/usr/bin/chromedriver' requires the chromium snap to be installed."

    monkeypatch.setattr(ikuuu_checkin.os.path, "exists", exists)
    monkeypatch.setattr(ikuuu_checkin.shutil, "which", lambda name: "/usr/bin/chromedriver")
    monkeypatch.setattr(ikuuu_checkin, "_binary_version", binary_version)

    with caplog.at_level(logging.WARNING):
        result = ikuuu_checkin._default_chromedriver_path("/usr/bin/google-chrome")

    assert result is None
    assert "忽略不可用 chromedriver" not in caplog.text


def test_ikuuu_webdriver_uses_selenium_manager_before_auto_candidates(monkeypatch):
    expected_driver = object()
    used_services = []

    class FakeService:
        def __init__(self, path):
            self.path = path

    class FakeWebDriver:
        pass

    def fake_chrome(*, service=None, options=None):
        used_services.append(service)
        return expected_driver

    FakeWebDriver.Chrome = staticmethod(fake_chrome)

    def default_driver_path(chrome_bin, *, include_auto_candidates=True):
        if include_auto_candidates:
            raise AssertionError("auto chromedriver candidates should only be a final fallback")
        return None

    monkeypatch.setattr(ikuuu_checkin, "_default_chromedriver_path", default_driver_path)
    monkeypatch.setattr(
        ikuuu_checkin,
        "_resolve_chromedriver_via_manager",
        lambda chrome_bin: "/tmp/managed-driver",
    )

    driver = ikuuu_checkin._create_ikuuu_webdriver(
        FakeWebDriver,
        FakeService,
        object(),
        "/usr/bin/google-chrome",
    )

    assert driver is expected_driver
    assert [service.path for service in used_services] == ["/tmp/managed-driver"]
