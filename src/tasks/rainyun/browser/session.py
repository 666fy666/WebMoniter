"""浏览器会话（参考 Rainyun-Qiandao）"""

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import ddddocr
from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.selenium_manager import SeleniumManager
from selenium.webdriver.support.wait import WebDriverWait

from src.tasks.rainyun.api_client import RainyunAPI
from src.tasks.rainyun.config_adapter import RainyunRunConfig

logger = logging.getLogger(__name__)


class RainyunBrowserUnavailableError(RuntimeError):
    """浏览器环境缺失，重试无法自动恢复。"""


@dataclass
class RuntimeContext:
    driver: WebDriver
    wait: WebDriverWait
    ocr: ddddocr.DdddOcr
    det: ddddocr.DdddOcr
    temp_dir: str
    api: RainyunAPI
    config: RainyunRunConfig


def _default_chrome_binary() -> str | None:
    """本机常见 Chrome/Chromium 路径，便于 Selenium Manager 匹配对应 chromedriver 版本"""
    if sys.platform == "win32":
        roots = [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        ]
        candidates = [
            os.path.join(r, "Google", "Chrome", "Application", "chrome.exe") for r in roots
        ]
    elif sys.platform == "darwin":
        candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    else:
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]
    for path in candidates:
        if path and os.path.isfile(path) and _is_usable_browser_binary(path):
            return path
    return None


def _chromedriver_cache_dir() -> Path:
    return Path.home() / ".cache" / "selenium" / "chromedriver"


def _clear_chromedriver_cache() -> None:
    cache = _chromedriver_cache_dir()
    if cache.is_dir():
        shutil.rmtree(cache, ignore_errors=True)
        logger.info("已清除 Selenium chromedriver 缓存: %s", cache)


def _is_chromedriver_version_mismatch(exc: BaseException) -> bool:
    msg = str(exc)
    return "only supports Chrome version" in msg and "Current browser version" in msg


def _binary_version(path: str) -> tuple[bool, str]:
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


def _major_version_from_text(text: str) -> int | None:
    match = re.search(r"\b(\d+)\.", text)
    return int(match.group(1)) if match else None


def _binary_major_version(path: str) -> int | None:
    ok, detail = _binary_version(path)
    if not ok:
        return None
    return _major_version_from_text(detail)


def _log_unusable_binary(kind: str, path: str, detail: str, *, warning: bool) -> None:
    if warning:
        logger.warning("忽略不可用 %s: %s (%s)", kind, path, detail)
    else:
        logger.debug("忽略不可用 %s: %s (%s)", kind, path, detail)


def _is_usable_browser_binary(path: str, *, warning: bool = False) -> bool:
    ok, detail = _binary_version(path)
    if not ok:
        _log_unusable_binary("Chrome/Chromium", path, detail, warning=warning)
        return False
    logger.debug("检测到 Chrome/Chromium: %s (%s)", path, detail.splitlines()[0])
    return True


def _is_usable_chromedriver(
    path: str, *, browser_major: int | None = None, warning: bool = False
) -> bool:
    ok, detail = _binary_version(path)
    if not ok:
        _log_unusable_binary("chromedriver", path, detail, warning=warning)
        return False
    driver_major = _major_version_from_text(detail)
    if browser_major and driver_major and driver_major != browser_major:
        message = f"{detail.splitlines()[0]}，与浏览器主版本 {browser_major} 不匹配"
        _log_unusable_binary("chromedriver", path, message, warning=warning)
        return False
    logger.debug("检测到 chromedriver: %s (%s)", path, detail.splitlines()[0])
    return True


def _is_webdriver_environment_error(exc: BaseException) -> bool:
    msg = str(exc)
    markers = (
        "unexpectedly exited",
        "Unable to obtain driver",
        "cannot find Chrome binary",
        "requires the chromium snap",
        "snap install chromium",
    )
    return any(marker in msg for marker in markers)


def _resolve_chromedriver_via_manager(chrome_bin: str | None) -> str | None:
    """通过 Selenium Manager 获取与当前 Chrome 主版本匹配的 chromedriver"""
    args = ["--browser", "chrome"]
    if chrome_bin:
        args.extend(["--browser-path", chrome_bin])
    try:
        output = SeleniumManager().binary_paths(args)
        path = output.get("driver_path", "")
        if path and os.path.isfile(path):
            logger.debug("Selenium Manager 选用 chromedriver: %s", path)
            return path
    except Exception as e:
        logger.warning("Selenium Manager 获取 chromedriver 失败: %s", e)
    return None


def _get_chromedriver_path(
    config: RainyunRunConfig,
    browser_bin: str | None = None,
    *,
    include_auto_candidates: bool = True,
) -> str | None:
    """返回可用的本地 chromedriver；自动候选只作为 Selenium Manager 后的兜底。"""
    browser_major = _binary_major_version(browser_bin) if browser_bin else None
    path = config.chromedriver_path
    if path:
        if os.path.exists(path) and _is_usable_chromedriver(
            path,
            browser_major=browser_major,
            warning=True,
        ):
            return path
        logger.warning("配置的 chromedriver_path 不可用，将尝试 Selenium Manager: %s", path)
    if not include_auto_candidates:
        return None
    for candidate in [
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "/usr/lib/chromium/chromedriver",
        "/usr/lib/chromium-browser/chromedriver",
    ]:
        if os.path.exists(candidate) and _is_usable_chromedriver(
            candidate,
            browser_major=browser_major,
            warning=False,
        ):
            return candidate
    return None


class BrowserSession:
    def __init__(self, config: RainyunRunConfig, debug: bool = False, linux: bool = True):
        self.config = config
        self.debug = debug
        self.linux = linux
        self.driver: WebDriver | None = None
        self.wait: WebDriverWait | None = None
        self.temp_dir: str = ""

    def start(self) -> tuple[WebDriver, WebDriverWait, str]:
        driver = self._init_selenium()
        self._apply_stealth(driver)
        wait = WebDriverWait(driver, self.config.timeout)
        temp_dir = tempfile.mkdtemp(prefix="rainyun-")
        self.driver = driver
        self.wait = wait
        self.temp_dir = temp_dir
        return driver, wait, temp_dir

    def close(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

    def _init_selenium(self) -> WebDriver:
        ops = Options()
        ops.add_argument("--no-sandbox")
        if self.debug:
            ops.add_experimental_option("detach", True)
        if self.linux:
            ops.add_argument("--headless")
            ops.add_argument("--disable-gpu")
            ops.add_argument("--disable-dev-shm-usage")
        if self.config.chrome_low_memory:
            ops.add_argument("--disable-extensions")
            ops.add_argument("--disable-background-networking")
            ops.add_argument("--disable-sync")
            ops.add_argument("--disable-translate")
            ops.add_argument("--disable-default-apps")
            ops.add_argument("--no-first-run")
            ops.add_argument("--disable-software-rasterizer")
            ops.add_argument("--js-flags=--max-old-space-size=256")
        configured_chrome = (self.config.chrome_bin or "").strip()
        if configured_chrome:
            if os.path.isfile(configured_chrome) and _is_usable_browser_binary(
                configured_chrome,
                warning=True,
            ):
                ops.binary_location = configured_chrome
            else:
                raise RainyunBrowserUnavailableError(
                    f"配置的 Chrome/Chromium 路径不存在或不可用: {configured_chrome}"
                )
        else:
            default_bin = _default_chrome_binary()
            if default_bin:
                ops.binary_location = default_bin
            else:
                raise RainyunBrowserUnavailableError(
                    "未找到 Chrome/Chromium 浏览器，请安装 google-chrome-stable 或 chromium，"
                    "或配置 rainyun.chrome_bin/CHROME_BIN 后重试"
                )

        chrome_bin = ops.binary_location or None
        driver_path = _get_chromedriver_path(
            self.config,
            chrome_bin,
            include_auto_candidates=False,
        )
        if driver_path:
            try:
                return webdriver.Chrome(service=Service(driver_path), options=ops)
            except WebDriverException as e:
                logger.warning(
                    "chromedriver %s 启动失败，将尝试 Selenium Manager: %s",
                    driver_path,
                    e,
                )
                if _is_chromedriver_version_mismatch(e):
                    _clear_chromedriver_cache()

        for attempt in range(2):
            resolved = _resolve_chromedriver_via_manager(chrome_bin)
            try:
                if resolved:
                    return webdriver.Chrome(service=Service(resolved), options=ops)
                return webdriver.Chrome(options=ops)
            except SessionNotCreatedException as e:
                if attempt == 0 and _is_chromedriver_version_mismatch(e):
                    logger.warning("chromedriver 与 Chrome 版本不匹配，清除缓存后重试: %s", e)
                    _clear_chromedriver_cache()
                    continue
                raise
            except WebDriverException as e:
                if _is_webdriver_environment_error(e):
                    raise RainyunBrowserUnavailableError(f"Chrome WebDriver 初始化失败: {e}") from e
                raise

        driver_path = _get_chromedriver_path(
            self.config,
            chrome_bin,
            include_auto_candidates=True,
        )
        if driver_path:
            try:
                return webdriver.Chrome(service=Service(driver_path), options=ops)
            except WebDriverException as e:
                raise RainyunBrowserUnavailableError(f"Chrome WebDriver 初始化失败: {e}") from e
        raise RuntimeError("无法初始化 Chrome WebDriver")

    def _apply_stealth(self, driver: WebDriver) -> None:
        stealth_paths = [
            "stealth.min.js",
            Path(__file__).resolve().parents[3] / "webUI" / "static" / "stealth.min.js",
            Path(__file__).resolve().parents[1] / "stealth.min.js",
            "tasks/rainyun/stealth.min.js",
        ]
        for p in stealth_paths:
            if os.path.exists(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        js = f.read()
                    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": js})
                    logger.debug("已应用 stealth.min.js")
                except Exception as e:
                    logger.warning("应用 stealth.min.js 失败: %s", e)
                return
