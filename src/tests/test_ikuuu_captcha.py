"""控制流程测试不代替真实图片准确率评估。"""

import io
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.tasks import ikuuu_captcha as captcha
from src.tasks import ikuuu_models as models
from src.tasks import ikuuu_recognition as recognition


@pytest.fixture
def browser(monkeypatch):
    pytest.importorskip("selenium")
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.support import ui

    class Wait:
        def __init__(self, driver, timeout):
            self.driver = driver

        def until(self, predicate):
            result = predicate(self.driver)
            if not result:
                raise TimeoutException()
            return result

    monkeypatch.setattr(ui, "WebDriverWait", Wait)
    challenge = captcha.Challenge("选 3 个符合右图的图片", "background-a", "prompt-a", 3)
    state = SimpleNamespace(challenge=challenge, verified=False, reads=[])
    items = [Mock() for _ in range(9)]
    panel = Mock()
    panel.find_elements.return_value = items
    refresh = Mock()
    refresh.tag_name = "button"
    refresh.is_displayed.return_value = True

    def change():
        old = state.challenge
        state.challenge = captcha.Challenge(old.title, old.background + "x", old.prompt, 3)

    refresh.click.side_effect = change
    driver = Mock()
    driver.find_elements.side_effect = (
        lambda by, css: [refresh] if css == ".geetest_refresh" else []
    )
    monkeypatch.setattr(captcha, "_snapshot", lambda d: state.challenge)
    monkeypatch.setattr(captcha, "_verified", lambda d: state.verified)
    monkeypatch.setattr(captcha, "_panel", lambda d: panel)
    monkeypatch.setattr(captcha, "_image_bytes", lambda url: state.reads.append(url) or b"image")
    monkeypatch.setattr(recognition, "recognize_nine", Mock(return_value=[1, 3, 7]))
    return state, driver, items, refresh


def test_nine_success_clicks_only_selected_tiles(browser, monkeypatch):
    state, driver, items, refresh = browser
    monkeypatch.setattr(captcha, "_result", lambda *args: "success")
    assert captcha.CaptchaSolver().solve_if_present(driver)
    assert [i for i, item in enumerate(items) if item.click.called] == [1, 3, 7]
    refresh.click.assert_not_called()


def test_remaining_selection_count_does_not_change_challenge_fingerprint(monkeypatch):
    monkeypatch.setattr(captcha, "_is_loading", lambda d: False)
    item = Mock()
    item.value_of_css_property.return_value = 'url("https://static.geetest.com/background.jpg")'
    prompt = Mock()
    prompt.get_attribute.return_value = "https://static.geetest.com/prompt.png"
    panel = Mock()
    monkeypatch.setattr(captcha, "require_supported_challenge", lambda d: None)
    monkeypatch.setattr(captcha, "_panel", lambda d: panel)
    snapshots = []
    for selected in range(4):
        panel.find_element.return_value.text = f"选 {3 - selected} 个符合右图的图片"
        panel.find_elements.side_effect = lambda by, css: {
            ".geetest_item_img": [item] * 9,
            ".geetest_ques_tips img": [prompt],
            ".geetest_item_ghost.geetest_selected": [Mock()] * selected,
        }[css]
        snapshots.append(captcha._snapshot(Mock()))
    assert len(set(snapshots)) == 1


def test_refresh_discards_previous_images_and_stops_after_five_rounds(browser, monkeypatch):
    state, driver, items, refresh = browser
    monkeypatch.setattr(captcha, "_result", lambda *args: "failed")
    solver = captcha.CaptchaSolver()
    with pytest.raises(captcha.IkuuuCaptchaUnavailableError, match="5 轮"):
        solver.solve_if_present(driver)
    assert solver.rounds == 5
    assert refresh.click.call_count == 4
    assert state.reads[::2] == ["background-a" + "x" * n for n in range(5)]
    with pytest.raises(captcha.IkuuuCaptchaUnavailableError, match="5 轮"):
        solver.solve_if_present(driver)
    assert len(state.reads) == 10


def test_four_failures_can_still_succeed_on_fifth_challenge(browser, monkeypatch):
    _, driver, _, refresh = browser
    results = iter(["failed"] * 4 + ["success"])
    monkeypatch.setattr(captcha, "_result", lambda *args: next(results))
    solver = captcha.CaptchaSolver()
    assert solver.solve_if_present(driver)
    assert solver.rounds == 5
    assert refresh.click.call_count == 4


def test_refresh_during_inference_does_not_click_old_result(browser, monkeypatch):
    state, driver, items, refresh = browser
    calls = 0

    def recognize(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            refresh.click()
        return [1, 3, 7]

    monkeypatch.setattr(recognition, "recognize_nine", recognize)
    monkeypatch.setattr(captcha, "_result", lambda *args: "success")
    assert captcha.CaptchaSolver().solve_if_present(driver)
    assert calls == 2
    assert sum(item.click.call_count for item in items) == 3


def test_missing_model_stops_without_click_or_refresh(browser, monkeypatch):
    _, driver, items, refresh = browser
    monkeypatch.setattr(recognition, "recognize_nine", Mock(side_effect=FileNotFoundError()))
    with pytest.raises(captcha.IkuuuCaptchaUnavailableError, match="模型缺失"):
        captcha.CaptchaSolver().solve_if_present(driver)
    assert not any(item.click.called for item in items)
    refresh.click.assert_not_called()


def test_panel_disappearing_is_not_proof_of_success(browser, monkeypatch):
    state, driver, items, _ = browser
    items[7].click.side_effect = lambda: setattr(state, "challenge", None)
    monkeypatch.setattr(captcha, "_result", lambda *args: False)
    driver.find_elements.side_effect = lambda *args: []
    with pytest.raises(captcha.IkuuuCaptchaUnavailableError, match="未确认验证码成功"):
        captcha.CaptchaSolver().solve_if_present(driver)


def test_failure_message_takes_priority_over_changing_selection_dom(monkeypatch):
    driver = Mock()
    failure = Mock(text="验证失败 请重新尝试")
    failure.is_displayed.return_value = True
    driver.find_elements.return_value = [failure]
    monkeypatch.setattr(captcha, "_verified", lambda d: False)
    snapshot = Mock(side_effect=AssertionError("失败动画期间不读取选中数"))
    monkeypatch.setattr(captcha, "_snapshot", snapshot)
    assert captcha._result(driver, captcha.Challenge("title", "image", "prompt", 3)) == "failed"
    snapshot.assert_not_called()


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (300, 200, (-75, 50)),
        (600, 400, (-150, 100)),
        (150, 100, (-38, 25)),
    ],
)
def test_word_coordinates_follow_css_image_size(width, height, expected):
    assert captcha.word_click_offset((0.25, 0.75), width, height) == expected


@pytest.mark.parametrize("point", [(float("nan"), 0.5), (-0.1, 0.5), (0.5, 1.1)])
def test_word_invalid_coordinates_never_clicked(point):
    with pytest.raises(captcha.IkuuuCaptchaUnavailableError):
        captcha.word_click_offset(point, 300, 200)


def test_word_missing_candidates_refreshes_before_any_click(browser, monkeypatch):
    state, driver, _, refresh = browser
    state.challenge = captcha.Challenge(
        "请在下图依次点击", "background-a", ("one", "two", "three"), 3, captcha.CaptchaKind.WORD
    )

    # 保持题型，仅更换背景。
    def change():
        old = state.challenge
        state.challenge = captcha.Challenge(
            old.title, old.background + "x", old.prompt, old.count, old.kind
        )

    refresh.click.side_effect = change
    points = [(0.2, 0.3), (0.5, 0.6), (0.8, 0.4)]
    predictor = Mock(side_effect=[recognition.RecognitionFailedError("候选不足"), points])
    click = Mock()
    monkeypatch.setattr(captcha, "_predict_challenge", predictor)
    monkeypatch.setattr(captcha, "_click_choice", click)
    monkeypatch.setattr(
        captcha,
        "_panel",
        lambda d: SimpleNamespace(
            find_elements=lambda *args: [object()] * 3,
        ),
    )
    monkeypatch.setattr(captcha, "_result", lambda *args: "success")
    solver = captcha.CaptchaSolver()
    assert solver.solve_if_present(driver)
    assert solver.rounds == 2
    assert [args.args[2] for args in click.call_args_list] == points
    refresh.click.assert_called_once()


def test_word_and_nine_share_one_login_retry_budget(browser, monkeypatch):
    state, driver, _, _ = browser
    monkeypatch.setattr(captcha, "_result", lambda *args: "success")
    solver = captcha.CaptchaSolver()
    solver.rounds = 4
    assert solver.solve_if_present(driver)
    state.challenge = captcha.Challenge(
        "请在下图依次点击", "new-image", ("one", "two", "three"), 3, captcha.CaptchaKind.WORD
    )
    with pytest.raises(captcha.IkuuuCaptchaUnavailableError, match="5 轮"):
        solver.solve_if_present(driver)


def test_word_incomplete_click_markers_refresh_and_exhaust_budget(browser, monkeypatch):
    state, driver, _, refresh = browser
    challenge = captcha.Challenge(
        "请在下图依次点击", "background-a", ("one", "two", "three"), 3, captcha.CaptchaKind.WORD
    )
    state.challenge = challenge

    def change():
        state.challenge = captcha.Challenge(
            challenge.title,
            state.challenge.background + "x",
            challenge.prompt,
            3,
            captcha.CaptchaKind.WORD,
        )

    refresh.click.side_effect = change
    monkeypatch.setattr(
        captcha, "_predict_challenge", lambda c: [(0.2, 0.3), (0.5, 0.6), (0.8, 0.4)]
    )
    monkeypatch.setattr(captcha, "_click_choice", Mock())
    monkeypatch.setattr(
        captcha,
        "_panel",
        lambda d: SimpleNamespace(
            find_elements=lambda *args: [object()],
        ),
    )
    with pytest.raises(captcha.IkuuuCaptchaUnavailableError, match="5 轮"):
        captcha.CaptchaSolver().solve_if_present(driver)
    assert refresh.click.call_count == 4


def test_refresh_animation_keeps_word_type_from_dom_text():
    panel = Mock(text="")
    panel.get_attribute.return_value = "请在下图依次点击"
    panel.is_displayed.return_value = True
    driver = Mock()
    driver.find_elements.return_value = [panel]
    assert captcha.visible_challenge(driver) == captcha.CaptchaKind.WORD


def test_partial_dom_during_refresh_waits_for_complete_challenge(monkeypatch):
    pytest.importorskip("selenium")
    from selenium.common.exceptions import NoSuchElementException

    monkeypatch.setattr(captcha, "_is_loading", lambda d: False)
    monkeypatch.setattr(captcha, "_read_snapshot", Mock(side_effect=NoSuchElementException()))
    assert captcha._snapshot(Mock()) is None


def test_automatic_new_challenge_does_not_trigger_duplicate_refresh(browser, monkeypatch):
    state, driver, _, refresh = browser
    calls = 0

    def result(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            state.challenge = captcha.Challenge("选 3 个符合右图的图片", "new", "prompt-b", 3)
            return "failed"
        return "success"

    monkeypatch.setattr(captcha, "_result", result)
    solver = captcha.CaptchaSolver()
    assert solver.solve_if_present(driver)
    assert solver.rounds == 2
    refresh.click.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "http://static.geetest.com/image",
        "https://evil.test/image",
        "https://static.geetest.com.evil.test/image",
        "https://name@static.geetest.com/image",
        "https://static.geetest.com:8080/image",
    ],
)
def test_image_download_rejects_untrusted_origins(url):
    with pytest.raises(captcha.IkuuuCaptchaUnavailableError):
        captcha._image_bytes(url)


def test_image_download_never_follows_redirect_or_sends_browser_cookies(monkeypatch):
    import requests

    response = Mock(status_code=302)
    request = Mock()
    request.return_value.__enter__ = Mock(return_value=response)
    request.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(requests, "get", request)
    with pytest.raises(captcha.IkuuuCaptchaUnavailableError):
        captcha._image_bytes("https://static.geetest.com/image")
    assert request.call_args.kwargs == {
        "timeout": (5, 10),
        "allow_redirects": False,
        "stream": True,
    }


def test_model_checksum_failure_preserves_existing_file(tmp_path, monkeypatch):
    path = tmp_path / models.NINE_FILENAME
    path.write_bytes(b"previous")
    monkeypatch.setattr(models, "urlopen", lambda *a, **kw: io.BytesIO(b"invalid weights"))
    with pytest.raises(ValueError, match="SHA-256"):
        models.download_model(tmp_path)
    assert path.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [path]


def test_lazy_recognizer_reuses_model(monkeypatch):
    network = Mock()
    network.select.return_value = [0, 1, 2]
    factory = Mock(return_value=network)
    monkeypatch.setattr(recognition, "_recognizer", None)
    monkeypatch.setattr(recognition, "NineRecognizer", factory)
    assert recognition.recognize_nine(b"board", b"prompt") == [0, 1, 2]
    recognition.recognize_nine(b"board2", b"prompt2")
    factory.assert_called_once()
