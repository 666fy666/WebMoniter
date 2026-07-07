"""仓库根目录相对路径约定（Docker WORKDIR /app、本地 uv run、PyInstaller 解压目录均以应用根为 cwd）。"""

import sys
from pathlib import Path

CONFIG_YAML_FILE = Path("config.yml")
SRC_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SRC_DIR.parent
WEB_UI_DIR = SRC_DIR / "webUI"
WEB_UI_STATIC_DIR = WEB_UI_DIR / "static"
WEB_UI_TEMPLATES_DIR = WEB_UI_DIR / "templates"


def get_app_root() -> Path:
    """应用根目录：PyInstaller 打包后以可执行文件所在目录为基准，否则为项目根。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def get_data_dir() -> Path:
    """data 目录路径，不存在时自动创建。"""
    data_dir = get_app_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


# 常用数据文件路径（绝对路径，避免 cwd 变化导致落错位置）
DATA_DIR = get_data_dir()
DB_PATH = (DATA_DIR / "data.db").resolve()
AUTH_FILE = (DATA_DIR / "auth.json").resolve()
COOKIE_CACHE_FILE = (DATA_DIR / "cookie_cache.json").resolve()
SESSION_SECRET_FILE = (DATA_DIR / "session_secret").resolve()
WEB_SESSION_FILE = (DATA_DIR / "web_sessions.json").resolve()
WEIBO_IMG_DIR = DATA_DIR / "weibo"


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
