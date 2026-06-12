"""路径常量 smoke 测试。"""

from pathlib import Path

from src.core.paths import (
    AUTH_FILE,
    COOKIE_CACHE_FILE,
    DB_PATH,
    PROJECT_ROOT,
    get_app_root,
    get_data_dir,
)


def test_get_app_root_is_directory() -> None:
    root = get_app_root()
    assert root.is_dir()


def test_data_paths_under_data_dir() -> None:
    data_dir = get_data_dir()
    assert data_dir.is_dir()
    assert DB_PATH.parent == data_dir.resolve()
    assert AUTH_FILE.parent == data_dir.resolve()
    assert COOKIE_CACHE_FILE.parent == data_dir.resolve()


def test_project_root_contains_src() -> None:
    assert (PROJECT_ROOT / "src").is_dir()
    assert (PROJECT_ROOT / "main.py").is_file() or Path("main.py").is_file()
