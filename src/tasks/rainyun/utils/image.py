"""图片工具"""

import io

import numpy as np

# cv2 可能因环境冲突（如 ddddocr）而异常，优先尝试导入
try:
    import cv2

    _HAS_CV2 = hasattr(cv2, "imdecode")
except Exception:
    cv2 = None  # type: ignore
    _HAS_CV2 = False


def decode_image_bytes(image_bytes: bytes, label: str) -> np.ndarray:
    if not image_bytes:
        raise ValueError(f"{label} 数据为空，无法解码")
    if _HAS_CV2 and cv2 is not None:
        buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is not None:
            return image
    # cv2 不可用或解码失败时，使用 Pillow 后备（返回 BGR 格式以兼容后续 cv2 逻辑）
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    return arr[:, :, ::-1]  # RGB -> BGR


def encode_image_bytes(image: np.ndarray, label: str) -> bytes:
    if image is None or image.size == 0:
        raise ValueError(f"{label} 为空，无法编码")
    if _HAS_CV2 and cv2 is not None:
        success, encoded = cv2.imencode(".jpg", image)
        if success:
            return encoded.tobytes()
    # Pillow 后备：BGR -> RGB
    from PIL import Image

    rgb = image[:, :, ::-1] if len(image.shape) == 3 and image.shape[2] >= 3 else image
    pil_img = Image.fromarray(rgb)
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG")
    return buf.getvalue()


def split_sprite_image(sprite: np.ndarray) -> list[np.ndarray]:
    if sprite is None or sprite.size == 0:
        raise ValueError("验证码小图为空，无法切分")
    width = sprite.shape[1]
    if width < 3:
        raise ValueError("验证码小图宽度异常，无法切分")
    step = width // 3
    if step == 0:
        raise ValueError("验证码小图切分宽度为 0")
    return [
        sprite[:, 0:step],
        sprite[:, step : step * 2],
        sprite[:, step * 2 : width],
    ]


def normalize_gray(image: np.ndarray) -> np.ndarray:
    if image is None:
        return image
    if len(image.shape) == 2:
        return image
    if _HAS_CV2 and cv2 is not None:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Pillow 后备：BGR -> RGB -> L
    from PIL import Image

    rgb = image[:, :, ::-1]
    pil_img = Image.fromarray(rgb)
    return np.array(pil_img.convert("L"), dtype=np.uint8)
