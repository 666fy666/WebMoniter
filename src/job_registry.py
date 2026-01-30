"""
任务注册表 - 统一注册监控任务与定时任务，新增任务时只需在本模块的模块列表中追加并实现任务逻辑。

新增监控/定时任务步骤：
1. 在 monitors/ 或 tasks/ 下实现任务模块（见 docs/SECONDARY_DEVELOPMENT.md）
2. 在 MONITOR_MODULES 或 TASK_MODULES 中追加模块路径
3. 在任务模块内调用 register_monitor() 或 register_task() 完成注册
"""

import importlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from src.config import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class JobDescriptor:
    """任务描述：用于调度器注册与热重载时更新触发参数"""

    job_id: str
    run_func: Callable[[], Awaitable[None]]
    trigger: str  # "interval" | "cron"
    get_trigger_kwargs: Callable[[AppConfig], dict[str, Any]]


# 监控任务（间隔执行）模块列表，新增监控时在此追加模块路径即可
MONITOR_MODULES: list[str] = [
    "monitors.huya_monitor",
    "monitors.weibo_monitor",
]

# 定时任务（Cron 执行）模块列表，新增定时任务时在此追加模块路径即可
TASK_MODULES: list[str] = [
    "tasks.log_cleanup",
    "tasks.ikuuu_checkin",
    "tasks.tieba_checkin",
    "tasks.weibo_chaohua_checkin",
    "tasks.demo_task",  # 二次开发示例，不需要可移除此行
]

MONITOR_JOBS: list[JobDescriptor] = []
TASK_JOBS: list[JobDescriptor] = []


def register_monitor(
    job_id: str,
    run_func: Callable[[], Awaitable[None]],
    get_trigger_kwargs: Callable[[AppConfig], dict[str, Any]],
) -> None:
    """
    注册一个监控任务（间隔触发）。
    应在监控模块加载时调用，例如：register_monitor("huya_monitor", run_huya_monitor, lambda c: {"seconds": c.huya_monitor_interval_seconds})
    """
    MONITOR_JOBS.append(
        JobDescriptor(
            job_id=job_id,
            run_func=run_func,
            trigger="interval",
            get_trigger_kwargs=get_trigger_kwargs,
        )
    )
    logger.debug("已注册监控任务: %s", job_id)


def register_task(
    job_id: str,
    run_func: Callable[[], Awaitable[None]],
    get_trigger_kwargs: Callable[[AppConfig], dict[str, Any]],
) -> None:
    """
    注册一个定时任务（Cron 触发）。
    应在任务模块加载时调用，例如：register_task("daily_checkin", run_checkin_once, lambda c: {"hour": h, "minute": m})
    """
    TASK_JOBS.append(
        JobDescriptor(
            job_id=job_id,
            run_func=run_func,
            trigger="cron",
            get_trigger_kwargs=get_trigger_kwargs,
        )
    )
    logger.debug("已注册定时任务: %s", job_id)


def discover_and_import() -> None:
    """
    按 MONITOR_MODULES 与 TASK_MODULES 导入模块，触发各模块内的 register_monitor/register_task 调用。
    主入口在启动调度前调用一次即可。
    """
    for mod_name in MONITOR_MODULES + TASK_MODULES:
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            logger.warning("导入任务模块 %s 失败: %s", mod_name, e)
