"""任务 enable 映射一致性测试。"""

from src.jobs.enable_fields import TASK_JOB_ENABLE_FIELD_MAP


def test_task_enable_map_has_core_checkin_tasks() -> None:
    assert TASK_JOB_ENABLE_FIELD_MAP["ikuuu_checkin"] == "checkin_enable"
    assert TASK_JOB_ENABLE_FIELD_MAP["tieba_checkin"] == "tieba_enable"
    assert TASK_JOB_ENABLE_FIELD_MAP["log_cleanup"] == "log_cleanup_enable"


def test_demo_task_not_in_enable_map() -> None:
    assert "demo_task" not in TASK_JOB_ENABLE_FIELD_MAP
