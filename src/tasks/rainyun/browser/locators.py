"""页面定位符（参考 Rainyun-Qiandao）"""

from selenium.webdriver.common.by import By

XPATH_CONFIG = {
    "LOGIN_BTN": "//button[@type='submit' and contains(., '登') and contains(., '录')]",
    "SIGN_IN_CARD": "//div[contains(@class, 'card') and .//div[contains(@class, 'card-header') and .//span[contains(normalize-space(.), '每日签到')]]]",
    "SIGN_IN_HEADER": "//div[contains(@class, 'card-header') and .//span[contains(normalize-space(.), '每日签到')]]",
    "SIGN_IN_BTN": "//div[contains(@class, 'card-header') and .//span[contains(normalize-space(.), '每日签到')]]//*[self::a or self::button][contains(normalize-space(.), '领取奖励') or contains(normalize-space(.), '去完成') or contains(normalize-space(.), '去签到')]",
    "CAPTCHA_SUBMIT": (By.XPATH, "//div[@id='tcStatus']/div[2]/div[2]/div/div"),
    "CAPTCHA_RELOAD": (By.ID, "reload"),
    "CAPTCHA_BG": (By.ID, "slideBg"),
    "CAPTCHA_OP": (By.ID, "tcOperation"),
    "CAPTCHA_IMG_INSTRUCTION": (By.XPATH, "//div[@id='instruction']//img"),
}
