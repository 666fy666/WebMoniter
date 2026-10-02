"""离线复跑图片识别实验；不提交验证码，不启用生产识别器。

输入清单可为采集脚本生成的列表，或验收报告中的 samples 数组。
样本和候选权重由调用者准备；脚本只读取本地文件。
"""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
from time import perf_counter

import ddddocr
import numpy as np
import onnxruntime as ort
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

MODEL_SHA256 = "2085490e5a44158600092114a6dd918d2862093caffbc2f7647c5374ce99bedc"


def white_background(image):
    rgba = image.convert("RGBA")
    rgb = Image.new("RGB", rgba.size, "white")
    rgb.paste(rgba, mask=rgba.getchannel("A"))
    return rgb


def image_tensor(image):
    pixels = np.asarray(white_background(image).resize((224, 224)), dtype=np.float32) / 255
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    return ((pixels - mean) / std).transpose(2, 0, 1)


def validate_inputs(manifest, samples, model):
    if hashlib.sha256(model.read_bytes()).hexdigest() != MODEL_SHA256:
        raise ValueError("候选权重校验值与本次验收版本不一致")
    records = json.loads(manifest.read_text(encoding="utf-8"))
    if isinstance(records, dict):
        records = records["samples"]
    for kind in ("word", "nine"):
        items = [row for row in records if row["kind"] == kind]
        if len(items) < 20 or len({row["sha256"][0] for row in items}) != len(items):
            raise ValueError(f"{kind} 样本不足 20 道或存在重复背景图")
        for row in items:
            if len(row["files"]) != len(row["sha256"]):
                raise ValueError("图片与校验值数量不一致")
            for filename, expected in zip(row["files"], row["sha256"], strict=True):
                if Path(filename).name != filename:
                    raise ValueError("样本文件名不可包含路径")
                if hashlib.sha256((samples / filename).read_bytes()).hexdigest() != expected:
                    raise ValueError(f"样本校验失败：{filename}")
    return records


def evaluate(records, samples, model):
    options = Options()
    options.binary_location = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
    for arg in ("--headless", "--no-sandbox", "--disable-dev-shm-usage"):
        options.add_argument(arg)
    driver = webdriver.Chrome(
        service=Service(os.environ.get("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")),
        options=options,
    )
    try:
        driver.get("data:text/html,<title>offline model validation</title>")
        detection = ddddocr.DdddOcr(det=True, ocr=False, show_ad=False)
        recognition = ddddocr.DdddOcr(show_ad=False)
        settings = ort.SessionOptions()
        settings.intra_op_num_threads = 1
        settings.inter_op_num_threads = 1
        network = ort.InferenceSession(
            str(model), sess_options=settings, providers=["CPUExecutionProvider"]
        )

        def recognize(image):
            buffer = io.BytesIO()
            white_background(image).save(buffer, format="PNG")
            return recognition.classification(buffer.getvalue())

        results = []
        for row in records:
            started = perf_counter()
            background = Image.open(samples / row["files"][0]).convert("RGB")
            result = {"id": row["id"], "kind": row["kind"]}
            if row["kind"] == "word":
                boxes = detection.detection((samples / row["files"][0]).read_bytes())
                result["boxes"] = boxes
                result["characters"] = [recognize(background.crop(tuple(box))) for box in boxes]
                result["prompt"] = [
                    recognize(Image.open(samples / name)) for name in row["files"][1:]
                ]
            elif row["kind"] == "nine":
                width, height = background.size
                images = [Image.open(samples / row["files"][1])]
                images.extend(
                    background.crop(
                        (
                            col * width // 3,
                            line * height // 3,
                            (col + 1) * width // 3,
                            (line + 1) * height // 3,
                        )
                    )
                    for line in range(3)
                    for col in range(3)
                )
                output = network.run(
                    None,
                    {network.get_inputs()[0].name: np.stack([image_tensor(x) for x in images])},
                )[0]
                output /= np.maximum(np.linalg.norm(output, axis=1, keepdims=True), 1e-12)
                scores = output[1:] @ output[0]
                result["scores"] = scores.tolist()
                result["selected"] = sorted((np.argsort(scores)[-3:] + 1).tolist())
            else:
                raise ValueError("未知样本题型")
            result["seconds"] = perf_counter() - started
            results.append(result)
        peak_path = Path("/sys/fs/cgroup/memory.peak")
        return {
            "predictions": results,
            "cgroup_peak_bytes": int(peak_path.read_text()) if peak_path.exists() else None,
            "browser_version": driver.capabilities.get("browserVersion"),
        }
    finally:
        driver.quit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "samples", "model", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    records = validate_inputs(args.manifest, args.samples, args.model)
    result = evaluate(records, args.samples, args.model)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已评估 {len(result['predictions'])} 道题；结果写入 {args.output}")


if __name__ == "__main__":
    main()
