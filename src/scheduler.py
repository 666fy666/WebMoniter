"""任务调度器模块 - 使用APScheduler进行任务调度"""

import asyncio
import logging
import signal
import sys
import threading
from collections.abc import Callable

# 控制台日志分隔符：在「任务源」日志（监控/定时任务/主流程）与上一组推送之间插入，提升阅读体验
_LOG_SEPARATOR = "─" * 60

# 视为「任务源」的 logger 名称：监控类、定时任务模块、主入口
def _is_task_source(name: str) -> bool:
    return (
        "Monitor" in name
        or name.startswith("tasks.")
        or name == "__main__"
    )

# 视为「同一事件内推送」的 logger 名称：推送渠道，不在此前插分隔符
def _is_push_channel(name: str) -> bool:
    return name in (
        "WxPusher",
        "DingtalkBot",
        "FeishuBot",
        "WeComApps",
        "PushChannelManager",
    )


class TaskGroupFormatter(logging.Formatter):
    """在任务组之间插入分隔符的 Formatter，仅用于控制台。"""

    _last_logger_name: str | None = None
    _lock = threading.Lock()

    def format(self, record: logging.LogRecord) -> str:
        name = record.name
        base_fmt = super().format(record)
        with self._lock:
            prev = TaskGroupFormatter._last_logger_name
            need_sep = (
                _is_task_source(name)
                and (
                    prev is None
                    or _is_push_channel(prev)
                    or (_is_task_source(prev) and prev != name)
                )
            )
            TaskGroupFormatter._last_logger_name = name
        if need_sep:
            return f"\n{_LOG_SEPARATOR}\n{base_fmt}"
        return base_fmt

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.config import AppConfig, get_config


class TaskScheduler:
    """任务调度器 - 统一管理所有监控任务"""

    def __init__(self, config: AppConfig | None = None):
        """
        初始化调度器

        Args:
            config: 应用配置，如果为None则自动加载
        """
        self.config = config or get_config()
        self.scheduler = AsyncIOScheduler()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._shutdown_event = asyncio.Event()

    def add_job(
        self,
        func: Callable,
        trigger: str | IntervalTrigger | CronTrigger,
        job_id: str | None = None,
        **kwargs,
    ):
        """
        添加定时任务

        Args:
            func: 要执行的异步函数
            trigger: 触发器，可以是字符串（如 "interval", "cron"）或触发器对象
            job_id: 任务ID，如果不提供则自动生成
            **kwargs: 传递给触发器的其他参数
        """
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            **kwargs,
        )
        self.logger.debug("已添加任务: %s", job_id or func.__name__)

    def add_interval_job(
        self,
        func: Callable,
        seconds: int | None = None,
        minutes: int | None = None,
        hours: int | None = None,
        job_id: str | None = None,
    ):
        """
        添加间隔任务

        Args:
            func: 要执行的异步函数
            seconds: 间隔秒数（优先级最高）
            minutes: 间隔分钟数
            hours: 间隔小时数
            job_id: 任务ID

        注意：seconds、minutes、hours 至少需要提供一个，如果提供多个，优先级为 seconds > minutes > hours
        """
        trigger_kwargs = {}
        if seconds is not None:
            trigger_kwargs["seconds"] = seconds
        elif minutes is not None:
            trigger_kwargs["minutes"] = minutes
        elif hours is not None:
            trigger_kwargs["hours"] = hours
        else:
            # 默认使用1分钟
            trigger_kwargs["minutes"] = 1

        self.add_job(
            func,
            trigger=IntervalTrigger(**trigger_kwargs),
            job_id=job_id,
        )

    def add_cron_job(
        self,
        func: Callable,
        minute: str = "*",
        hour: str = "*",
        day: str = "*",
        month: str = "*",
        day_of_week: str = "*",
        job_id: str | None = None,
    ):
        """
        添加Cron任务

        Args:
            func: 要执行的异步函数
            minute: 分钟（cron格式，如 "*/2" 表示每2分钟）
            hour: 小时
            day: 日期
            month: 月份
            day_of_week: 星期几
            job_id: 任务ID
        """
        self.add_job(
            func,
            trigger=CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
            ),
            job_id=job_id,
        )

    def update_interval_job(
        self,
        job_id: str,
        seconds: int | None = None,
        minutes: int | None = None,
        hours: int | None = None,
    ):
        """
        更新间隔任务的间隔时间（用于热重载）

        Args:
            job_id: 任务ID
            seconds: 间隔秒数（优先级最高）
            minutes: 间隔分钟数
            hours: 间隔小时数

        注意：seconds、minutes、hours 至少需要提供一个，如果提供多个，优先级为 seconds > minutes > hours

        Returns:
            更新信息字符串，如果更新失败返回None
        """
        job = self.scheduler.get_job(job_id)
        if job is None:
            self.logger.warning(f"任务 {job_id} 不存在，无法更新间隔时间")
            return None

        # 构建新的触发器参数
        trigger_kwargs = {}
        if seconds is not None:
            trigger_kwargs["seconds"] = seconds
        elif minutes is not None:
            trigger_kwargs["minutes"] = minutes
        elif hours is not None:
            trigger_kwargs["hours"] = hours
        else:
            self.logger.warning(f"未提供有效的间隔时间参数，无法更新任务 {job_id}")
            return None

        # 创建新的触发器
        new_trigger = IntervalTrigger(**trigger_kwargs)

        # 更新任务的触发器
        job.reschedule(trigger=new_trigger)
        # 返回更新信息，不直接输出日志
        if seconds is not None:
            return f"{job_id}(间隔: {seconds}秒)"
        if minutes is not None:
            return f"{job_id}(间隔: {minutes}分钟)"
        if hours is not None:
            return f"{job_id}(间隔: {hours}小时)"
        return None

    def update_cron_job(
        self,
        job_id: str,
        minute: str | None = None,
        hour: str | None = None,
        day: str | None = None,
        month: str | None = None,
        day_of_week: str | None = None,
    ):
        """
        更新Cron任务的执行时间（用于热重载）

        Args:
            job_id: 任务ID
            minute: 分钟（cron格式，如 "0" 表示整点）
            hour: 小时（cron格式，如 "2" 表示2点）
            day: 日期（cron格式，默认 "*"）
            month: 月份（cron格式，默认 "*"）
            day_of_week: 星期几（cron格式，默认 "*"）

        Returns:
            更新信息字符串，如果更新失败返回None
        """
        job = self.scheduler.get_job(job_id)
        if job is None:
            self.logger.warning(f"任务 {job_id} 不存在，无法更新执行时间")
            return None

        # 获取当前触发器的参数
        current_trigger = job.trigger
        if not isinstance(current_trigger, CronTrigger):
            self.logger.warning(f"任务 {job_id} 不是Cron任务，无法更新")
            return None

        # 使用新参数或保留旧参数（通过字符串表示获取）
        # CronTrigger 的字符串表示格式为: "cron[year='*', month='*', day='*', week='*', day_of_week='*', hour='*', minute='*']"
        # 简化处理：直接使用提供的参数，未提供的使用默认值 "*"
        new_minute = minute if minute is not None else "*"
        new_hour = hour if hour is not None else "*"
        new_day = day if day is not None else "*"
        new_month = month if month is not None else "*"
        new_day_of_week = day_of_week if day_of_week is not None else "*"

        # 创建新的触发器
        new_trigger = CronTrigger(
            minute=new_minute,
            hour=new_hour,
            day=new_day,
            month=new_month,
            day_of_week=new_day_of_week,
        )

        # 更新任务的触发器
        job.reschedule(trigger=new_trigger)
        # 返回更新信息，不直接输出日志
        return f"{job_id}(执行时间: {new_hour}:{new_minute})"

    def start(self):
        """启动调度器"""
        self.scheduler.start()
        self.logger.debug("调度器已启动")

    def shutdown(self, wait: bool = True):
        """
        关闭调度器

        Args:
            wait: 是否等待正在执行的任务完成
        """
        self.scheduler.shutdown(wait=wait)
        self.logger.debug("调度器已关闭")

    async def run_forever(self):
        """运行调度器直到收到停止信号"""

        def signal_handler(signum, frame):
            self.logger.debug("收到信号 %s，准备关闭", signum)
            self._shutdown_event.set()

        # Windows平台不支持SIGTERM，需要检查平台
        signal.signal(signal.SIGINT, signal_handler)
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, signal_handler)

        # 启动调度器
        self.start()

        try:
            # 等待关闭信号
            await self._shutdown_event.wait()
        finally:
            self.shutdown(wait=True)


def setup_logging(log_level: str = "INFO", console_output: bool = None):
    """
    设置日志配置

    Args:
        log_level: 日志级别
        console_output: 是否输出到控制台，None时自动检测（非TTY环境不输出到控制台）
    """
    import sys

    # 自动检测是否为交互式终端
    if console_output is None:
        # 如果标准输出不是TTY（如nohup后台运行），则不输出到控制台
        console_output = sys.stdout.isatty()

    # 先清除现有的处理器（避免重复）
    root_logger = logging.root
    root_logger.handlers.clear()

    # 只在交互式终端或明确指定时才添加控制台处理器
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(
            TaskGroupFormatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(console_handler)

    # 设置根日志记录器的级别和格式
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # 降低APScheduler的日志级别，减少冗余的调度器日志
    # 只记录WARNING及以上级别的日志，减少INFO级别的"Running job"、"executed successfully"等日志
    apscheduler_logger = logging.getLogger("apscheduler")
    apscheduler_logger.setLevel(logging.WARNING)

    # 如果没有处理器，创建一个NullHandler避免警告
    if not root_logger.handlers:
        root_logger.addHandler(logging.NullHandler())
