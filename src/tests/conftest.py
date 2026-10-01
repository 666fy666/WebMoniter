"""测试运行文件隔离与任务注册夹具。"""

from __future__ import annotations

import atexit
import importlib
import logging
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from src.core import paths
from src.settings import config

# 必须在收集测试模块之前设置：部分模块导入时会创建 Cookie、会话文件。
_runtime = tempfile.TemporaryDirectory(prefix="webmoniter-tests-", ignore_cleanup_errors=True)
atexit.register(_runtime.cleanup)
_runtime_dir = Path(_runtime.name)
paths.DATA_DIR = _runtime_dir
paths.get_data_dir = lambda: _runtime_dir
for _name, _filename in {
    "DB_PATH": "data.db",
    "AUTH_FILE": "auth.json",
    "COOKIE_CACHE_FILE": "cookie_cache.json",
    "SESSION_SECRET_FILE": "session_secret",
    "WEB_SESSION_FILE": "web_sessions.json",
    "WEIBO_IMG_DIR": "weibo",
}.items():
    setattr(paths, _name, _runtime_dir / _filename)

_config_file = _runtime_dir / "config.yml"
shutil.copyfile(paths.PROJECT_ROOT / "config/config.yml.sample", _config_file)
config.CONFIG_YAML_FILE = _config_file
config.load_config_from_yml.__defaults__ = (str(_config_file),)

from src.jobs.log_manager import LogManager  # noqa: E402

LogManager.__init__.__defaults__ = (str(_runtime_dir / "logs"), 3)

logger = logging.getLogger(__name__)

# 依赖 rainyun extra（Selenium、ddddocr 等），dev 环境未安装时应跳过
OPTIONAL_IMPORT_MODULES: frozenset[str] = frozenset({"src.tasks.rainyun_checkin"})
OPTIONAL_DEPENDENCIES = frozenset({"selenium", "ddddocr", "cv2"})


def _reload_or_import(mod_name: str):
    if mod_name in sys.modules:
        return importlib.reload(sys.modules[mod_name])
    return importlib.import_module(mod_name)


def safe_reload_modules(module_paths: list[str]) -> list[str]:
    """重载模块以重新执行 register_*；返回导入/重载失败的模块路径。"""
    failed: list[str] = []
    for mod_name in module_paths:
        try:
            _reload_or_import(mod_name)
        except ModuleNotFoundError as exc:
            if (
                mod_name in OPTIONAL_IMPORT_MODULES
                and (exc.name or "").split(".", 1)[0] in OPTIONAL_DEPENDENCIES
            ):
                logger.debug("跳过可选依赖模块 %s: %s", mod_name, exc)
                failed.append(mod_name)
            else:
                raise
    return failed


@pytest.fixture(scope="module")
def registered_jobs():
    from src.jobs import registry

    previous_monitors = registry.MONITOR_JOBS[:]
    previous_tasks = registry.TASK_JOBS[:]
    registry.MONITOR_JOBS.clear()
    registry.TASK_JOBS.clear()
    try:
        skipped = safe_reload_modules(registry.MONITOR_MODULES + registry.TASK_MODULES)
        yield tuple(registry.MONITOR_JOBS), tuple(registry.TASK_JOBS), skipped
    finally:
        registry.MONITOR_JOBS[:] = previous_monitors
        registry.TASK_JOBS[:] = previous_tasks
