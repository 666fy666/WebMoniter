"""任务注册表 smoke 测试。"""

import importlib
import importlib.util

from src.jobs import registry
from src.jobs.registry import TASK_MODULES, get_registered_task, register_monitor, register_task


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


def test_register_monitor_replaces_existing_job_id() -> None:
    async def noop() -> None:
        return None

    registry.MONITOR_JOBS.clear()
    try:
        register_monitor("unit_monitor", noop, lambda c: {"seconds": 1}, description="old")
        register_monitor("unit_monitor", noop, lambda c: {"seconds": 2}, description="new")

        assert len(registry.MONITOR_JOBS) == 1
        assert registry.MONITOR_JOBS[0].description == "new"
        assert registry.MONITOR_JOBS[0].get_trigger_kwargs(None) == {"seconds": 2}
    finally:
        registry.MONITOR_JOBS.clear()


def test_register_task_replaces_existing_job_id() -> None:
    async def noop() -> None:
        return None

    registry.TASK_JOBS.clear()
    try:
        register_task("unit_task", noop, lambda c: {"hour": "1", "minute": "0"})
        register_task("unit_task", noop, lambda c: {"hour": "2", "minute": "30"})

        assert len(registry.TASK_JOBS) == 1
        assert registry.TASK_JOBS[0].get_trigger_kwargs(None) == {"hour": "2", "minute": "30"}
    finally:
        registry.TASK_JOBS.clear()
