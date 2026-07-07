from __future__ import annotations

import logging

import pytest


def _import_rainyun_checkin():
    pytest.importorskip("selenium")
    pytest.importorskip("ddddocr")
    from src.tasks import rainyun_checkin

    return rainyun_checkin


def _import_rainyun_session():
    pytest.importorskip("selenium")
    pytest.importorskip("ddddocr")
    from src.tasks.rainyun import config_adapter
    from src.tasks.rainyun.browser import session

    return session, config_adapter.RainyunRunConfig


@pytest.mark.asyncio
async def test_non_retryable_rainyun_error_stops_retries(monkeypatch):
    rainyun_checkin = _import_rainyun_checkin()
    attempts = 0

    async def fail_once(account, renew_threshold_days, *, chrome_overrides=None):
        nonlocal attempts
        attempts += 1
        return False, "用户 test 不可重试：未找到 Chrome/Chromium 浏览器"

    monkeypatch.setattr(rainyun_checkin, "_run_single_account_async", fail_once)

    account = rainyun_checkin.RainyunAccountConfig(username="test", password="secret")
    ok, msg = await rainyun_checkin._run_single_account_with_retry(account, 7)

    assert ok is False
    assert attempts == 1
    assert "已跳过后续重试" in msg


def test_rainyun_browser_session_requires_chrome(monkeypatch):
    session, config_cls = _import_rainyun_session()
    monkeypatch.setattr(session, "_default_chrome_binary", lambda: None)

    config = config_cls(
        rainyun_user="test",
        rainyun_pwd="secret",
        rainyun_api_key="",
        display_name="test",
        cookie_file="",
    )

    with pytest.raises(session.RainyunBrowserUnavailableError, match="未找到 Chrome/Chromium"):
        session.BrowserSession(config)._init_selenium()


def test_rainyun_browser_session_rejects_missing_configured_chrome():
    session, config_cls = _import_rainyun_session()
    config = config_cls(
        rainyun_user="test",
        rainyun_pwd="secret",
        rainyun_api_key="",
        display_name="test",
        cookie_file="",
        chrome_bin="/tmp/webmoniter-missing-chrome",
    )

    with pytest.raises(session.RainyunBrowserUnavailableError, match="路径不存在"):
        session.BrowserSession(config)._init_selenium()


def test_rainyun_snap_chromedriver_stub_is_ignored(tmp_path, monkeypatch):
    session, config_cls = _import_rainyun_session()
    fake_driver = tmp_path / "chromedriver"
    fake_driver.write_text(
        "#!/bin/sh\n"
        "echo \"Command '/usr/bin/chromedriver' requires the chromium snap to be installed.\" >&2\n"
        "exit 1\n"
    )
    fake_driver.chmod(0o755)

    config = config_cls(
        rainyun_user="test",
        rainyun_pwd="secret",
        rainyun_api_key="",
        display_name="test",
        cookie_file="",
        chromedriver_path=str(fake_driver),
    )

    monkeypatch.setattr(session.os.path, "exists", lambda path: path == str(fake_driver))

    assert session._get_chromedriver_path(config) is None


def test_rainyun_auto_snap_chromedriver_stub_is_debug_only(caplog, monkeypatch):
    session, config_cls = _import_rainyun_session()
    config = config_cls(
        rainyun_user="test",
        rainyun_pwd="secret",
        rainyun_api_key="",
        display_name="test",
        cookie_file="",
    )

    def exists(path):
        return path in {"/usr/bin/google-chrome", "/usr/bin/chromedriver"}

    def binary_version(path):
        if path == "/usr/bin/google-chrome":
            return True, "Google Chrome 150.0.7871.46"
        return False, "Command '/usr/bin/chromedriver' requires the chromium snap to be installed."

    monkeypatch.setattr(session.os.path, "exists", exists)
    monkeypatch.setattr(session, "_binary_version", binary_version)

    with caplog.at_level(logging.WARNING):
        result = session._get_chromedriver_path(config, "/usr/bin/google-chrome")

    assert result is None
    assert "忽略不可用 chromedriver" not in caplog.text


def test_rainyun_browser_session_falls_back_when_system_chromedriver_exits(monkeypatch):
    session, config_cls = _import_rainyun_session()
    config = config_cls(
        rainyun_user="test",
        rainyun_pwd="secret",
        rainyun_api_key="",
        display_name="test",
        cookie_file="",
    )
    expected_driver = object()
    calls = []

    class FakeService:
        def __init__(self, path):
            self.path = path

    def fake_chrome(*, service=None, options=None):
        calls.append(service)
        if len(calls) == 1:
            raise session.WebDriverException(
                "Message: Service /usr/bin/chromedriver unexpectedly exited. Status code was: 1"
            )
        return expected_driver

    monkeypatch.setattr(session, "_default_chrome_binary", lambda: "/usr/bin/google-chrome-stable")
    monkeypatch.setattr(
        session,
        "_get_chromedriver_path",
        lambda *args, **kwargs: "/usr/bin/chromedriver",
    )
    monkeypatch.setattr(
        session, "_resolve_chromedriver_via_manager", lambda chrome_bin: "/tmp/managed-driver"
    )
    monkeypatch.setattr(session, "Service", FakeService)
    monkeypatch.setattr(session.webdriver, "Chrome", fake_chrome)

    driver = session.BrowserSession(config)._init_selenium()

    assert driver is expected_driver
    assert len(calls) == 2
