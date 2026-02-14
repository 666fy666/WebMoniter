"""验证码处理（参考 Rainyun-Qiandao main.py）"""

import logging
import os
import random
import re
import time
from dataclasses import dataclass
from itertools import combinations, permutations

import cv2
import numpy as np
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.support import expected_conditions as EC

from tasks.rainyun.browser.locators import XPATH_CONFIG
from tasks.rainyun.browser.session import RuntimeContext
from tasks.rainyun.config_adapter import RainyunRunConfig
from tasks.rainyun.utils.http import download_bytes, download_to_file
from tasks.rainyun.utils.image import (
    decode_image_bytes,
    encode_image_bytes,
    normalize_gray,
    split_sprite_image,
)

logger = logging.getLogger(__name__)

_LOG_PREFIX = ""


def _set_log_user(user: str | None) -> None:
    global _LOG_PREFIX
    _LOG_PREFIX = f"用户 {user} " if user else ""


def _get_log_prefix() -> str:
    return _LOG_PREFIX


class CaptchaRetryableError(Exception):
    pass


@dataclass(frozen=True)
class MatchResult:
    positions: list[tuple[int, int]]
    similarities: list[float]
    method: str


def temp_path(ctx: RuntimeContext, filename: str) -> str:
    return os.path.join(ctx.temp_dir, filename)


def clear_temp_dir(temp_dir: str) -> None:
    if not os.path.exists(temp_dir):
        return
    for filename in os.listdir(temp_dir):
        path = os.path.join(temp_dir, filename)
        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)


def _download_image_bytes(
    url: str, config: RainyunRunConfig, fallback_path: str | None = None
) -> bytes:
    try:
        return download_bytes(
            url,
            timeout=config.download_timeout,
            max_retries=config.download_max_retries,
            retry_delay=config.download_retry_delay,
        )
    except RuntimeError as e:
        if fallback_path and download_to_file(url, fallback_path, config):
            with open(fallback_path, "rb") as f:
                return f.read()
        raise CaptchaRetryableError(f"验证码图片下载失败: {e}")


def get_url_from_style(style: str) -> str:
    if not style:
        raise ValueError("style 属性为空")
    m = re.search(r"url\(([^)]+)\)", style, re.IGNORECASE)
    if not m:
        raise ValueError(f"无法解析 URL: {style}")
    return m.group(1).strip().strip('"').strip("'")


def get_width_from_style(style: str) -> float:
    if not style:
        raise ValueError("style 为空")
    m = re.search(r"width\s*:\s*([\d.]+)px", style, re.IGNORECASE)
    if not m:
        raise ValueError(f"无法解析宽度: {style}")
    return float(m.group(1))


def get_height_from_style(style: str) -> float:
    if not style:
        raise ValueError("style 为空")
    m = re.search(r"height\s*:\s*([\d.]+)px", style, re.IGNORECASE)
    if not m:
        raise ValueError(f"无法解析高度: {style}")
    return float(m.group(1))


def get_element_size(element) -> tuple[float, float]:
    size = element.size or {}
    w, h = size.get("width", 0), size.get("height", 0)
    if not w or not h:
        raise ValueError("无法解析元素尺寸")
    return float(w), float(h)


def detect_captcha_bboxes(
    ctx: RuntimeContext,
    captcha_bytes: bytes,
    captcha_image: np.ndarray,
) -> list[tuple[int, int, int, int]]:
    payloads = [
        ("raw", captcha_bytes),
        ("reencode", encode_image_bytes(captcha_image, "验证码背景图")),
    ]
    for label, payload in payloads:
        try:
            bboxes = ctx.det.detection(payload)
            if bboxes:
                return bboxes
        except Exception as e:
            logger.warning("验证码检测失败(%s): %s", label, e)
    return []


def compute_sift_similarity(sprite: np.ndarray, spec: np.ndarray, sift) -> float:
    sprite_gray = normalize_gray(sprite)
    spec_gray = normalize_gray(spec)
    kp1, des1 = sift.detectAndCompute(sprite_gray, None)
    kp2, des2 = sift.detectAndCompute(spec_gray, None)
    if des1 is None or des2 is None:
        return 0.0
    bf = cv2.BFMatcher()
    matches = bf.knnMatch(des1, des2, k=2)
    good = [
        m for m_n in matches if len(m_n) == 2 for m, n in [m_n] if m.distance < 0.8 * n.distance
    ]
    if not matches or len(good) == 0:
        return 0.0
    return len(good) / len(matches)


def compute_template_similarity(sprite: np.ndarray, spec: np.ndarray) -> float:
    sprite_gray = normalize_gray(sprite)
    spec_gray = normalize_gray(spec)
    if sprite_gray is None or spec_gray is None or sprite_gray.size == 0 or spec_gray.size == 0:
        return 0.0
    if sprite_gray.shape != spec_gray.shape:
        sprite_gray = cv2.resize(sprite_gray, (spec_gray.shape[1], spec_gray.shape[0]))
    result = cv2.matchTemplate(spec_gray, sprite_gray, cv2.TM_CCOEFF_NORMED)
    return float(np.max(result))


def build_match_result(
    background: np.ndarray,
    sprites: list[np.ndarray],
    bboxes: list[tuple[int, int, int, int]],
    similarity_fn,
    method: str,
) -> MatchResult | None:
    if not bboxes or len(sprites) != 3:
        return None
    valid_specs: list[tuple[tuple[int, int], np.ndarray]] = []
    for bbox in bboxes:
        if len(bbox) != 4:
            continue
        x1, y1, x2, y2 = map(int, bbox)
        if x2 <= x1 or y2 <= y1:
            continue
        spec = background[y1:y2, x1:x2]
        if spec.size == 0:
            continue
        center = (int((x1 + x2) / 2), int((y1 + y2) / 2))
        valid_specs.append((center, spec))
    if not valid_specs:
        return None
    best_positions: list[tuple[int, int] | None] = [None, None, None]
    best_scores: list[float | None] = [None, None, None]
    if len(valid_specs) < len(sprites):
        for center, spec in valid_specs:
            for i, sprite in enumerate(sprites):
                if sprite is None or sprite.size == 0:
                    continue
                sim = similarity_fn(sprite, spec)
                if best_scores[i] is None or sim > (best_scores[i] or 0):
                    best_scores[i] = sim
                    best_positions[i] = center
    else:
        sim_matrix = []
        for sprite in sprites:
            row = []
            for _, spec in valid_specs:
                if sprite is None or sprite.size == 0:
                    row.append(0.0)
                else:
                    row.append(similarity_fn(sprite, spec))
            sim_matrix.append(row)
        best_key = None
        best_perm = None
        best_scores_local = None
        for chosen in combinations(range(len(valid_specs)), len(sprites)):
            for perm in permutations(chosen):
                scores = [sim_matrix[i][perm[i]] for i in range(len(sprites))]
                key = (min(scores), sum(scores) / len(scores), sum(scores))
                if best_key is None or key > best_key:
                    best_key = key
                    best_perm = perm
                    best_scores_local = scores
        if best_perm is not None and best_scores_local is not None:
            for i, bbox_idx in enumerate(best_perm):
                center, _ = valid_specs[bbox_idx]
                best_positions[i] = center
                best_scores[i] = best_scores_local[i]
    if any(p is None for p in best_positions):
        return None
    return MatchResult(
        positions=[p for p in best_positions if p is not None],
        similarities=[float(s) if s is not None else 0.0 for s in best_scores],
        method=method,
    )


class SiftMatcher:
    name = "sift"

    def __init__(self):
        self._sift = cv2.SIFT_create() if hasattr(cv2, "SIFT_create") else None

    def match(self, background, sprites, bboxes):
        if not self._sift:
            return None
        return build_match_result(
            background,
            sprites,
            bboxes,
            lambda s, sp: compute_sift_similarity(s, sp, self._sift),
            self.name,
        )


class TemplateMatcher:
    name = "template"

    def match(self, background, sprites, bboxes):
        return build_match_result(
            background,
            sprites,
            bboxes,
            compute_template_similarity,
            self.name,
        )


class StrategyCaptchaSolver:
    def __init__(self, matchers):
        self.matchers = matchers

    def solve(self, background, sprites, bboxes):
        for matcher in self.matchers:
            result = matcher.match(background, sprites, bboxes)
            if result:
                return result
        return None


def save_captcha_samples(
    captcha_image: np.ndarray | None,
    sprites: list[np.ndarray],
    *,
    config: RainyunRunConfig,
    reason: str,
) -> None:
    if not config.captcha_save_samples:
        return
    try:
        base_dir = os.path.join("temp", "captcha_samples")
        os.makedirs(base_dir, exist_ok=True)
        sample_dir = os.path.join(
            base_dir, f"{time.strftime('%Y%m%d-%H%M%S')}-{reason}-{random.randint(1000, 9999)}"
        )
        os.makedirs(sample_dir, exist_ok=True)
        if captcha_image is not None and captcha_image.size > 0:
            cv2.imwrite(os.path.join(sample_dir, "background.jpg"), captcha_image)
        for i, sprite in enumerate(sprites, 1):
            if sprite is not None and sprite.size > 0:
                cv2.imwrite(os.path.join(sample_dir, f"sprite_{i}.jpg"), sprite)
    except Exception as e:
        logger.warning("保存验证码样本失败: %s", e)


def check_captcha(
    ctx: RuntimeContext, captcha_image: np.ndarray, sprites: list[np.ndarray]
) -> bool:
    if len(sprites) != 3:
        return False
    low_confidence = 0
    for i, sprite in enumerate(sprites, 1):
        sb = encode_image_bytes(sprite, f"验证码小图{i}")
        if ctx.ocr.classification(sb) in ["0", "1"]:
            low_confidence += 1
    if low_confidence >= 2:
        return False
    return True


def check_answer(result: MatchResult, min_similarity: float = 0.25) -> bool:
    if not result.positions or len(result.positions) < 3:
        return False
    if len(result.positions) != len(set(result.positions)):
        return False
    min_match = min(result.similarities) if result.similarities else 0.0
    return min_match >= min_similarity


def download_captcha_assets(ctx: RuntimeContext) -> tuple[bytes, np.ndarray, list[np.ndarray]]:
    clear_temp_dir(ctx.temp_dir)
    slide_bg = ctx.wait.until(EC.visibility_of_element_located(XPATH_CONFIG["CAPTCHA_BG"]))
    img1_url = get_url_from_style(slide_bg.get_attribute("style") or "")
    captcha_bytes = _download_image_bytes(img1_url, ctx.config, temp_path(ctx, "captcha.jpg"))
    sprite_el = ctx.wait.until(
        EC.visibility_of_element_located(XPATH_CONFIG["CAPTCHA_IMG_INSTRUCTION"])
    )
    img2_url = sprite_el.get_attribute("src") or ""
    sprite_bytes = _download_image_bytes(img2_url, ctx.config, temp_path(ctx, "sprite.jpg"))
    captcha_image = decode_image_bytes(captcha_bytes, "验证码背景图")
    sprite_image = decode_image_bytes(sprite_bytes, "验证码小图")
    sprites = split_sprite_image(sprite_image)
    return captcha_bytes, captcha_image, sprites


def process_captcha(ctx: RuntimeContext, retry_count: int = 0) -> bool:
    prev_prefix = _get_log_prefix()
    _set_log_user(ctx.config.display_name or ctx.config.rainyun_user)
    prefix = _get_log_prefix()

    def refresh_captcha() -> bool:
        try:
            reload_btn = ctx.driver.find_element(*XPATH_CONFIG["CAPTCHA_RELOAD"])
            time.sleep(2)
            reload_btn.click()
            time.sleep(2)
            return True
        except Exception as e:
            logger.error("%s无法刷新验证码: %s", prefix, e)
            return False

    solver = StrategyCaptchaSolver([SiftMatcher(), TemplateMatcher()])
    current_retry = retry_count
    try:
        while True:
            if (
                not ctx.config.captcha_retry_unlimited
                and current_retry >= ctx.config.captcha_retry_limit
            ):
                logger.error("%s验证码重试次数过多", prefix)
                return False
            try:
                captcha_bytes, captcha_image, sprites = download_captcha_assets(ctx)
                if not check_captcha(ctx, captcha_image, sprites):
                    if not refresh_captcha():
                        return False
                    current_retry += 1
                    continue
                bboxes = detect_captcha_bboxes(ctx, captcha_bytes, captcha_image)
                if not bboxes:
                    save_captcha_samples(
                        captcha_image, sprites, config=ctx.config, reason="no_bboxes"
                    )
                    if not refresh_captcha():
                        return False
                    current_retry += 1
                    continue
                result = solver.solve(captcha_image, sprites, bboxes)
                if result and check_answer(result):
                    for x, y in result.positions:
                        slide_bg = ctx.wait.until(
                            EC.visibility_of_element_located(XPATH_CONFIG["CAPTCHA_BG"])
                        )
                        style = slide_bg.get_attribute("style")
                        width_raw, height_raw = captcha_image.shape[1], captcha_image.shape[0]
                        try:
                            width = get_width_from_style(style or "")
                            height = get_height_from_style(style or "")
                        except ValueError:
                            width, height = get_element_size(slide_bg)
                        x_offset, y_offset = float(-width / 2), float(-height / 2)
                        final_x = int(x_offset + x / width_raw * width)
                        final_y = int(y_offset + y / height_raw * height)
                        ActionChains(ctx.driver).move_to_element_with_offset(
                            slide_bg, final_x, final_y
                        ).click().perform()
                    confirm = ctx.wait.until(
                        EC.element_to_be_clickable(XPATH_CONFIG["CAPTCHA_SUBMIT"])
                    )
                    confirm.click()
                    time.sleep(5)
                    result_el = ctx.wait.until(
                        EC.visibility_of_element_located(XPATH_CONFIG["CAPTCHA_OP"])
                    )
                    if "show-success" in (result_el.get_attribute("class") or ""):
                        return True
                save_captcha_samples(
                    captcha_image, sprites, config=ctx.config, reason="submit_failed"
                )
            except (TimeoutException, ValueError, CaptchaRetryableError) as e:
                logger.error("%s验证码异常: %s", prefix, e)
            if not refresh_captcha():
                return False
            current_retry += 1
    finally:
        _set_log_user(prev_prefix or None)
    return False
