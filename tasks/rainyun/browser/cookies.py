"""Cookies 读写"""

import json
import logging
import os
import time

from selenium.webdriver.chrome.webdriver import WebDriver

from tasks.rainyun.browser.urls import build_app_url
from tasks.rainyun.config_adapter import RainyunRunConfig

logger = logging.getLogger(__name__)


def _prefix(config: RainyunRunConfig) -> str:
    return f"用户 {config.display_name} " if config.display_name else ""


def save_cookies(driver: WebDriver, config: RainyunRunConfig) -> None:
    prefix = _prefix(config)
    cookies = driver.get_cookies()
    cookie_dir = os.path.dirname(config.cookie_file)
    if cookie_dir:
        os.makedirs(cookie_dir, exist_ok=True)
    with open(config.cookie_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f)
    logger.info("%sCookies 已保存到 %s", prefix, config.cookie_file)


def load_cookies(driver: WebDriver, config: RainyunRunConfig) -> bool:
    prefix = _prefix(config)
    if not os.path.exists(config.cookie_file):
        logger.info("%s未找到 cookies 文件", prefix)
        return False
    try:
        with open(config.cookie_file, encoding="utf-8") as f:
            cookies = json.load(f)
        driver.get(build_app_url(config, "/"))
        for cookie in cookies:
            cookie.pop("sameSite", None)
            cookie.pop("expiry", None)
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                logger.warning("%s添加 cookie 失败: %s", prefix, e)
        logger.info("%sCookies 已加载", prefix)
        return True
    except json.JSONDecodeError as e:
        backup = f"{config.cookie_file}.bad-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            os.replace(config.cookie_file, backup)
            logger.warning("%sCookies 文件损坏，已备份到 %s", prefix, backup)
        except OSError:
            pass
        try:
            with open(config.cookie_file, "w", encoding="utf-8") as f:
                json.dump([], f)
        except OSError:
            pass
        logger.error("%s加载 cookies 失败: %s", prefix, e)
        return False
    except Exception as e:
        logger.error("%s加载 cookies 失败: %s", prefix, e)
        return False
