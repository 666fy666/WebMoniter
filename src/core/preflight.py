"""Startup environment preflight for source-based runs."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_SOURCE_PYTHON = (3, 11)
SKIP_ENV = "WEBMONITER_SKIP_PREFLIGHT"
BROWSER_SMOKE_ENV = "WEBMONITER_PREFLIGHT_BROWSER_SMOKE"
VERBOSE_ENV = "WEBMONITER_PREFLIGHT_VERBOSE"

CORE_IMPORTS: tuple[tuple[str, str], ...] = (
    ("aiohttp", "aiohttp"),
    ("requests", "requests"),
    ("aiosqlite", "aiosqlite"),
    ("pydantic", "pydantic"),
    ("apscheduler", "apscheduler"),
    ("yaml", "pyyaml"),
    ("ruamel.yaml", "ruamel.yaml"),
    ("aiosmtplib", "aiosmtplib"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("jinja2", "jinja2"),
    ("multipart", "python-multipart"),
    ("itsdangerous", "itsdangerous"),
    ("bs4", "beautifulsoup4"),
    ("PIL", "pillow"),
    ("rsa", "rsa"),
    ("Crypto", "pycryptodome"),
)
DEV_IMPORTS: tuple[tuple[str, str], ...] = (
    ("pytest", "pytest"),
    ("pytest_asyncio", "pytest-asyncio"),
)
RAINYUN_IMPORTS: tuple[tuple[str, str], ...] = (
    ("selenium", "selenium"),
    ("ddddocr", "ddddocr"),
    ("cv2", "opencv-python-headless"),
)
IKUUU_BROWSER_IMPORTS: tuple[tuple[str, str], ...] = (("selenium", "selenium"),)

COMMON_CHROME_PATHS: tuple[str, ...] = (
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
COMMON_CHROMEDRIVER_PATHS: tuple[str, ...] = (
    "/usr/bin/chromedriver",
    "/usr/local/bin/chromedriver",
    "/usr/lib/chromium/chromedriver",
    "/usr/lib/chromium-browser/chromedriver",
)


@dataclass(frozen=True)
class PreflightIssue:
    name: str
    detail: str
    solution: str


@dataclass(frozen=True)
class PreflightReport:
    issues: tuple[PreflightIssue, ...]
    notes: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


def _is_docker() -> bool:
    return Path("/.dockerenv").exists() or os.environ.get("WEBMONITER_DOCKER") == "1"


def _is_source_run() -> bool:
    return not _is_docker() and not getattr(sys, "frozen", False)


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_falsey(value: str | None) -> bool:
    return (value or "").strip().lower() in {"0", "false", "no", "off"}


def _run_version_command(path: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    if result.returncode != 0:
        return False, output or f"exit code {result.returncode}"
    return True, output


def _has_import(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _missing_imports(imports: tuple[tuple[str, str], ...]) -> list[str]:
    return [package_name for module_name, package_name in imports if not _has_import(module_name)]


def _source_setup_solution() -> str:
    return (
        "建议执行：uv python install 3.11；uv venv --python 3.11；"
        "uv sync --extra dev --extra rainyun；uv run python main.py"
    )


def _check_uv(issues: list[PreflightIssue], notes: list[str]) -> None:
    uv_path = shutil.which("uv")
    if not uv_path:
        issues.append(
            PreflightIssue(
                "uv",
                "源码运行模式未找到 uv。",
                "安装 uv 后重试：curl -LsSf https://astral.sh/uv/install.sh | sh",
            )
        )
        return
    ok, version = _run_version_command(uv_path)
    if ok:
        notes.append(f"uv: {version}")
    else:
        issues.append(
            PreflightIssue(
                "uv",
                f"uv 可执行文件不可用：{version}",
                "重新安装 uv，或确认 uv 所在目录已加入 PATH。",
            )
        )


def _check_python(issues: list[PreflightIssue], notes: list[str]) -> None:
    current = sys.version_info[:2]
    expected = REQUIRED_SOURCE_PYTHON
    if current != expected:
        issues.append(
            PreflightIssue(
                "Python",
                f"源码运行固定使用 Python {expected[0]}.{expected[1]}，当前是 {sys.version.split()[0]}。",
                _source_setup_solution(),
            )
        )
        return
    notes.append(f"Python: {sys.version.split()[0]}")


def _check_virtualenv(issues: list[PreflightIssue], notes: list[str]) -> None:
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix) or bool(
        os.environ.get("VIRTUAL_ENV")
    )
    if not in_venv:
        issues.append(
            PreflightIssue(
                "虚拟环境",
                "当前 Python 不在虚拟环境中。",
                "请使用 uv run python main.py 启动，或先执行 uv sync --extra dev --extra rainyun。",
            )
        )
        return
    notes.append(f"虚拟环境: {sys.prefix}")


def _check_imports(
    issues: list[PreflightIssue],
    imports: tuple[tuple[str, str], ...],
    *,
    name: str,
    solution: str,
) -> None:
    missing = _missing_imports(imports)
    if missing:
        issues.append(
            PreflightIssue(
                name,
                "缺少 Python 依赖：" + ", ".join(sorted(set(missing))),
                solution,
            )
        )


def _load_config_for_preflight(issues: list[PreflightIssue]) -> Any | None:
    try:
        from src.settings.config import get_config

        return get_config(reload=True)
    except Exception as exc:
        issues.append(
            PreflightIssue(
                "配置",
                f"配置加载失败：{exc}",
                "请确认 config.yml 存在且格式正确，可参考 config/config.yml.sample。",
            )
        )
        return None


def _browser_required(config: Any | None) -> tuple[bool, list[str]]:
    if config is None:
        return False, []
    tasks: list[str] = []
    if bool(getattr(config, "checkin_enable", False)):
        tasks.append("ikuuu_checkin")
    if bool(getattr(config, "rainyun_enable", False)):
        tasks.append("rainyun_checkin")
    return bool(tasks), tasks


def _valid_binary(path: str) -> tuple[bool, str]:
    if not path or not Path(path).is_file():
        return False, "文件不存在"
    return _run_version_command(path)


def _major_version_from_text(text: str) -> int | None:
    match = re.search(r"\b(\d+)\.", text)
    return int(match.group(1)) if match else None


def _configured_or_common_browser(config: Any | None) -> tuple[str | None, str]:
    candidates = [
        os.environ.get("CHROME_BIN", "").strip(),
        str(getattr(config, "rainyun_chrome_bin", "") or "").strip() if config else "",
        *COMMON_CHROME_PATHS,
    ]
    seen: set[str] = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        ok, detail = _valid_binary(path)
        if ok:
            return path, detail
    return None, "未找到可执行的 Chrome/Chromium"


def _configured_driver(config: Any | None) -> str:
    return os.environ.get("CHROMEDRIVER_PATH", "").strip() or (
        str(getattr(config, "rainyun_chromedriver_path", "") or "").strip() if config else ""
    )


def _driver_candidates() -> tuple[str, ...]:
    candidates = (shutil.which("chromedriver") or "", *COMMON_CHROMEDRIVER_PATHS)
    return tuple(dict.fromkeys(path for path in candidates if path))


def _validate_chromedriver(
    path: str,
    browser_major: int | None,
) -> tuple[bool, str]:
    ok, detail = _valid_binary(path)
    if not ok:
        return False, detail
    driver_major = _major_version_from_text(detail)
    if browser_major and driver_major and browser_major != driver_major:
        return False, f"{detail.splitlines()[0]}，与 Chrome 主版本 {browser_major} 不匹配"
    return True, detail


def _resolve_local_chromedriver(
    issues: list[PreflightIssue],
    config: Any | None,
    browser_detail: str,
    notes: list[str],
) -> str | None:
    browser_major = _major_version_from_text(browser_detail)
    configured = _configured_driver(config)
    if configured:
        ok, detail = _validate_chromedriver(configured, browser_major)
        if ok:
            notes.append(f"chromedriver: {configured} ({detail.splitlines()[0]})")
            return configured
        issues.append(
            PreflightIssue(
                "chromedriver",
                f"配置的 chromedriver 不可用：{configured} ({detail})",
                "删除错误的 CHROMEDRIVER_PATH/rainyun.chromedriver_path，或配置与当前 Chrome "
                "主版本匹配的真实 chromedriver 路径。",
            )
        )
        return None

    ignored: list[str] = []
    for candidate in _driver_candidates():
        ok, detail = _validate_chromedriver(candidate, browser_major)
        if ok:
            notes.append(f"chromedriver: {candidate} ({detail.splitlines()[0]})")
            return candidate
        ignored.append(f"{candidate} ({detail.splitlines()[0] if detail else '不可用'})")

    if ignored:
        notes.append("chromedriver: 未找到本地匹配驱动，已忽略 " + "；".join(ignored[:3]))
    else:
        notes.append("chromedriver: 未找到本地驱动，浏览器任务运行时将尝试 Selenium Manager")
    return None


def _check_browser_smoke(
    issues: list[PreflightIssue],
    notes: list[str],
    browser_path: str,
    driver_path: str | None,
    browser_detail: str,
) -> None:
    if not _is_truthy(os.environ.get(BROWSER_SMOKE_ENV)):
        notes.append(
            "浏览器自动化 smoke test: 已跳过；如需启动前验证 WebDriver，"
            f"设置 {BROWSER_SMOKE_ENV}=1"
        )
        return
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        options = Options()
        options.binary_location = browser_path
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        driver = (
            webdriver.Chrome(service=Service(driver_path), options=options)
            if driver_path
            else webdriver.Chrome(options=options)
        )
        try:
            driver.quit()
        finally:
            del driver
        notes.append("浏览器自动化: Chrome WebDriver 可启动")
    except Exception as exc:
        issues.append(
            PreflightIssue(
                "浏览器自动化",
                f"Chrome WebDriver 启动失败：{exc}",
                "若是源码运行，先执行 uv sync --extra rainyun；当前浏览器为 "
                f"{browser_detail.splitlines()[0]}。若 Selenium Manager 无法下载驱动，"
                "请安装同主版本 chromedriver，并配置 CHROMEDRIVER_PATH/rainyun.chromedriver_path；"
                "不要使用 Ubuntu snap 的 /usr/bin/chromedriver stub。",
            )
        )


def _check_browser(
    issues: list[PreflightIssue],
    notes: list[str],
    config: Any | None,
    enabled_browser_tasks: list[str],
) -> None:
    browser_path, browser_detail = _configured_or_common_browser(config)
    if not browser_path:
        issues.append(
            PreflightIssue(
                "浏览器",
                f"已启用 {', '.join(enabled_browser_tasks)}，但未找到可用 Chrome/Chromium。",
                "Ubuntu 源码运行可安装 google-chrome-stable，或使用 Docker full 镜像；"
                "路径特殊时配置 CHROME_BIN/rainyun.chrome_bin。",
            )
        )
        return

    notes.append(f"浏览器: {browser_path} ({browser_detail.splitlines()[0]})")
    driver_path = _resolve_local_chromedriver(issues, config, browser_detail, notes)
    if any(issue.name == "chromedriver" for issue in issues):
        return
    _check_browser_smoke(issues, notes, browser_path, driver_path, browser_detail)


def check_preflight() -> PreflightReport:
    """Return startup preflight issues without printing or exiting."""
    issues: list[PreflightIssue] = []
    notes: list[str] = []
    source_run = _is_source_run()

    if source_run:
        _check_uv(issues, notes)
        _check_python(issues, notes)
        _check_virtualenv(issues, notes)

    dependency_solution = "请执行：uv sync --extra dev --extra rainyun"
    _check_imports(issues, CORE_IMPORTS, name="核心依赖", solution=dependency_solution)
    if source_run:
        _check_imports(issues, DEV_IMPORTS, name="开发依赖", solution=dependency_solution)

    config = (
        None
        if any(issue.name in {"核心依赖"} for issue in issues)
        else _load_config_for_preflight(issues)
    )
    browser_needed, browser_tasks = _browser_required(config)
    if browser_needed:
        browser_imports = IKUUU_BROWSER_IMPORTS
        if "rainyun_checkin" in browser_tasks:
            browser_imports = tuple(dict.fromkeys((*IKUUU_BROWSER_IMPORTS, *RAINYUN_IMPORTS)))
        _check_imports(issues, browser_imports, name="浏览器任务依赖", solution=dependency_solution)
        if not any(issue.name == "浏览器任务依赖" for issue in issues):
            _check_browser(issues, notes, config, browser_tasks)
    else:
        notes.append("浏览器任务: 未启用，跳过 Chrome WebDriver 检查")

    return PreflightReport(issues=tuple(issues), notes=tuple(notes))


def format_preflight_report(report: PreflightReport, *, verbose: bool | None = None) -> str:
    if verbose is None:
        verbose = _is_truthy(os.environ.get(VERBOSE_ENV))

    if report.ok:
        if not verbose:
            return "环境预检通过"
        note_text = "；".join(report.notes)
        return f"环境预检通过：{note_text}" if note_text else "环境预检通过"

    lines = ["环境预检失败，项目未启动："]
    for idx, issue in enumerate(report.issues, start=1):
        lines.append(f"{idx}. {issue.name}: {issue.detail}")
        lines.append(f"   解决方案: {issue.solution}")
    if report.notes:
        lines.append("已通过项目：" + "；".join(report.notes))
    return "\n".join(lines)


def run_startup_preflight() -> None:
    """Run preflight before starting the web server; exits process on failure."""
    if _is_truthy(os.environ.get(SKIP_ENV)):
        print("环境预检已跳过（WEBMONITER_SKIP_PREFLIGHT=1）")
        return

    report = check_preflight()
    print(format_preflight_report(report))
    if not report.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    run_startup_preflight()
