from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

from src.jobs.task_outcome import TASK_FAILED, TASK_SUCCESS
from src.settings.config import AppConfig
from src.settings.config_writer import ConfigUpdateResult
from src.tasks import weibo_cookie_refresh as refresh


class _FakeDriver:
    def __init__(self) -> None:
        self.cookies: list[dict] = []
        self.current_url = "about:blank"
        self.quit_called = False
        self.timeout = 0

    def set_page_load_timeout(self, timeout: int) -> None:
        self.timeout = timeout

    def get(self, url: str) -> None:
        self.current_url = url

    def delete_all_cookies(self) -> None:
        self.cookies.clear()

    def add_cookie(self, cookie: dict) -> None:
        self.cookies.append(dict(cookie))

    def get_cookie(self, name: str):
        return next((cookie for cookie in self.cookies if cookie["name"] == name), None)

    def get_cookies(self) -> list[dict]:
        return list(self.cookies)

    def execute_script(self, script: str) -> str:
        return "complete"

    def quit(self) -> None:
        self.quit_called = True


class _RotatingSubDriver(_FakeDriver):
    def __init__(self) -> None:
        super().__init__()
        self.get_calls = 0

    def get(self, url: str) -> None:
        super().get(url)
        self.get_calls += 1
        if self.get_calls != 2:
            return
        for cookie in self.cookies:
            if cookie["name"] == "SUB":
                cookie["value"] = "browser-sub"
            elif cookie["name"] == "SUBP":
                cookie["value"] = "browser-subp"


def test_parse_cookie_preserves_equals_and_skips_invalid_parts() -> None:
    parsed = refresh._parse_cookie_string(" SUB=abc==; invalid; XSRF-TOKEN=token%3D; empty= ")

    assert parsed == [("SUB", "abc=="), ("XSRF-TOKEN", "token%3D")]


def test_merge_cookie_preserves_original_fields_order_and_equals() -> None:
    result = refresh._merge_cookie_string(
        "LEGACY=keep; SUB=old==; WBPSESS=old-session",
        [
            {"name": "SUB", "value": "old", "domain": ".weibo.com"},
            {"name": "OTHER", "value": "ignored", "domain": ".example.com"},
            {"name": "SUB", "value": "new==", "domain": "weibo.com"},
            {"name": "XSRF-TOKEN", "value": "xsrf", "domain": ".weibo.com"},
        ]
    )

    assert result == (
        "LEGACY=keep; SUB=new==; WBPSESS=old-session; XSRF-TOKEN=xsrf"
    )


def test_renew_cookie_uses_isolated_driver_and_always_quits(monkeypatch) -> None:
    driver = _FakeDriver()
    validated: list[str] = []
    monkeypatch.setattr(refresh, "_create_webdriver", lambda: driver)
    monkeypatch.setattr(refresh.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        refresh,
        "_validate_cookie_sync",
        lambda cookie, requirements, uid: validated.append(cookie),
    )

    result = refresh._renew_cookie_sync(
        "SUB=value==; XSRF-TOKEN=xsrf",
        refresh.CookieValidationRequirements(validate_weibo=True, validate_chaohua=True),
        "123456",
    )

    assert result.success is True
    assert result.cookie_string == "SUB=value==; XSRF-TOKEN=xsrf"
    assert validated == [result.cookie_string, result.cookie_string]
    assert driver.timeout == refresh._PAGE_LOAD_TIMEOUT_SECONDS
    assert driver.quit_called is True


def test_renew_cookie_sanitizes_unexpected_browser_error(monkeypatch) -> None:
    secret = "SUB=do-not-log"

    def fail():
        raise RuntimeError(f"browser failed with {secret}")

    monkeypatch.setattr(refresh, "_validate_cookie_sync", lambda *args: None)
    monkeypatch.setattr(refresh, "_create_webdriver", fail)

    result = refresh._renew_cookie_sync(f"SUB={secret}")

    assert result.success is False
    assert secret not in result.error
    assert result.error == "刷新过程中发生异常（RuntimeError）"


def test_renew_cookie_rejects_injected_sub_when_server_rejects_candidate(monkeypatch) -> None:
    driver = _RotatingSubDriver()
    secret = "do-not-log"
    validation_results = iter(
        [
            None,
            "微博监控接口拒绝当前登录态（HTTP 403）",
            "微博监控接口拒绝当前登录态（HTTP 403）",
        ]
    )
    monkeypatch.setattr(refresh, "_create_webdriver", lambda: driver)
    monkeypatch.setattr(refresh.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        refresh,
        "_validate_cookie_sync",
        lambda *args: next(validation_results),
    )

    result = refresh._renew_cookie_sync(f"SUB={secret}; SUBP=original-subp")

    assert result.success is False
    assert "HTTP 403" in result.error
    assert secret not in result.error
    assert driver.quit_called is True


def test_renew_cookie_preserves_original_sub_when_fallback_is_valid(monkeypatch) -> None:
    driver = _RotatingSubDriver()
    validation_results = iter(
        [None, "微博监控接口拒绝当前登录态（HTTP 403）", None]
    )
    monkeypatch.setattr(refresh, "_create_webdriver", lambda: driver)
    monkeypatch.setattr(refresh.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        refresh,
        "_validate_cookie_sync",
        lambda *args: next(validation_results),
    )

    result = refresh._renew_cookie_sync("SUB=original-sub; SUBP=original-subp")

    assert result.success is True
    assert result.cookie_string == "SUB=original-sub; SUBP=browser-subp"
    assert driver.quit_called is True


def test_renew_cookie_does_not_start_browser_when_original_is_invalid(monkeypatch) -> None:
    monkeypatch.setattr(
        refresh,
        "_validate_cookie_sync",
        lambda *args: "微博监控接口拒绝当前登录态（HTTP 403）",
    )
    monkeypatch.setattr(
        refresh,
        "_create_webdriver",
        lambda: pytest.fail("失效 Cookie 不应启动浏览器"),
    )

    result = refresh._renew_cookie_sync("SUB=expired")

    assert result.success is False
    assert "请重新获取 Cookie" in result.error


class _FakeValidationResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        return self._payload


def test_validate_cookie_checks_monitor_and_chaohua_with_shared_user_agent(
    monkeypatch,
) -> None:
    calls: list[dict] = []

    class FakeSession:
        def __init__(self) -> None:
            self.trust_env = True

        def get(self, url, **kwargs):
            calls.append({"url": url, "trust_env": self.trust_env, **kwargs})
            if url == refresh.WEIBO_SPA_CONFIG_URL:
                return _FakeValidationResponse(200, {"ok": 1, "data": {"uid": "9876543210"}})
            if url == refresh.WEIBO_CHAOHUA_LIST_URL:
                return _FakeValidationResponse(
                    200,
                    {"ok": 1, "data": {"list": [], "total_number": 0, "max_page": 1}},
                )
            return _FakeValidationResponse(200, {"ok": 1})

        def close(self) -> None:
            pass

    monkeypatch.setattr(refresh.requests, "Session", FakeSession)

    error = refresh._validate_cookie_sync(
        "SUB=valid; XSRF-TOKEN=token",
        refresh.CookieValidationRequirements(validate_weibo=True, validate_chaohua=True),
        "123456",
    )

    assert error is None
    assert [call["url"] for call in calls] == [
        refresh.WEIBO_SPA_CONFIG_URL,
        refresh.WEIBO_MONITOR_URL,
        refresh.WEIBO_CHAOHUA_LIST_URL,
    ]
    assert all(
        call["headers"]["User-Agent"] == refresh.WEIBO_DESKTOP_USER_AGENT for call in calls
    )
    assert [call["trust_env"] for call in calls] == [True, False, True]
    assert "X-XSRF-TOKEN" not in calls[0]["headers"]
    assert "X-XSRF-TOKEN" not in calls[1]["headers"]
    assert calls[2]["headers"]["X-XSRF-TOKEN"] == "token"
    assert calls[2]["params"]["uid"] == "9876543210"
    assert calls[2]["headers"]["Referer"].endswith("/9876543210/231093_-_chaohua")


def test_validate_chaohua_rejects_anonymous_ok_response(monkeypatch) -> None:
    calls: list[str] = []

    class FakeSession:
        trust_env = True

        def get(self, url, **kwargs):
            calls.append(url)
            return _FakeValidationResponse(200, {"ok": 1, "data": {"isNormal": False}})

        def close(self) -> None:
            pass

    monkeypatch.setattr(refresh.requests, "Session", FakeSession)

    error = refresh._validate_cookie_sync(
        "SUB=anonymous; XSRF-TOKEN=token",
        refresh.CookieValidationRequirements(validate_chaohua=True),
        "",
    )

    assert error == "微博登录接口未识别到完整登录账号，Cookie 可能仅为匿名会话"
    assert calls == [refresh.WEIBO_SPA_CONFIG_URL]


def test_validate_cookie_rejects_403_without_exposing_cookie(monkeypatch) -> None:
    secret = "do-not-expose"

    class FakeSession:
        trust_env = True

        def get(self, *args, **kwargs):
            return _FakeValidationResponse(403, {"ok": 0})

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        refresh.requests,
        "Session",
        FakeSession,
    )

    error = refresh._validate_cookie_sync(
        f"SUB={secret}",
        refresh.CookieValidationRequirements(validate_weibo=True),
        "123456",
    )

    assert error == "微博监控接口拒绝当前登录态（HTTP 403）"
    assert secret not in error


def test_validate_chaohua_requires_xsrf_without_sending_request(monkeypatch) -> None:
    monkeypatch.setattr(
        refresh.requests,
        "Session",
        lambda: pytest.fail("缺少 XSRF 时不应发送请求"),
    )

    error = refresh._validate_cookie_sync(
        "SUB=valid",
        refresh.CookieValidationRequirements(validate_chaohua=True),
        "",
    )

    assert error == "Cookie 缺少 XSRF-TOKEN，无法用于微博超话"


def test_build_updates_supports_duplicates_multi_cookie_and_partial_failure() -> None:
    shared = "SUB=shared; XSRF-TOKEN=old"
    failed = "SUB=failed; XSRF-TOKEN=old"
    refreshed = "SUB=shared-new; XSRF-TOKEN=new"
    snapshots = [
        refresh.CookieFieldSnapshot(("weibo", "cookie"), shared, False),
        refresh.CookieFieldSnapshot(("weibo_chaohua", "cookie"), shared, True),
        refresh.CookieFieldSnapshot(("weibo_chaohua", "cookies"), [shared, failed], True),
    ]
    results = {
        shared: refresh.CookieRenewalResult(True, refreshed),
        failed: refresh.CookieRenewalResult(False, error="登录状态已失效"),
    }

    updates, renewed, failures = refresh._build_config_updates(snapshots, results)

    assert renewed == 3
    assert [update.path for update in updates] == [
        ("weibo", "cookie"),
        ("weibo_chaohua", "cookie"),
        ("weibo_chaohua", "cookies"),
    ]
    assert updates[-1].value == [refreshed, failed]
    assert failures == ["weibo_chaohua.cookies[2]：登录状态已失效"]
    assert refresh._unique_cookie_values(snapshots) == [shared, failed]
    assert refresh._cookie_requirements(snapshots) == {
        shared: refresh.CookieValidationRequirements(
            validate_weibo=True,
            validate_chaohua=True,
        ),
        failed: refresh.CookieValidationRequirements(validate_chaohua=True),
    }


@pytest.mark.asyncio
async def test_run_refresh_deduplicates_shared_cookie_and_reports_success(monkeypatch) -> None:
    original = "SUB=shared; XSRF-TOKEN=old"
    renewed = "SUB=shared-new; XSRF-TOKEN=new"
    config = AppConfig(
        weibo_cookie=original,
        weibo_chaohua_cookie=original,
        weibo_uids="123456, 789012",
        weibo_push_channels=["ops"],
    )
    seen: dict = {}

    async def fake_renew(values: list[str], requirements, validation_uid: str):
        seen["values"] = values
        seen["requirements"] = requirements
        seen["validation_uid"] = validation_uid
        return {original: refresh.CookieRenewalResult(True, renewed)}

    async def fake_apply(path, updates):
        seen["updates"] = updates
        return ConfigUpdateResult(
            applied_paths=("weibo.cookie", "weibo_chaohua.cookie"),
            changed_paths=("weibo.cookie", "weibo_chaohua.cookie"),
            conflict_paths=(),
            wrote_file=True,
        )

    async def fake_send(config_arg, summary):
        seen["summary"] = summary

    monkeypatch.setattr(refresh, "get_config", lambda reload=False: config)
    monkeypatch.setattr(refresh, "_renew_unique_cookies", fake_renew)
    monkeypatch.setattr(refresh, "apply_config_updates", fake_apply)
    monkeypatch.setattr(refresh, "_send_summary", fake_send)

    outcome = await refresh.run_weibo_cookie_refresh_once()

    assert outcome is TASK_SUCCESS
    assert seen["values"] == [original]
    assert seen["requirements"][original] == refresh.CookieValidationRequirements(
        validate_weibo=True,
        validate_chaohua=True,
    )
    assert seen["validation_uid"] == "123456"
    assert len(seen["updates"]) == 2
    assert seen["summary"].success is True
    assert seen["summary"].renewed_targets == 2


@pytest.mark.asyncio
async def test_run_refresh_writes_successes_but_partial_failure_is_failed(monkeypatch) -> None:
    good = "SUB=good"
    bad = "SUB=bad; XSRF-TOKEN=old"
    config = AppConfig(weibo_cookie=good, weibo_chaohua_cookie=bad)
    seen: dict = {}

    async def fake_renew(values: list[str], requirements, validation_uid: str):
        return {
            good: refresh.CookieRenewalResult(True, "SUB=good-new"),
            bad: refresh.CookieRenewalResult(False, error="登录状态已失效"),
        }

    async def fake_apply(path, updates):
        seen["updates"] = updates
        return ConfigUpdateResult(
            applied_paths=("weibo.cookie",),
            changed_paths=("weibo.cookie",),
            conflict_paths=(),
            wrote_file=True,
        )

    async def fake_send(config_arg, summary):
        seen["summary"] = summary

    monkeypatch.setattr(refresh, "get_config", lambda reload=False: config)
    monkeypatch.setattr(refresh, "_renew_unique_cookies", fake_renew)
    monkeypatch.setattr(refresh, "apply_config_updates", fake_apply)
    monkeypatch.setattr(refresh, "_send_summary", fake_send)

    outcome = await refresh.run_weibo_cookie_refresh_once()

    assert outcome is TASK_FAILED
    assert [update.path for update in seen["updates"]] == [("weibo", "cookie")]
    assert seen["summary"].renewed_targets == 1
    assert seen["summary"].failures == ("weibo_chaohua.cookie：登录状态已失效",)


@pytest.mark.asyncio
async def test_send_summary_reuses_weibo_channels(monkeypatch) -> None:
    config = AppConfig(weibo_push_channels=["ops"])
    summary = refresh.RefreshSummary(1, 1, 1, (), (), (), False)
    calls: dict = {}
    push = object()

    @asynccontextmanager
    async def fake_context(*args, **kwargs) -> AsyncIterator[object]:
        calls["context_kwargs"] = kwargs
        yield push

    async def fake_send(push_arg, config_arg, logger_arg, **kwargs):
        calls["push"] = push_arg
        calls["send_kwargs"] = kwargs
        return True

    monkeypatch.setattr(refresh, "push_manager_context", fake_context)
    monkeypatch.setattr(refresh, "send_news_if_allowed", fake_send)

    await refresh._send_summary(config, summary)

    assert calls["context_kwargs"]["push_channels"] == ["ops"]
    assert calls["push"] is push
    assert calls["send_kwargs"]["quiet_log"].startswith("微博 Cookie 刷新")


def test_push_summary_never_contains_cookie_value() -> None:
    secret = "SUB=secret-value"
    summary = refresh.RefreshSummary(
        total_targets=1,
        renewed_targets=0,
        unique_cookies=1,
        changed_fields=(),
        conflicts=(),
        failures=("weibo.cookie：登录状态已失效",),
        wrote_file=False,
    )

    title, description = refresh._format_push(summary)

    assert title == "微博 Cookie 刷新失败"
    assert secret not in description


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("21:00", {"hour": "21", "minute": "0"}), ("invalid", {"hour": "21", "minute": "0"})],
)
def test_refresh_trigger_defaults_to_21(raw: str, expected: dict[str, str]) -> None:
    config = AppConfig(weibo_cookie_refresh_time=raw)

    assert refresh._get_weibo_cookie_refresh_trigger_kwargs(config) == expected
