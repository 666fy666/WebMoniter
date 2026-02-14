"""浏览器会话（参考 Rainyun-Qiandao）"""

import logging
import os
import tempfile
from dataclasses import dataclass

import ddddocr
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait

from tasks.rainyun.api_client import RainyunAPI
from tasks.rainyun.config_adapter import RainyunRunConfig

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
        driver_path = _get_chromedriver_path(self.config)
        if driver_path:
            return webdriver.Chrome(service=Service(driver_path), options=ops)
        # 未配置 chromedriver 时，由 Selenium 4.6+ 的 Selenium Manager 自动下载并管理
        return webdriver.Chrome(options=ops)

    def _apply_stealth(self, driver: WebDriver) -> None:
        stealth_paths = [
            "stealth.min.js",
            "web/static/stealth.min.js",
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
