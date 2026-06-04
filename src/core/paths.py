"""仓库根目录相对路径约定（Docker WORKDIR /app、本地 uv run、PyInstaller 解压目录均以应用根为 cwd）。"""

from pathlib import Path

CONFIG_YAML_FILE = Path("config.yml")
SRC_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SRC_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
WEB_UI_DIR = SRC_DIR / "webUI"
WEB_UI_STATIC_DIR = WEB_UI_DIR / "static"
WEB_UI_TEMPLATES_DIR = WEB_UI_DIR / "templates"


def resolve_config_sample_path() -> Path:
    """示例配置文件路径。

    - 源码仓库：`config/config.yml.sample`
    - Windows 发行包根目录：常为扁平的 `config.yml.sample`
    """
    nested = Path("config/config.yml.sample")
    flat = Path("config.yml.sample")
    if nested.is_file():
        return nested
    return flat
