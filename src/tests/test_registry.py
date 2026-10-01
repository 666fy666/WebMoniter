"""任务注册表 smoke 测试。"""

import pytest

from src.jobs import registry
from src.jobs.registry import register_monitor, register_task


@pytest.fixture(autouse=True)
def restore_registry():
    monitors = registry.MONITOR_JOBS[:]
    tasks = registry.TASK_JOBS[:]
    try:
        yield
    finally:
        registry.MONITOR_JOBS[:] = monitors
        registry.TASK_JOBS[:] = tasks


def test_register_monitor_replaces_existing_job_id() -> None:
    async def noop() -> bool:
        return True

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
    async def noop() -> bool:
        return True

    registry.TASK_JOBS.clear()
    try:
        register_task("unit_task", noop, lambda c: {"hour": "1", "minute": "0"})
        register_task("unit_task", noop, lambda c: {"hour": "2", "minute": "30"})

        assert len(registry.TASK_JOBS) == 1
        assert registry.TASK_JOBS[0].get_trigger_kwargs(None) == {"hour": "2", "minute": "30"}
    finally:
        registry.TASK_JOBS.clear()


def test_register_task_can_opt_out_of_startup_run() -> None:
    async def noop() -> bool:
        return True

    registry.TASK_JOBS.clear()
    try:
        register_task(
            "cron_only",
            noop,
            lambda c: {"hour": "21", "minute": "0"},
            run_on_startup=False,
        )

        assert registry.TASK_JOBS[0].run_on_startup is False
    finally:
        registry.TASK_JOBS.clear()
