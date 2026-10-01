"""任务注册、配置字段和调度契约的一致性检查。"""

from src.jobs.enable_fields import MONITOR_JOB_ENABLE_FIELD_MAP, TASK_JOB_ENABLE_FIELD_MAP
from src.jobs.metadata import MONITOR_SPECS, TASK_SPECS
from src.jobs.registry import monitor_job_enabled
from src.settings.config import AppConfig, get_config


def test_enable_fields_exist_and_are_unique():
    fields = [*MONITOR_JOB_ENABLE_FIELD_MAP.values(), *TASK_JOB_ENABLE_FIELD_MAP.values()]
    assert len(fields) == len(set(fields))
    assert set(fields) <= set(AppConfig.model_fields)


def test_registered_jobs_match_metadata_and_triggers(registered_jobs):
    monitors, tasks, skipped = registered_jobs
    skipped_ids = {module.rsplit(".", 1)[-1] for module in skipped}
    expected = {spec.job_id: spec for spec in (*MONITOR_SPECS, *TASK_SPECS)}
    jobs = monitors + tasks
    assert {job.job_id for job in monitors} == set(MONITOR_JOB_ENABLE_FIELD_MAP)
    assert {job.job_id for job in tasks} | skipped_ids == {spec.job_id for spec in TASK_SPECS}
    assert len(jobs) == len({job.job_id for job in jobs})
    config = get_config()
    for job in jobs:
        spec = expected[job.job_id]
        assert job.description == spec.description, job.job_id
        assert job.original_run_func is not None, job.job_id
        kwargs = job.get_trigger_kwargs(config)
        if job in monitors:
            assert job.trigger == "interval" and kwargs, job.job_id
        else:
            assert job.trigger == "cron", job.job_id
            assert "hour" in kwargs and "minute" in kwargs, job.job_id
            if not spec.plugin_only:
                assert TASK_JOB_ENABLE_FIELD_MAP[job.job_id] == spec.enable_field


def test_monitor_job_enabled_defaults_true_for_unknown_job():
    assert monitor_job_enabled("unknown_monitor", get_config()) is True
