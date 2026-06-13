"""
任务注册表 - 统一注册监控任务与定时任务，新增任务时只需在本模块的模块列表中追加并实现任务逻辑。

新增监控/定时任务步骤：
1. 在 src/monitors/ 或 src/tasks/ 下实现任务模块（见 docs/SECONDARY_DEVELOPMENT.md）
2. 在 MONITOR_MODULES 或 TASK_MODULES 中追加模块路径
3. 在任务模块内调用 register_monitor() 或 register_task() 完成注册
"""

import functools
import importlib
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from src.jobs.enable_fields import MONITOR_JOB_ENABLE_FIELD_MAP, TASK_JOB_ENABLE_FIELD_MAP
from src.jobs.log_manager import LogManager, TaskLogFilter, _current_job_id
from src.settings.config import AppConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class JobDescriptor:
    """任务描述：用于调度器注册与热重载时更新触发参数"""

    job_id: str
    run_func: Callable[[], Awaitable[None]]
    trigger: str  # "interval" | "cron"
    get_trigger_kwargs: Callable[[AppConfig], dict[str, Any]]
    description: str = ""
    # 原始执行函数（未包装），用于手动触发时绕过"当天已运行则跳过"检查
    original_run_func: Callable[[], Awaitable[None]] | None = field(default=None)


# 监控任务（间隔执行）模块列表，新增监控时在此追加模块路径即可
MONITOR_MODULES: list[str] = [
    "src.monitors.huya_monitor",
    "src.monitors.weibo_monitor",
    "src.monitors.bilibili_monitor",
    "src.monitors.douyin_monitor",
    "src.monitors.douyu_monitor",
    "src.monitors.xhs_monitor",
]

# 定时任务（Cron 执行）模块列表，新增定时任务时在此追加模块路径即可
TASK_MODULES: list[str] = [
    "src.tasks.log_cleanup",
    "src.tasks.ikuuu_checkin",
    "src.tasks.tieba_checkin",
    "src.tasks.weibo_chaohua_checkin",
    "src.tasks.rainyun_checkin",  # 雨云签到
    "src.tasks.enshan_checkin",  # 恩山论坛签到
    "src.tasks.fg_checkin",  # 富贵论坛签到
    "src.tasks.aliyun_checkin",  # 阿里云盘签到
    "src.tasks.smzdm_checkin",  # 什么值得买签到
    "src.tasks.zdm_draw",  # 值得买每日抽奖
    "src.tasks.tyyun_checkin",  # 天翼云盘签到
    "src.tasks.miui_checkin",  # 小米社区签到
    "src.tasks.iqiyi_checkin",  # 爱奇艺签到
    "src.tasks.lenovo_checkin",  # 联想乐豆签到
    "src.tasks.lbly_checkin",  # 丽宝乐园签到
    "src.tasks.pinzan_checkin",  # 品赞代理签到
    "src.tasks.dml_checkin",  # 达美乐任务
    "src.tasks.xiaomao_checkin",  # 小茅预约（i茅台）
    "src.tasks.ydwx_checkin",  # 一点万象签到
    "src.tasks.xingkong_checkin",  # 星空代理签到
    "src.tasks.qtw_checkin",  # 千图网签到
    "src.tasks.freenom_checkin",  # Freenom 免费域名续期
    "src.tasks.weather_push",  # 天气每日推送
    "src.tasks.kuake_checkin",  # 夸克网盘签到
    "src.tasks.kjwj_checkin",  # 科技玩家签到
    "src.tasks.fr_checkin",  # 帆软社区签到 + 摇摇乐
    "src.tasks.nine_nine_nine_task",  # 999 会员中心健康打卡
    "src.tasks.zgfc_draw",  # 中国福彩抽奖活动
    "src.tasks.ssq_500w_notice",  # 双色球开奖通知（守号+冷号机选）
    "src.tasks.demo_task",  # 二次开发示例，不需要可移除此行
]

MONITOR_JOBS: list[JobDescriptor] = []
TASK_JOBS: list[JobDescriptor] = []


def _upsert_job(jobs: list[JobDescriptor], descriptor: JobDescriptor) -> None:
    """Register a job once; module reloads replace the existing descriptor."""
    for idx, existing in enumerate(jobs):
        if existing.job_id == descriptor.job_id:
            jobs[idx] = descriptor
            return
    jobs.append(descriptor)


@asynccontextmanager
async def _task_logging_context(job_id: str):
    """
    异步上下文管理器：在任务执行期间挂载专属日志文件处理器，
    通过 TaskLogFilter + _current_job_id 保证并发任务日志隔离。
    """
    log_manager = LogManager()
    handler = log_manager.setup_task_file_logging(job_id)
    handler.addFilter(TaskLogFilter(job_id))
    logging.root.addHandler(handler)
    token = _current_job_id.set(job_id)
    try:
        yield
    finally:
        _current_job_id.reset(token)
        try:
            logging.root.removeHandler(handler)
            handler.close()
        except Exception as e:
            logger.debug("移除任务日志处理器时出错（可忽略）: %s", e)


async def run_task_with_logging(job_id: str, run_func: Callable[[], Awaitable[None]]) -> None:
    """
    在任务专属日志支持下执行任务。用于手动触发时确保也写入任务专属日志文件。
    """
    async with _task_logging_context(job_id):
        await run_func()


def monitor_job_enabled(job_id: str, config: AppConfig) -> bool:
    """监控类任务是否在配置中启用（未映射的 job_id 视为始终启用）。"""
    enable_field = MONITOR_JOB_ENABLE_FIELD_MAP.get(job_id)
    return enable_field is None or getattr(config, enable_field, True)


def register_monitor(
    job_id: str,
    run_func: Callable[[], Awaitable[None]],
    get_trigger_kwargs: Callable[[AppConfig], dict[str, Any]],
    *,
    description: str = "",
) -> None:
    """
    注册一个监控任务（间隔触发）。
    应在监控模块加载时调用，例如：register_monitor("huya_monitor", run_huya_monitor, lambda c: {"seconds": c.huya_monitor_interval_seconds})
    """

    @functools.wraps(run_func)
    async def wrapped_run_func() -> None:
        config = get_config()
        if not monitor_job_enabled(job_id, config):
            logger.debug("%s: 当前配置未启用，跳过执行", job_id)
            return
        async with _task_logging_context(job_id):
            await run_func()

    _upsert_job(
        MONITOR_JOBS,
        JobDescriptor(
            job_id=job_id,
            run_func=wrapped_run_func,
            trigger="interval",
            get_trigger_kwargs=get_trigger_kwargs,
            description=description or f"任务 {job_id}",
            original_run_func=run_func,
        )
    )
    logger.debug("已注册监控任务: %s", job_id)


def register_task(
    job_id: str,
    run_func: Callable[[], Awaitable[None]],
    get_trigger_kwargs: Callable[[AppConfig], dict[str, Any]],
    *,
    skip_if_run_today: bool = True,
    description: str = "",
) -> None:
    """
    注册一个定时任务（Cron 触发）。
    应在任务模块加载时调用，例如：register_task("ikuuu_checkin", run_checkin_once, lambda c: {"hour": h, "minute": m})

    Args:
        job_id: 任务唯一标识
        run_func: 任务执行函数
        get_trigger_kwargs: 获取触发参数的函数
        skip_if_run_today: 是否在当天已运行过时跳过（默认 True）
        description: Web 任务列表展示文案
    """
    from src.storage.database import has_run_today as check_run_today
    from src.storage.database import mark_as_run_today

    @functools.wraps(run_func)
    async def wrapped_run_func() -> None:
        enable_field = TASK_JOB_ENABLE_FIELD_MAP.get(job_id)
        if enable_field is not None:
            config = get_config()
            if not getattr(config, enable_field, False):
                logger.debug("%s: 当前配置未启用，跳过调度执行", job_id)
                return

        if skip_if_run_today and await check_run_today(job_id):
            logger.info("%s: 当天已经运行过了，跳过该任务", job_id)
            return

        async with _task_logging_context(job_id):
            await run_func()
            if skip_if_run_today:
                await mark_as_run_today(job_id)

    _upsert_job(
        TASK_JOBS,
        JobDescriptor(
            job_id=job_id,
            run_func=wrapped_run_func,
            trigger="cron",
            get_trigger_kwargs=get_trigger_kwargs,
            description=description or f"任务 {job_id}",
            original_run_func=run_func,
        )
    )
    logger.debug("已注册定时任务: %s (skip_if_run_today=%s)", job_id, skip_if_run_today)


def get_registered_task(job_id: str) -> JobDescriptor | None:
    """按 job_id 查找已注册的定时任务（青龙 CLI 等场景使用）。"""
    for job in TASK_JOBS:
        if job.job_id == job_id:
            return job
    return None


def discover_and_import_tasks_only() -> None:
    """仅导入 TASK_MODULES，供青龙 CLI 等轻量场景使用。"""
    for mod_name in TASK_MODULES:
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            logger.warning("导入任务模块 %s 失败: %s", mod_name, e)


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
