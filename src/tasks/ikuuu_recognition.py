"""文字点选与九宫格的本地识别，按需加载 CPU ONNX 模型。"""

import io
import itertools
from pathlib import Path
from threading import Lock

from src.tasks.ikuuu_models import (
    WORD_DETECTION_FILENAME,
    WORD_MATCHING_FILENAME,
    model_directory,
    verified_model,
)


class NineRecognizer:
    def __init__(self, directory: Path | None = None):
        import numpy as np
        import onnxruntime as ort

        self.np = np
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.network = ort.InferenceSession(
            str(verified_model(directory or model_directory())),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )

    def select(self, background: bytes, prompt: bytes, count: int = 3) -> list[int]:
        from PIL import Image

        if count != 3:
            raise ValueError("仅验收过选择 3 张图片的九宫格题型")
        np = self.np
        board = Image.open(io.BytesIO(background))
        width, height = board.size
        if width < 90 or height < 90 or width > 2048 or height > 2048:
            raise ValueError("九宫格图片尺寸异常")
        board = board.convert("RGB")
        query = Image.open(io.BytesIO(prompt))
        if not (1 <= query.width <= 512 and 1 <= query.height <= 512):
            raise ValueError("九宫格提示图尺寸异常")
        images = [query]
        images.extend(
            board.crop(
                (
                    col * width // 3,
                    row * height // 3,
                    (col + 1) * width // 3,
                    (row + 1) * height // 3,
                )
            )
            for row in range(3)
            for col in range(3)
        )
        tensors = []
        for image in images:
            rgba = image.convert("RGBA")
            rgb = Image.new("RGB", rgba.size, "white")
            rgb.paste(rgba, mask=rgba.getchannel("A"))
            pixels = np.asarray(rgb.resize((224, 224)), dtype=np.float32) / 255
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            tensors.append(((pixels - mean) / std).transpose(2, 0, 1))
        output = self.network.run(None, {self.network.get_inputs()[0].name: np.stack(tensors)})[0]
        if output.shape != (10, 91) or not np.isfinite(output).all():
            raise ValueError("九宫格模型输出异常")
        output /= np.maximum(np.linalg.norm(output, axis=1, keepdims=True), 1e-12)
        scores = output[1:] @ output[0]
        return sorted(np.argsort(scores)[-count:].tolist())


class RecognitionFailedError(RuntimeError):
    """本题未找到完整匹配，可以刷新换题；模型和依赖错误不能这样重试。"""


def _letterbox(rgb, shape, fill, interpolation):
    import cv2
    import numpy as np

    h, w = rgb.shape[:2]
    scale = min(shape[0] / w, shape[1] / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    x, y = (shape[0] - nw) // 2, (shape[1] - nh) // 2
    image = np.full((shape[1], shape[0], 3), fill, np.uint8)
    image[y : y + nh, x : x + nw] = cv2.resize(rgb, (nw, nh), interpolation=interpolation)
    return image.astype(np.float32).transpose(2, 0, 1) / 255, scale, (x, y)


class WordRecognizer:
    def __init__(self, directory: Path | None = None):
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        directory = directory or model_directory()
        self.detector = ort.InferenceSession(
            str(verified_model(directory, WORD_DETECTION_FILENAME)),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.matcher = ort.InferenceSession(
            str(verified_model(directory, WORD_MATCHING_FILENAME)),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )

    def select(self, background: bytes, prompts: list[bytes]) -> list[tuple[float, float]]:
        import cv2
        import numpy as np
        from PIL import Image, ImageOps

        if len(prompts) != 3:
            raise ValueError("当前仅支持三个提示字的顺序点选")
        board = Image.open(io.BytesIO(background))
        if not (90 <= board.width <= 2048 and 90 <= board.height <= 2048):
            raise ValueError("文字背景图尺寸异常")
        bg = np.asarray(board.convert("RGB"))
        smooth = cv2.GaussianBlur(bg, (3, 3), 0)
        gray = cv2.cvtColor(smooth, cv2.COLOR_RGB2GRAY)
        equalized = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(6, 4)).apply(gray)
        variants = [
            smooth,
            255 - smooth,
            cv2.cvtColor(equalized, cv2.COLOR_GRAY2RGB),
            cv2.cvtColor(255 - equalized, cv2.COLOR_GRAY2RGB),
        ]
        candidates = []
        for variant in variants:
            tensor, scale, (dx, dy) = _letterbox(variant, (640, 640), 114, cv2.INTER_LINEAR)
            raw = self.detector.run(None, {self.detector.get_inputs()[0].name: tensor[None]})[0][0]
            if raw.shape != (300, 6) or not np.isfinite(raw).all():
                raise ValueError("文字检测模型输出异常")
            for x1, y1, x2, y2, confidence, kind in raw:
                if confidence >= 0.1 and int(kind) == 0:
                    box = [
                        max(0, int((x1 - dx) / scale)),
                        max(0, int((y1 - dy) / scale)),
                        min(board.width, int((x2 - dx) / scale)),
                        min(board.height, int((y2 - dy) / scale)),
                    ]
                    if box[2] > box[0] and box[3] > box[1]:
                        candidates.append((float(confidence), box))
        boxes = []
        for _, box in sorted(candidates, reverse=True):
            duplicate = False
            for old in boxes:
                intersection = max(0, min(old[2], box[2]) - max(old[0], box[0])) * max(
                    0, min(old[3], box[3]) - max(old[1], box[1])
                )
                union = (
                    (old[2] - old[0]) * (old[3] - old[1])
                    + (box[2] - box[0]) * (box[3] - box[1])
                    - intersection
                )
                if intersection / union > 0.5:
                    duplicate = True
                    break
            if not duplicate:
                boxes.append(box)
            if len(boxes) >= 12:
                break
        if len(boxes) < len(prompts):
            raise RecognitionFailedError("本题检测到的候选字不足")
        queries = []
        for data in prompts:
            image = Image.open(io.BytesIO(data))
            if not (1 <= image.width <= 512 and 1 <= image.height <= 512):
                raise ValueError("文字提示图尺寸异常")
            rgba = image.convert("RGBA")
            rgb = Image.new("RGB", rgba.size, "white")
            rgb.paste(rgba, mask=rgba.getchannel("A"))
            bounds = ImageOps.invert(rgb.convert("L")).getbbox()
            if bounds is None:
                raise RecognitionFailedError("本题提示字为空")
            queries.append(
                _letterbox(np.asarray(rgb.crop(bounds)), (112, 112), 128, cv2.INTER_CUBIC)[0]
            )
        chars = [
            _letterbox(bg[y1:y2, x1:x2], (112, 112), 128, cv2.INTER_CUBIC)[0]
            for x1, y1, x2, y2 in boxes
        ]
        output = self.matcher.run(
            None,
            {
                self.matcher.get_inputs()[0].name: np.stack([x for x in queries for _ in chars]),
                self.matcher.get_inputs()[1].name: np.stack(chars * len(queries)),
            },
        )[0]
        if output.size != len(queries) * len(chars) or not np.isfinite(output).all():
            raise ValueError("文字匹配模型输出异常")
        scores = 1 / (1 + np.exp(-np.clip(output.reshape(len(queries), len(chars)), -80, 80)))
        order = max(
            itertools.permutations(range(len(chars)), len(queries)),
            key=lambda indices: sum(float(scores[i, j]) for i, j in enumerate(indices)),
        )
        return [
            (
                (boxes[j][0] + boxes[j][2]) / (2 * board.width),
                (boxes[j][1] + boxes[j][3]) / (2 * board.height),
            )
            for j in order
        ]


_recognizer: NineRecognizer | None = None
_lock = Lock()


def recognize_nine(background: bytes, prompt: bytes, count: int = 3) -> list[int]:
    global _recognizer
    # 多账号共用一份模型，同时限制推理内存峰值。
    with _lock:
        if _recognizer is None:
            _recognizer = NineRecognizer()
        return _recognizer.select(background, prompt, count)


_word_recognizer: WordRecognizer | None = None


def recognize_word(background: bytes, prompts: list[bytes]) -> list[tuple[float, float]]:
    global _word_recognizer
    with _lock:
        if _word_recognizer is None:
            _word_recognizer = WordRecognizer()
        return _word_recognizer.select(background, prompts)
