from __future__ import annotations

from types import SimpleNamespace

from src.core import preflight


def test_format_preflight_report_includes_solutions():
    report = preflight.PreflightReport(
        issues=(
            preflight.PreflightIssue(
                name="Python",
                detail="当前版本不符合要求",
                solution="uv python install 3.11",
            ),
        ),
        notes=("uv: uv 0.8.0",),
    )

    text = preflight.format_preflight_report(report)

    assert "环境预检失败" in text
    assert "当前版本不符合要求" in text
    assert "uv python install 3.11" in text
    assert "已通过项目" in text


def test_format_preflight_success_is_concise_by_default():
    report = preflight.PreflightReport(issues=(), notes=("uv: uv 0.11.26", "Python: 3.11.15"))

    assert preflight.format_preflight_report(report) == "环境预检通过"


def test_format_preflight_success_can_show_verbose_notes():
    report = preflight.PreflightReport(issues=(), notes=("uv: uv 0.11.26", "Python: 3.11.15"))

    text = preflight.format_preflight_report(report, verbose=True)

    assert text.startswith("环境预检通过：")
    assert "Python: 3.11.15" in text


def test_browser_required_only_when_browser_tasks_enabled():
    disabled = SimpleNamespace(
        checkin_enable=False,
        rainyun_enable=False,
        weibo_cookie_refresh_enable=False,
    )
    enabled = SimpleNamespace(
        checkin_enable=True,
        rainyun_enable=False,
        weibo_cookie_refresh_enable=False,
    )
    refresh_enabled = SimpleNamespace(
        checkin_enable=False,
        rainyun_enable=False,
        weibo_cookie_refresh_enable=True,
    )

    assert preflight._browser_required(disabled) == (False, [])
    assert preflight._browser_required(enabled) == (True, ["ikuuu_checkin"])
    assert preflight._browser_required(refresh_enabled) == (True, ["weibo_cookie_refresh"])


def test_localhost_proxy_bypass_preserves_existing_entries(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "internal.example")
    monkeypatch.delenv("no_proxy", raising=False)

    preflight._ensure_localhost_proxy_bypass()

    assert preflight.os.environ["NO_PROXY"].split(",") == [
        "internal.example",
        "localhost",
        "127.0.0.1",
        "::1",
    ]


def test_configured_browser_preferred_over_common_paths(monkeypatch):
    config = SimpleNamespace(rainyun_chrome_bin="/opt/chrome", rainyun_chromedriver_path="")

    def valid_binary(path):
        if path == "/opt/chrome":
            return True, "Google Chrome 150.0.0.0"
        return False, "missing"

    monkeypatch.delenv("CHROME_BIN", raising=False)
    monkeypatch.setattr(preflight, "_valid_binary", valid_binary)

    path, detail = preflight._configured_or_common_browser(config)

    assert path == "/opt/chrome"
    assert "Google Chrome" in detail


def test_invalid_configured_chromedriver_blocks_startup(monkeypatch):
    config = SimpleNamespace(rainyun_chromedriver_path="/bad/chromedriver")
    issues = []
    notes = []

    monkeypatch.delenv("CHROMEDRIVER_PATH", raising=False)
    monkeypatch.setattr(preflight, "_valid_binary", lambda path: (False, "snap stub"))

    result = preflight._resolve_local_chromedriver(
        issues,
        config,
        "Google Chrome 150.0.0.0",
        notes,
    )

    assert result is None
    assert len(issues) == 1
    assert issues[0].name == "chromedriver"
    assert "snap stub" in issues[0].detail


def test_auto_chromedriver_candidates_ignore_snap_stub(monkeypatch):
    config = SimpleNamespace(rainyun_chromedriver_path="")
    issues = []
    notes = []

    monkeypatch.delenv("CHROMEDRIVER_PATH", raising=False)
    monkeypatch.setattr(preflight, "_driver_candidates", lambda: ("/usr/bin/chromedriver",))
    monkeypatch.setattr(
        preflight,
        "_valid_binary",
        lambda path: (False, "Command '/usr/bin/chromedriver' requires the chromium snap"),
    )

    result = preflight._resolve_local_chromedriver(
        issues,
        config,
        "Google Chrome 150.0.0.0",
        notes,
    )

    assert result is None
    assert issues == []
    assert "未找到本地匹配驱动" in notes[0]


def test_matching_chromedriver_candidate_is_used(monkeypatch):
    config = SimpleNamespace(rainyun_chromedriver_path="")
    issues = []
    notes = []

    monkeypatch.delenv("CHROMEDRIVER_PATH", raising=False)
    monkeypatch.setattr(preflight, "_driver_candidates", lambda: ("/opt/chromedriver",))
    monkeypatch.setattr(
        preflight,
        "_valid_binary",
        lambda path: (True, "ChromeDriver 150.0.7871.46"),
    )

    result = preflight._resolve_local_chromedriver(
        issues,
        config,
        "Google Chrome 150.0.0.0",
        notes,
    )

    assert result == "/opt/chromedriver"
    assert issues == []
    assert "ChromeDriver 150" in notes[0]


def test_browser_smoke_is_skipped_by_default(monkeypatch):
    issues = []
    notes = []

    monkeypatch.delenv(preflight.BROWSER_SMOKE_ENV, raising=False)

    preflight._check_browser_smoke(
        issues,
        notes,
        "/opt/chrome",
        None,
        "Google Chrome 150.0.0.0",
    )

    assert issues == []
    assert "已跳过" in notes[0]
    assert preflight.BROWSER_SMOKE_ENV in notes[0]


def test_browser_smoke_failure_points_to_direct_chromium_probe(monkeypatch):
    issues = []
    notes = []

    monkeypatch.setenv(preflight.BROWSER_SMOKE_ENV, "1")
    monkeypatch.setattr(preflight, "_is_truthy", lambda value: value == "1")

    class FailingWebDriver:
        @staticmethod
        def Chrome(*args, **kwargs):  # noqa: N802
            raise RuntimeError("Chrome instance exited")

    class DummyOptions:
        def __init__(self):
            self.binary_location = ""
            self.arguments = []

        def add_argument(self, argument):
            self.arguments.append(argument)

    class DummyService:
        def __init__(self, path):
            self.path = path

    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "selenium":
            return SimpleNamespace(webdriver=FailingWebDriver)
        if name == "selenium.webdriver.chrome.options":
            return SimpleNamespace(Options=DummyOptions)
        if name == "selenium.webdriver.chrome.service":
            return SimpleNamespace(Service=DummyService)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    preflight._check_browser_smoke(
        issues,
        notes,
        "/usr/bin/chromium",
        "/usr/bin/chromedriver",
        "Chromium 150.0.7871.46",
    )

    assert len(issues) == 1
    assert preflight.SMOKE_TEST_COMMAND in issues[0].solution
    assert "132/133" in issues[0].solution
