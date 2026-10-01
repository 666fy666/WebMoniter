"""路径常量 smoke 测试。"""

from src.core.paths import (
    AUTH_FILE,
    COOKIE_CACHE_FILE,
    DB_PATH,
    PROJECT_ROOT,
    get_data_dir,
)


def test_data_paths_under_data_dir() -> None:
    data_dir = get_data_dir()
    assert data_dir.is_dir()
    assert data_dir.parent != PROJECT_ROOT
    assert DB_PATH.parent == data_dir.resolve()
    assert AUTH_FILE.parent == data_dir.resolve()
    assert COOKIE_CACHE_FILE.parent == data_dir.resolve()
