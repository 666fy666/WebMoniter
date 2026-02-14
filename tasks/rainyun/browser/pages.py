"""页面对象封装（参考 Rainyun-Qiandao browser/pages.py）"""

import logging
import re
import time
from collections.abc import Callable

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from tasks.rainyun.browser.cookies import save_cookies
from tasks.rainyun.browser.locators import XPATH_CONFIG
from tasks.rainyun.browser.session import RuntimeContext
from tasks.rainyun.browser.urls import build_app_url

logger = logging.getLogger(__name__)
CaptchaHandler = Callable[["RuntimeContext"], bool]


class LoginPage:
    _LOGIN_MAX_ATTEMPTS = 2
    _LOGIN_REDIRECT_WAIT_SECONDS = 20
    _LOGIN_CAPTCHA_WAIT_SECONDS = 8

    def __init__(self, ctx: RuntimeContext, captcha_handler: CaptchaHandler) -> None:
        self.ctx = ctx
        self.captcha_handler = captcha_handler

    def check_login_status(self) -> bool:
        user_label = self.ctx.config.display_name or self.ctx.config.rainyun_user
        self.ctx.driver.get(build_app_url(self.ctx.config, "/dashboard"))
        time.sleep(3)
        if "login" in self.ctx.driver.current_url:
            logger.info("用户 %s Cookie 已失效，需要重新登录", user_label)
            return False
        if self.ctx.driver.current_url == build_app_url(self.ctx.config, "/dashboard"):
            logger.info("用户 %s Cookie 有效，已登录", user_label)
            return True
        return False

    def _submit_login_form(self, user: str, pwd: str, user_label: str) -> bool:
        try:
            username = self.ctx.wait.until(
                EC.visibility_of_element_located((By.NAME, "login-field"))
            )
            password = self.ctx.wait.until(
                EC.visibility_of_element_located((By.NAME, "login-password"))
            )
            login_button = self.ctx.wait.until(
                EC.visibility_of_element_located((By.XPATH, XPATH_CONFIG["LOGIN_BTN"]))
            )
            username.clear()
            password.clear()
            username.send_keys(user)
            password.send_keys(pwd)
            # 先滚动到按钮可见，避免被 footer 等元素遮挡导致 ElementClickInterceptedException
            self.ctx.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", login_button
            )
            time.sleep(0.3)
            try:
                login_button.click()
            except Exception:
                self.ctx.driver.execute_script("arguments[0].click();", login_button)
            return True
        except TimeoutException:
            logger.error("用户 %s 页面加载超时", user_label)
            return False

    def _handle_login_captcha(self, user_label: str, wait_seconds: int) -> bool:
        try:
            captcha_wait = WebDriverWait(self.ctx.driver, wait_seconds, poll_frequency=0.5)
            captcha_wait.until(EC.visibility_of_element_located((By.ID, "tcaptcha_iframe_dy")))
            logger.warning("用户 %s 触发验证码！", user_label)
            self.ctx.driver.switch_to.frame("tcaptcha_iframe_dy")
            if not self.captcha_handler(self.ctx):
                logger.error("用户 %s 登录验证码识别失败", user_label)
                return False
            return True
        except TimeoutException:
            logger.info("用户 %s 未触发验证码", user_label)
            return True
        finally:
            self.ctx.driver.switch_to.default_content()

    def _wait_login_redirect(self) -> bool:
        wait_seconds = max(self.ctx.config.timeout, self._LOGIN_REDIRECT_WAIT_SECONDS)
        redirect_wait = WebDriverWait(self.ctx.driver, wait_seconds, poll_frequency=0.5)
        try:
            redirect_wait.until(EC.url_contains("dashboard"))
            return True
        except TimeoutException:
            return False

    def login(self, user: str, pwd: str) -> bool:
        user_label = self.ctx.config.display_name or user
        logger.info("用户 %s 发起登录请求", user_label)
        self.ctx.driver.get(build_app_url(self.ctx.config, "/auth/login"))
        for attempt in range(1, self._LOGIN_MAX_ATTEMPTS + 1):
            if not self._submit_login_form(user, pwd, user_label):
                return False
            captcha_wait_seconds = max(self.ctx.config.timeout, self._LOGIN_CAPTCHA_WAIT_SECONDS)
            if attempt > 1:
                captcha_wait_seconds = self._LOGIN_CAPTCHA_WAIT_SECONDS
            if not self._handle_login_captcha(user_label, wait_seconds=captcha_wait_seconds):
                return False
            time.sleep(2)
            if self._wait_login_redirect():
                logger.info("用户 %s 登录成功！", user_label)
                save_cookies(self.ctx.driver, self.ctx.config)
                return True
            current_url = self.ctx.driver.current_url
            if attempt < self._LOGIN_MAX_ATTEMPTS and "/auth/login" in current_url:
                logger.warning("用户 %s 第 %d 次登录后仍停留登录页，自动重试", user_label, attempt)
                continue
            break
        logger.error(
            "用户 %s 登录超时或失败！当前 URL: %s", user_label, self.ctx.driver.current_url
        )
        return False


class RewardPage:
    _REWARD_PAGE_PATH = "/account/reward/earn"
    _REWARD_PAGE_URL_WAIT_SECONDS = 8
    _REWARD_PAGE_MENU_XPATH = "//a[contains(@href, '/account/reward/earn')]"
    _DAILY_SIGN_CLAIM_TEXTS = ("领取奖励", "去完成", "去签到")
    _DAILY_SIGN_CLAIM_XPATH = "//*[self::a or self::button][contains(normalize-space(.), '领取奖励') or contains(normalize-space(.), '去完成') or contains(normalize-space(.), '去签到')]"
    _DAILY_SIGN_DONE_PATTERNS = ("已完成", "已领取", "已签到", "明日再来")
    _DAILY_SIGN_SECTION_WAIT_SECONDS = 25
    _DAILY_SIGN_DONE_WAIT_SECONDS = 12

    def __init__(self, ctx: RuntimeContext, captcha_handler: CaptchaHandler) -> None:
        self.ctx = ctx
        self.captcha_handler = captcha_handler

    def _wait_reward_page_url(self, timeout: int | None = None) -> bool:
        if timeout is None:
            timeout = self._REWARD_PAGE_URL_WAIT_SECONDS
        wait = WebDriverWait(self.ctx.driver, timeout, poll_frequency=0.5)
        try:
            return bool(wait.until(EC.url_contains(self._REWARD_PAGE_PATH)))
        except TimeoutException:
            return False

    def _click_reward_menu_link(self) -> bool:
        try:
            links = self.ctx.driver.find_elements(By.XPATH, self._REWARD_PAGE_MENU_XPATH)
        except Exception:
            return False
        if not links:
            return False
        visible_links = []
        hidden_links = []
        for link in links:
            try:
                if link.is_displayed() and link.is_enabled():
                    visible_links.append(link)
                else:
                    hidden_links.append(link)
            except Exception:
                hidden_links.append(link)
        for link in [*visible_links, *hidden_links]:
            try:
                link.click()
                return True
            except Exception:
                try:
                    self.ctx.driver.execute_script("arguments[0].click();", link)
                    return True
                except Exception:
                    continue
        return False

    def open(self) -> bool:
        target_url = build_app_url(self.ctx.config, self._REWARD_PAGE_PATH)
        user_label = self.ctx.config.display_name or self.ctx.config.rainyun_user
        if self._click_reward_menu_link() and self._wait_reward_page_url():
            logger.info("用户 %s 通过站内菜单进入奖励页", user_label)
            return True
        self.ctx.driver.get(target_url)
        if self._wait_reward_page_url():
            logger.info("用户 %s 通过直接 URL 进入奖励页", user_label)
            return True
        fallback_url = f"{target_url}?_ts={int(time.time() * 1000)}"
        try:
            self.ctx.driver.execute_script("window.location.assign(arguments[0]);", fallback_url)
        except Exception:
            self.ctx.driver.get(fallback_url)
        if self._wait_reward_page_url(timeout=max(self._REWARD_PAGE_URL_WAIT_SECONDS, 10)):
            logger.info("用户 %s 通过 JS 跳转进入奖励页", user_label)
            return True
        return False

    def _wait_daily_sign_section_ready(self, timeout: int | None = None) -> bool:
        if timeout is None:
            timeout = max(self._DAILY_SIGN_SECTION_WAIT_SECONDS, self.ctx.config.timeout)
        wait = WebDriverWait(self.ctx.driver, timeout, poll_frequency=0.5)

        def _probe(driver):
            if driver.find_elements(By.XPATH, XPATH_CONFIG["SIGN_IN_HEADER"]):
                return True
            if driver.find_elements(By.XPATH, XPATH_CONFIG["SIGN_IN_CARD"]):
                return True
            has_daily_sign_span = bool(
                driver.find_elements(By.XPATH, "//span[contains(normalize-space(.), '每日签到')]")
            )
            has_claim_button = bool(driver.find_elements(By.XPATH, self._DAILY_SIGN_CLAIM_XPATH))
            return has_daily_sign_span and has_claim_button

        try:
            return bool(wait.until(_probe))
        except TimeoutException:
            return False

    def _get_daily_sign_header_text(self) -> str:
        try:
            elements = self.ctx.driver.find_elements(By.XPATH, XPATH_CONFIG["SIGN_IN_HEADER"])
            if not elements:
                return ""
            header = elements[0]
            raw_text = (header.get_attribute("innerText") or header.text or "").strip()
            return re.sub(r"\s+", " ", raw_text).strip()
        except Exception:
            return ""

    def _get_daily_sign_card_text(self) -> str:
        try:
            elements = self.ctx.driver.find_elements(By.XPATH, XPATH_CONFIG["SIGN_IN_CARD"])
            if not elements:
                return ""
            card = elements[0]
            raw_text = (card.get_attribute("innerText") or card.text or "").strip()
            return re.sub(r"\s+", " ", raw_text).strip()
        except Exception:
            return ""

    def _detect_daily_sign_done_pattern(self) -> str | None:
        header_text = self._get_daily_sign_header_text()
        for pattern in self._DAILY_SIGN_DONE_PATTERNS:
            if pattern in header_text:
                return pattern
        return None

    def _wait_daily_sign_done_pattern(self, timeout: int | None = None) -> str | None:
        if timeout is None:
            timeout = self._DAILY_SIGN_DONE_WAIT_SECONDS
        wait = WebDriverWait(self.ctx.driver, timeout, poll_frequency=0.5)
        try:
            return wait.until(lambda d: self._detect_daily_sign_done_pattern() or False)
        except TimeoutException:
            return None

    def handle_daily_reward(self, start_points: int) -> dict:
        user_label = self.ctx.config.display_name or self.ctx.config.rainyun_user
        opened = self.open()
        if not opened:
            logger.warning("用户 %s 奖励页 URL 未及时命中", user_label)
        if not self._wait_daily_sign_section_ready():
            self.ctx.driver.refresh()
            if not self._wait_daily_sign_section_ready(timeout=max(self.ctx.config.timeout, 15)):
                raise Exception("奖励页加载超时：未找到每日签到模块")
        done_pattern = self._detect_daily_sign_done_pattern()
        if done_pattern:
            logger.info("用户 %s 今日已签到（检测到：%s），跳过", user_label, done_pattern)
            current_points, earned = self._log_points(start_points)
            return {"status": "already_signed", "current_points": current_points, "earned": earned}
        try:
            earn = self.ctx.wait.until(
                EC.element_to_be_clickable((By.XPATH, XPATH_CONFIG["SIGN_IN_BTN"]))
            )
            logger.info("用户 %s 点击领取奖励", user_label)
            try:
                earn.click()
            except Exception:
                self.ctx.driver.execute_script("arguments[0].click();", earn)
        except TimeoutException:
            done_pattern = self._detect_daily_sign_done_pattern()
            if done_pattern:
                logger.info("用户 %s 今日已签到（检测到：%s）", user_label, done_pattern)
                current_points, earned = self._log_points(start_points)
                return {
                    "status": "already_signed",
                    "current_points": current_points,
                    "earned": earned,
                }
            raise Exception("未找到每日签到按钮")
        logger.info("用户 %s 处理验证码", user_label)
        try:
            self.ctx.wait.until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, "tcaptcha_iframe_dy"))
            )
            if not self.captcha_handler(self.ctx):
                raise Exception("验证码识别失败")
        except TimeoutException:
            logger.info("用户 %s 未触发验证码", user_label)
        finally:
            self.ctx.driver.switch_to.default_content()
        done_pattern = self._wait_daily_sign_done_pattern()
        if not done_pattern:
            raise Exception("验证码处理后未检测到完成状态")
        current_points, earned = self._log_points(start_points)
        logger.info("用户 %s 签到成功（检测到：%s）", user_label, done_pattern)
        return {"status": "signed", "current_points": current_points, "earned": earned}

    def _log_points(self, start_points: int) -> tuple[int | None, int | None]:
        user_label = self.ctx.config.display_name or self.ctx.config.rainyun_user
        try:
            current_points = self.ctx.api.get_user_points()
            earned = current_points - start_points
            logger.info(
                "用户 %s 当前剩余积分: %s (本次获得 %s 分)",
                user_label,
                current_points,
                earned,
            )
            return current_points, earned
        except Exception:
            logger.info("用户 %s 无法获取积分信息", user_label)
            return None, None
