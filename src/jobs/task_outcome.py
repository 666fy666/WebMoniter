"""定时任务执行结果约定。

register_task 包装层仅在 run_func 返回 True 时写入「今日已运行」。
- True：任务已成功完成（当天可跳过）
- False：未执行、配置不完整或执行失败（允许当天重试）
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TaskResult:
    status: Literal["success", "partial", "failed", "skipped", "timeout"]


TaskOutcome = bool | TaskResult

TASK_SUCCESS: TaskOutcome = True
TASK_FAILED: TaskOutcome = False
TASK_SKIPPED = TaskResult("skipped")
TASK_PARTIAL = TaskResult("partial")
TASK_TIMEOUT = TaskResult("timeout")
