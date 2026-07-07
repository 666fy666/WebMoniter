"""任务元数据、注册表与 enable 映射一致性测试。

新增监控/定时任务时，若漏配 src.jobs.metadata 中的任务规格或生成出的兼容映射，
本模块中的测试应失败并提示不一致项。
"""

from src.jobs import registry
from src.jobs.enable_fields import MONITOR_JOB_ENABLE_FIELD_MAP, TASK_JOB_ENABLE_FIELD_MAP
from src.jobs.registry import (
    MONITOR_MODULES,
    TASK_MODULES,
    discover_and_import,
    discover_and_import_tasks_only,
    monitor_job_enabled,
)
from src.settings.config import AppConfig, get_config
from src.tests.conftest import safe_reload_modules

PLUGIN_ONLY_TASKS = frozenset({"demo_task"})


def _job_id_from_module(module_path: str) -> str:
    return module_path.rsplit(".", 1)[-1]


def _reset_registry() -> None:
    registry.MONITOR_JOBS.clear()
    registry.TASK_JOBS.clear()


def _reload_and_discover_all() -> list[str]:
    _reset_registry()
    failed = safe_reload_modules(MONITOR_MODULES + TASK_MODULES)
    discover_and_import()
    return failed


def _reload_and_discover_tasks() -> list[str]:
    _reset_registry()
    failed = safe_reload_modules(TASK_MODULES)
    discover_and_import_tasks_only()
    return failed


def test_all_monitor_modules_exist() -> None:
    import importlib.util

    for mod_name in MONITOR_MODULES:
        assert importlib.util.find_spec(mod_name) is not None, mod_name


def test_enable_field_names_exist_on_app_config() -> None:
    fields = set(AppConfig.model_fields)
    for field_name in MONITOR_JOB_ENABLE_FIELD_MAP.values():
        assert field_name in fields, field_name
    for field_name in TASK_JOB_ENABLE_FIELD_MAP.values():
        assert field_name in fields, field_name


def test_enable_field_names_are_unique() -> None:
    all_fields = [
        *MONITOR_JOB_ENABLE_FIELD_MAP.values(),
        *TASK_JOB_ENABLE_FIELD_MAP.values(),
    ]
    assert len(all_fields) == len(set(all_fields))


def test_monitor_enable_map_keys_match_module_list() -> None:
    expected = {_job_id_from_module(mod) for mod in MONITOR_MODULES}
    assert set(MONITOR_JOB_ENABLE_FIELD_MAP) == expected


def test_task_enable_map_keys_match_module_list() -> None:
    expected = {_job_id_from_module(mod) for mod in TASK_MODULES} - PLUGIN_ONLY_TASKS
    assert set(TASK_JOB_ENABLE_FIELD_MAP) == expected


def test_monitor_enable_map_matches_registered_jobs() -> None:
    _reload_and_discover_all()
    registered = {job.job_id for job in registry.MONITOR_JOBS}
    mapped = set(MONITOR_JOB_ENABLE_FIELD_MAP)
    assert registered == mapped, (
        f"监控任务与 enable 映射不一致："
        f"缺少映射 {registered - mapped}；多余映射 {mapped - registered}"
    )


def test_task_enable_map_matches_config_driven_jobs() -> None:
    failed = _reload_and_discover_tasks()
    registered = {job.job_id for job in registry.TASK_JOBS}
    config_driven = registered - PLUGIN_ONLY_TASKS
    mapped = set(TASK_JOB_ENABLE_FIELD_MAP)
    skipped = {_job_id_from_module(mod) for mod in failed}
    assert config_driven | skipped == mapped, (
        f"定时任务与 enable 映射不一致："
        f"缺少映射 {mapped - config_driven - skipped}；多余映射 {config_driven - mapped}"
    )


def test_discover_registers_all_importable_modules() -> None:
    failed = _reload_and_discover_all()
    assert len(registry.MONITOR_JOBS) == len(MONITOR_MODULES)
    expected_tasks = len(TASK_MODULES) - len(failed)
    assert len(registry.TASK_JOBS) == expected_tasks


def test_registered_job_ids_are_unique() -> None:
    _reload_and_discover_all()
    all_ids = [job.job_id for job in registry.MONITOR_JOBS + registry.TASK_JOBS]
    assert len(all_ids) == len(set(all_ids))


def test_monitor_jobs_use_interval_trigger() -> None:
    _reload_and_discover_all()
    for job in registry.MONITOR_JOBS:
        assert job.trigger == "interval", job.job_id
        assert job.original_run_func is not None, job.job_id
        assert job.get_trigger_kwargs(get_config()), job.job_id


def test_task_jobs_use_cron_trigger() -> None:
    _reload_and_discover_tasks()
    for job in registry.TASK_JOBS:
        assert job.trigger == "cron", job.job_id
        assert job.original_run_func is not None, job.job_id
        kwargs = job.get_trigger_kwargs(get_config())
        assert "hour" in kwargs and "minute" in kwargs, job.job_id


def test_monitor_job_enabled_defaults_true_for_unknown_job() -> None:
    config = get_config()
    assert monitor_job_enabled("unknown_monitor", config) is True
