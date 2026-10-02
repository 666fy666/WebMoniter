"""固定版本的 iKuuu 本地模型；运行签到时不下载权重。"""

import argparse
import hashlib
import os
import tempfile
from pathlib import Path
from urllib.request import urlopen

NINE_FILENAME = "resnet18.onnx"
NINE_SHA256 = "2085490e5a44158600092114a6dd918d2862093caffbc2f7647c5374ce99bedc"
NINE_URL = (
    "https://raw.githubusercontent.com/WhiteZerooooo/GeetestMYS/"
    "0cc806751b70a866b96b31812737d9844b379fe0/model/resnet18.onnx"
)
WORD_DETECTION_FILENAME = "best_v3.onnx"
WORD_MATCHING_FILENAME = "pre_model_v7.onnx"
_WORD_BASE = (
    "https://raw.githubusercontent.com/MgArcher/Text_select_captcha/"
    "dcd1ac317c73cd29a7e3118f935c2b3fbd34cb02/model/"
)
MODELS = {
    NINE_FILENAME: (NINE_URL, NINE_SHA256),
    WORD_DETECTION_FILENAME: (
        _WORD_BASE + WORD_DETECTION_FILENAME,
        "a9804980ad250f236104c2befac980321de29799410847c52f5b855ac9de347d",
    ),
    WORD_MATCHING_FILENAME: (
        _WORD_BASE + WORD_MATCHING_FILENAME,
        "885e01b20592c558df7c7438177e39623f218d02154631cbdc17e654fcac3e05",
    ),
}


def model_directory() -> Path:
    return Path(os.environ.get("WEBMONITER_IKUUU_MODEL_DIR", "data/models/ikuuu"))


def verified_model(directory: Path, filename: str = NINE_FILENAME) -> Path:
    _, expected = MODELS[filename]
    path = directory / filename
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != expected:
        raise ValueError(f"模型 {filename} SHA-256 校验失败，请重新下载固定版本")
    return path


def download_model(directory: Path, filename: str = NINE_FILENAME) -> Path:
    url, expected = MODELS[filename]
    directory.mkdir(parents=True, exist_ok=True)
    try:
        return verified_model(directory, filename)
    except (OSError, ValueError):
        pass
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as output:
            temporary = Path(output.name)
            with urlopen(url, timeout=60) as response:
                total = 0
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > 50 * 1024 * 1024:
                        raise ValueError("模型下载大小超过上限")
                    output.write(block)
        with temporary.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != expected:
            raise ValueError(f"下载的模型 {filename} SHA-256 不匹配")
        temporary.replace(directory / filename)
        return verified_model(directory, filename)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=model_directory())
    args = parser.parse_args()
    for filename in MODELS:
        print(download_model(args.directory, filename))
