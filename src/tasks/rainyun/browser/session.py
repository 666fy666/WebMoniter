"""浏览器会话（参考 Rainyun-Qiandao）"""

import logging
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import ddddocr
from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.selenium_manager import SeleniumManager
from selenium.webdriver.support.wait import WebDriverWait

from src.tasks.rainyun.api_client import RainyunAPI
from src.tasks.rainyun.config_adapter import RainyunRunConfig

logger = logging.getLogger(__name__)


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
        if path and os.path.isfile(path):
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


def _get_chromedriver_path(config: RainyunRunConfig) -> str | None:
    """若配置中指定了存在可用的 chromedriver 路径则返回，否则返回 None 以使用 Selenium Manager 自动管理"""
    path = config.chromedriver_path
    if path and os.path.exists(path):
        return path
    for candidate in [
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "/usr/lib/chromium/chromedriver",
        "/usr/lib/chromium-browser/chromedriver",
    ]:
        if os.path.exists(candidate):
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
        if self.config.chrome_bin and os.path.exists(self.config.chrome_bin):
            ops.binary_location = self.config.chrome_bin
        elif not ops.binary_location:
            default_bin = _default_chrome_binary()
            if default_bin:
                ops.binary_location = default_bin

        driver_path = _get_chromedriver_path(self.config)
        if driver_path:
            return webdriver.Chrome(service=Service(driver_path), options=ops)

        chrome_bin = ops.binary_location or None
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
