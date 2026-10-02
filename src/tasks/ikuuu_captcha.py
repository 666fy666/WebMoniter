"""iKuuu 极验挑战处理；每次登录共用五轮上限，不保存截图。"""

import math
import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit

MAX_CHALLENGE_ROUNDS = 5


class CaptchaKind(str, Enum):
    WORD = "文字顺序点选"
    NINE = "九宫格图片选择"
    UNKNOWN = "未知图片验证"


class IkuuuLoginRejectedError(RuntimeError):
    """不应通过更换域名或重复登录恢复的失败。"""


class IkuuuCaptchaUnavailableError(IkuuuLoginRejectedError):
    """验证码不支持、模型缺失或挑战耗尽，停止自动登录。"""


def classify_prompt(text: str) -> CaptchaKind:
    compact = "".join(text.split())
    if "依次点击" in compact or "按顺序点击" in compact:
        return CaptchaKind.WORD
    if "选" in compact and "图片" in compact:
        return CaptchaKind.NINE
    return CaptchaKind.UNKNOWN


def _prompt_text(element) -> str:
    # 刷新动画会暂时隐藏提示，Selenium 的 .text 此时为空；DOM 文本仍保留题型。
    getter = getattr(element, "get_attribute", None)
    text = getter("textContent") if getter is not None else None
    return text if isinstance(text, str) and text.strip() else element.text


def visible_challenge(driver) -> CaptchaKind | None:
    unknown = False
    for element in driver.find_elements(
        "css selector",
        ".geetest_panel, .geetest_box, .geetest_popup_wrap, .geetest_window",
    ):
        if not element.is_displayed():
            continue
        kind = classify_prompt(_prompt_text(element))
        if kind != CaptchaKind.UNKNOWN:
            return kind
        if element.find_elements(
            "css selector",
            ".geetest_item_wrap, .geetest_canvas_bg, .geetest_bg, .geetest_table_box",
        ):
            unknown = True
    return CaptchaKind.UNKNOWN if unknown else None


def require_supported_challenge(driver) -> None:
    kind = visible_challenge(driver)
    if kind == CaptchaKind.UNKNOWN:
        raise IkuuuCaptchaUnavailableError(
            f"检测到极验{kind.value}；当前页面或题型不支持，自动登录已停止。"
        )


@dataclass(frozen=True)
class Challenge:
    title: str
    background: str
    prompt: str | tuple[str, ...]
    count: int
    kind: CaptchaKind = CaptchaKind.NINE


def _panel(driver):
    for panel in driver.find_elements("css selector", ".geetest_box, .geetest_panel"):
        if panel.is_displayed() and classify_prompt(_prompt_text(panel)) != CaptchaKind.UNKNOWN:
            return panel
    return None


def _snapshot(driver) -> Challenge | None:
    from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

    try:
        if _is_loading(driver):
            return None
        return _read_snapshot(driver)
    except (NoSuchElementException, StaleElementReferenceException):
        # 换题时提示与背景会分批替换，等待完整快照后再识别。
        return None


def _is_loading(driver) -> bool:
    return any(
        element.is_displayed()
        for element in driver.find_elements(
            "css selector",
            ".geetest_captcha.geetest_load, .geetest_captcha.geetest_nextReady",
        )
    )


def _read_snapshot(driver) -> Challenge | None:
    require_supported_challenge(driver)
    panel = _panel(driver)
    if panel is None:
        return None
    title = _prompt_text(panel.find_element("css selector", ".geetest_text_tips"))
    if classify_prompt(title) == CaptchaKind.WORD:
        images = panel.find_elements("css selector", ".geetest_ques_tips img")
        backgrounds = panel.find_elements("css selector", ".geetest_bg")
        if len(images) != 3 or len(backgrounds) != 1:
            return None
        match = re.fullmatch(
            r"url\([\'\"]?(.*?)[\'\"]?\)",
            backgrounds[0].value_of_css_property("background-image"),
        )
        if match is None:
            return None
        return Challenge(
            title,
            match[1],
            tuple(e.get_attribute("src") for e in images),
            len(images),
            CaptchaKind.WORD,
        )
    count = re.search(r"选\s*(\d+)", title)
    items = panel.find_elements("css selector", ".geetest_item_img")
    prompts = panel.find_elements("css selector", ".geetest_ques_tips img")
    selected = panel.find_elements("css selector", ".geetest_item_ghost.geetest_selected")
    # 页面提示显示的是剩余数量，每点一格会从 3 递减，不能当作换题。
    total = int(count[1]) + len(selected) if count else 0
    # 提交/失败动画可能先清除选中标记再更新提示；此时等待明确结果或下一题。
    if count is not None and ((int(count[1]) == 0 and total < 3) or total > 3):
        return None
    if len(items) != 9 or len(prompts) != 1:
        return None
    if total != 3:
        raise IkuuuCaptchaUnavailableError("九宫格页面结构变化或选图数量不支持")
    backgrounds = [item.value_of_css_property("background-image") for item in items]
    if len(set(backgrounds)) != 1:
        raise IkuuuCaptchaUnavailableError("九宫格图片布局不支持")
    match = re.fullmatch(r"url\([\'\"]?(.*?)[\'\"]?\)", backgrounds[0])
    if match is None:
        raise IkuuuCaptchaUnavailableError("九宫格图片尚未加载")
    return Challenge(
        re.sub(r"选\s*\d+", f"选 {total}", title),
        match[1],
        prompts[0].get_attribute("src"),
        total,
    )


def _image_bytes(url: str) -> bytes:
    import requests

    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"static.geetest.com", "static.geetest.net"}
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise IkuuuCaptchaUnavailableError("验证码图片地址不在支持范围")
    # 独立请求，不携带登录 Cookie，也不跟随图片地址重定向。
    with requests.get(url, timeout=(5, 10), allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            raise IkuuuCaptchaUnavailableError("验证码图片获取失败")
        content = bytearray()
        for block in response.iter_content(64 * 1024):
            content.extend(block)
            if len(content) > 2 * 1024 * 1024:
                raise IkuuuCaptchaUnavailableError("验证码图片大小异常")
        return bytes(content)


def _verified(driver) -> bool:
    for element in driver.find_elements(
        "css selector", ".geetest_success, .geetest_success_radar_tip, .geetest_success_radar"
    ):
        if element.is_displayed():
            return True
    return False


def _result(driver, previous: Challenge) -> str | bool:
    if _verified(driver):
        return "success"
    for element in driver.find_elements("css selector", ".geetest_result_tips, .geetest_tip"):
        if element.is_displayed() and any(x in element.text for x in ("失败", "重试", "错误")):
            return "failed"
    current = _snapshot(driver)
    if current is not None and current != previous:
        return "changed"
    return False


def _predict_challenge(challenge: Challenge):
    from src.tasks.ikuuu_recognition import recognize_nine, recognize_word

    background = _image_bytes(challenge.background)
    if challenge.kind == CaptchaKind.WORD:
        return recognize_word(background, [_image_bytes(url) for url in challenge.prompt])
    return recognize_nine(background, _image_bytes(challenge.prompt), challenge.count)


def word_click_offset(point: tuple[float, float], width: float, height: float) -> tuple[int, int]:
    if width <= 0 or height <= 0 or any(not math.isfinite(v) or not 0 < v < 1 for v in point):
        raise IkuuuCaptchaUnavailableError("文字点击位置超出图片范围")
    return round((point[0] - 0.5) * width), round((point[1] - 0.5) * height)


def _click_choice(driver, challenge: Challenge, choice) -> None:
    if challenge.kind == CaptchaKind.WORD:
        from selenium.webdriver.common.action_chains import ActionChains

        image = _panel(driver).find_element("css selector", ".geetest_bg")
        width, height = driver.execute_script(
            "const r=arguments[0].getBoundingClientRect(); return [r.width,r.height];", image
        )
        x, y = word_click_offset(choice, width, height)
        # 等待点击标记的入场动画，避免下一次点击被动画期间的控件状态吞掉。
        ActionChains(driver).move_to_element_with_offset(image, x, y).click().pause(0.35).perform()
    else:
        if not isinstance(choice, int) or not 0 <= choice < 9:
            raise IkuuuCaptchaUnavailableError("九宫格识别结果异常")
        items = _panel(driver).find_elements("css selector", ".geetest_item")
        if len(items) != 9:
            raise IkuuuCaptchaUnavailableError("九宫格点击区域不完整")
        items[choice].click()


class CaptchaSolver:
    def __init__(self):
        self.rounds = 0

    def solve_if_present(self, driver, *, wait_for_challenge: bool = False) -> bool:
        from selenium.common.exceptions import TimeoutException, WebDriverException
        from selenium.webdriver.support.ui import WebDriverWait

        try:
            if wait_for_challenge:
                WebDriverWait(driver, 10).until(lambda d: _verified(d) or _snapshot(d))
            while not _verified(driver):
                challenge = _snapshot(driver)
                if challenge is None:
                    if self.rounds:
                        raise IkuuuCaptchaUnavailableError("图片挑战已消失，但未确认验证成功")
                    return False
                if self.rounds >= MAX_CHALLENGE_ROUNDS:
                    raise IkuuuCaptchaUnavailableError(
                        f"图片验证码已处理 {MAX_CHALLENGE_ROUNDS} 轮，停止本次登录"
                    )
                self.rounds += 1
                from src.tasks.ikuuu_recognition import RecognitionFailedError

                try:
                    selected = _predict_challenge(challenge)
                except RecognitionFailedError:
                    selected = None
                except IkuuuCaptchaUnavailableError:
                    raise
                except (ImportError, OSError, ValueError) as exc:
                    raise IkuuuCaptchaUnavailableError(
                        "本地识别模型缺失、损坏或图片读取失败；请检查完整镜像及模型目录"
                    ) from exc
                result = "failed"
                if selected is not None:
                    if len(selected) != challenge.count or len(set(selected)) != challenge.count:
                        raise IkuuuCaptchaUnavailableError("图片识别结果数量或唯一性异常")
                    for choice in selected:
                        # 每次点击前重新核对题目；刷新后不使用旧坐标或旧元素。
                        if _snapshot(driver) != challenge:
                            result = "changed"
                            break
                        _click_choice(driver, challenge, choice)
                    else:
                        try:
                            if challenge.kind == CaptchaKind.WORD:
                                WebDriverWait(driver, 5).until(
                                    lambda d: _snapshot(d) != challenge
                                    or len(
                                        _panel(d).find_elements("css selector", ".geetest_mark_no")
                                    )
                                    == challenge.count
                                )
                            for button in driver.find_elements("css selector", ".geetest_submit"):
                                if (
                                    button.is_displayed()
                                    and button.is_enabled()
                                    and "geetest_disable"
                                    not in (button.get_attribute("class") or "")
                                ):
                                    if _snapshot(driver) == challenge:
                                        button.click()
                                    break
                            result = WebDriverWait(driver, 10).until(
                                lambda d: _result(d, challenge)
                            )
                        except TimeoutException:
                            result = "timeout"
                if result == "success":
                    return True
                if result == "changed":
                    WebDriverWait(driver, 10).until(lambda d: _verified(d) or _snapshot(d))
                    continue
                if self.rounds >= MAX_CHALLENGE_ROUNDS:
                    raise IkuuuCaptchaUnavailableError(
                        f"图片验证码已处理 {MAX_CHALLENGE_ROUNDS} 轮，未通过验证"
                    )
                if selected is not None:
                    try:
                        # 极验可能在失败后自动换题，避免手动刷新与自动请求相互覆盖。
                        WebDriverWait(driver, 2).until(
                            lambda d: (current := _snapshot(d)) is not None and current != challenge
                        )
                        continue
                    except TimeoutException:
                        pass
                refresh = next(
                    (
                        button
                        for button in driver.find_elements("css selector", ".geetest_refresh")
                        if button.is_displayed() and button.tag_name == "button"
                    ),
                    None,
                )
                if refresh is None:
                    raise IkuuuCaptchaUnavailableError("未确认验证码成功，且无法刷新挑战")
                refresh.click()
                WebDriverWait(driver, 10).until(
                    lambda d: (current := _snapshot(d)) is not None and current != challenge
                )
            return True
        except IkuuuLoginRejectedError:
            raise
        except (TimeoutException, WebDriverException) as exc:
            raise IkuuuCaptchaUnavailableError(
                "验证码页面等待超时或发生变化，停止本次登录"
            ) from exc
        except Exception as exc:
            # 验证码错误不能落入外层域名发现和登录重试。
            raise IkuuuCaptchaUnavailableError("本地验证码处理失败，停止本次登录") from exc
