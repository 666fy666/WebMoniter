"""登录状态与验证码终止行为回归；不模拟真实模型识别成功率。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.tasks import ikuuu_checkin as module
from src.tasks.ikuuu_captcha import (
    CaptchaKind,
    IkuuuCaptchaUnavailableError,
    IkuuuLoginRejectedError,
    classify_prompt,
    require_supported_challenge,
)


def config():
    return module.CheckinConfig(True, "ikuuu.win", "test@example.com", "test-only", "08:00", [], [])


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("请在下图依次点击 月桂酸", CaptchaKind.WORD),
        ("选 3 个符合右图的图片", CaptchaKind.NINE),
        ("请完成验证", CaptchaKind.UNKNOWN),
    ],
)
def test_challenge_classification(text, kind):
    assert classify_prompt(text) == kind
    panel = SimpleNamespace(
        text=text, is_displayed=lambda: True, find_elements=lambda *args: [object()]
    )
    driver = SimpleNamespace(find_elements=lambda *args: [panel])
    if kind in (CaptchaKind.NINE, CaptchaKind.WORD):
        require_supported_challenge(driver)
    else:
        with pytest.raises(IkuuuCaptchaUnavailableError, match=kind.value):
            require_supported_challenge(driver)


def test_hidden_challenge_does_not_block_login():
    panel = SimpleNamespace(is_displayed=lambda: False)
    require_supported_challenge(SimpleNamespace(find_elements=lambda *args: [panel]))


@pytest.mark.parametrize(
    ("url", "logout", "authenticated"),
    [
        ("https://ikuuu.win/auth/login", True, False),
        ("https://ikuuu.win/user", False, False),
        ("https://evil.test/user", True, False),
        ("https://ikuuu.win/user", True, True),
    ],
)
def test_authenticated_page_requires_origin_path_and_logout(url, logout, authenticated):
    driver = SimpleNamespace(
        current_url=url, find_elements=lambda *args: [SimpleNamespace(is_displayed=lambda: logout)]
    )
    assert module._authenticated_user_page(driver, config()) is authenticated


@pytest.mark.asyncio
async def test_captcha_failure_does_not_rediscover_domain_or_retry(monkeypatch):
    from src.core import browser_process

    login = AsyncMock(
        side_effect=browser_process.BrowserProcessError("IkuuuCaptchaUnavailableError")
    )
    discover = AsyncMock()
    monkeypatch.setattr(browser_process, "run_browser", login)
    monkeypatch.setattr(module, "_extract_ikuuu_domain_with_retry", discover)
    with pytest.raises(IkuuuCaptchaUnavailableError):
        await module._login_and_get_cookie(None, config())
    login.assert_called_once()
    discover.assert_not_awaited()


@pytest.mark.parametrize("outcome", ["success", "anonymous", "captcha", "bad_password"])
def test_browser_login_and_cleanup(monkeypatch, outcome):
    pytest.importorskip("selenium")
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.support import ui

    class Element:
        text = ""

        def is_displayed(self):
            return True

        def is_enabled(self):
            return True

        def clear(self):
            pass

        def send_keys(self, value):
            pass

        def click(self):
            if outcome == "success":
                driver.current_url = "https://ikuuu.win/user"

    element = Element()
    driver = Mock()
    driver.current_url = "https://ikuuu.win/auth/login"
    driver.find_element.return_value = element
    driver.get_cookies.return_value = [{"name": "session", "value": "test-only"}]

    def find_elements(by, selector):
        if "logout" in selector:
            return [element] if driver.current_url.endswith("/user") else []
        if "geetest_panel" in selector and outcome == "captcha":
            return [SimpleNamespace(text="请在下图依次点击", is_displayed=lambda: True)]
        if "alert-danger" in selector and outcome == "bad_password":
            return [SimpleNamespace(text="账号或密码错误", is_displayed=lambda: True)]
        return []

    driver.find_elements.side_effect = find_elements

    class Wait:
        def __init__(self, browser, timeout):
            self.browser = browser

        def until(self, predicate):
            result = predicate(self.browser)
            if not result:
                raise TimeoutException()
            return result

    monkeypatch.setattr(ui, "WebDriverWait", Wait)
    monkeypatch.setattr(module, "_default_chrome_binary", lambda: "/test/chrome")
    monkeypatch.setattr(module, "_create_ikuuu_webdriver", lambda *args: driver)
    if outcome != "captcha":
        monkeypatch.setattr(module, "CaptchaSolver", Mock)
    if outcome == "success":
        assert module._login_and_get_cookie_sync(config()) == "session=test-only"
    else:
        with pytest.raises(IkuuuLoginRejectedError):
            module._login_and_get_cookie_sync(config())
        driver.get_cookies.assert_not_called()
    driver.quit.assert_called_once()
