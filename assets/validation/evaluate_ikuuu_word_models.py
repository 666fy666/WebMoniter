"""文字检测 + 字形匹配离线复跑；本脚本不执行浏览器点击。"""

import argparse
import hashlib
import itertools
import json
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps

parser = argparse.ArgumentParser(description="离线评估文字检测和字形匹配，不注册生产识别器")
for name in ("manifest", "samples", "models", "output"):
    parser.add_argument("--" + name, type=Path, required=True)
args = parser.parse_args()
samples = args.samples
records = json.loads(args.manifest.read_text(encoding="utf-8"))
if isinstance(records, dict):
    records = records["samples"]
records = [row for row in records if row["kind"] == "word"]
if len(records) < 20 or len({r["sha256"][0] for r in records}) != len(records):
    raise ValueError("需要至少 20 道不同真实文字题")
for filename, checksum in {
    "best_v3.onnx": "a9804980ad250f236104c2befac980321de29799410847c52f5b855ac9de347d",
    "pre_model_v7.onnx": "885e01b20592c558df7c7438177e39623f218d02154631cbdc17e654fcac3e05",
}.items():
    if hashlib.sha256((args.models / filename).read_bytes()).hexdigest() != checksum:
        raise ValueError("权重校验失败: " + filename)
for row in records:
    for filename, checksum in zip(row["files"], row["sha256"], strict=True):
        if Path(filename).name != filename:
            raise ValueError("样本文件名不能含路径")
        if hashlib.sha256((samples / filename).read_bytes()).hexdigest() != checksum:
            raise ValueError("样本校验失败: " + filename)
settings = ort.SessionOptions()
settings.intra_op_num_threads = 1
settings.inter_op_num_threads = 1
det = ort.InferenceSession(
    str(args.models / "best_v3.onnx"), settings, providers=["CPUExecutionProvider"]
)
pair = ort.InferenceSession(
    str(args.models / "pre_model_v7.onnx"), settings, providers=["CPUExecutionProvider"]
)
print(
    "contracts",
    [(x.name, x.shape) for x in det.get_inputs()],
    [(x.name, x.shape) for x in det.get_outputs()],
    [(x.name, x.shape) for x in pair.get_inputs()],
    flush=True,
)


def letterbox(rgb, shape, fill, interpolation):
    h, w = rgb.shape[:2]
    scale = min(shape[0] / w, shape[1] / h)
    nw, nh = int(w * scale), int(h * scale)
    x, y = (shape[0] - nw) // 2, (shape[1] - nh) // 2
    image = np.full((shape[1], shape[0], 3), fill, np.uint8)
    image[y : y + nh, x : x + nw] = cv2.resize(rgb, (nw, nh), interpolation=interpolation)
    return image.astype(np.float32).transpose(2, 0, 1) / 255, scale, (x, y)


results = []
for row in records:
    start = time.perf_counter()
    bg = np.asarray(Image.open(samples / row["files"][0]).convert("RGB"))
    candidates = []
    smooth = cv2.GaussianBlur(bg, (3, 3), 0)
    gray = cv2.cvtColor(smooth, cv2.COLOR_RGB2GRAY)
    equalized = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(6, 4)).apply(gray)
    variants = [
        smooth,
        255 - smooth,
        cv2.cvtColor(equalized, cv2.COLOR_GRAY2RGB),
        cv2.cvtColor(255 - equalized, cv2.COLOR_GRAY2RGB),
    ]
    for blurred in variants:
        inp, scale, (dx, dy) = letterbox(blurred, (640, 640), 114, cv2.INTER_LINEAR)
        raw = det.run(None, {det.get_inputs()[0].name: inp[None]})[0][0]
        for x1, y1, x2, y2, confidence, kind in raw:
            if confidence >= 0.1 and int(kind) == 0:
                box = [
                    max(0, int((x1 - dx) / scale)),
                    max(0, int((y1 - dy) / scale)),
                    min(bg.shape[1], int((x2 - dx) / scale)),
                    min(bg.shape[0], int((y2 - dy) / scale)),
                ]
                if box[2] > box[0] and box[3] > box[1]:
                    candidates.append((float(confidence), box))
    boxes = []
    for confidence, box in sorted(candidates, reverse=True):
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
    prompts = []
    for f in row["files"][1:]:
        rgba = Image.open(samples / f).convert("RGBA")
        rgb = Image.new("RGB", rgba.size, "white")
        rgb.paste(rgba, mask=rgba.getchannel("A"))
        # The model was trained on cropped prompt characters, not their outer transparent margin.
        bbox = ImageOps.invert(rgb.convert("L")).getbbox()
        prompts.append(np.asarray(rgb.crop(bbox)))
    result = {"id": row["id"], "boxes": boxes}
    if len(boxes) >= len(prompts):
        chars = [bg[y1:y2, x1:x2] for x1, y1, x2, y2 in boxes]
        one = [letterbox(x, (112, 112), 128, cv2.INTER_CUBIC)[0] for x in prompts]
        two = [letterbox(x, (112, 112), 128, cv2.INTER_CUBIC)[0] for x in chars]
        feed = {
            pair.get_inputs()[0].name: np.stack([x for x in one for _ in two]),
            pair.get_inputs()[1].name: np.stack(two * len(one)),
        }
        logits = pair.run(None, feed)[0].reshape(len(one), len(two))
        scores = 1 / (1 + np.exp(-np.clip(logits, -80, 80)))
        assignment = max(
            itertools.permutations(range(len(two)), len(one)),
            key=lambda order: sum(float(scores[i, j]) for i, j in enumerate(order)),
        )
        result.update(
            scores=scores.tolist(),
            points=[
                [(boxes[j][0] + boxes[j][2]) / 2, (boxes[j][1] + boxes[j][3]) / 2]
                for j in assignment
            ],
        )
    result["seconds"] = time.perf_counter() - start
    results.append(result)
    print(row["id"], result, flush=True)
args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
