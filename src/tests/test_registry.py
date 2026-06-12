"""任务注册表 smoke 测试。"""

import importlib
import importlib.util

from src.jobs import registry
from src.jobs.registry import TASK_MODULES, get_registered_task


def test_all_task_modules_exist() -> None:
    for mod_name in TASK_MODULES:
        assert importlib.util.find_spec(mod_name) is not None


def test_discover_and_get_ikuuu_task() -> None:
    registry.TASK_JOBS.clear()
    importlib.reload(importlib.import_module("src.tasks.ikuuu_checkin"))
    job = get_registered_task("ikuuu_checkin")
    assert job is not None
    assert job.job_id == "ikuuu_checkin"
    assert job.description
    assert job.original_run_func is not None
