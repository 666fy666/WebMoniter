"""任务调度器模块 - 使用APScheduler进行任务调度"""
import asyncio
import logging
import signal
import sys
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.config import AppConfig, get_config


class TaskScheduler:
    """任务调度器 - 统一管理所有监控任务"""

    def __init__(self, config: Optional[AppConfig] = None):
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
        job_id: Optional[str] = None,
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
        self.logger.info(f"已添加任务: {job_id or func.__name__}")

    def add_interval_job(
        self,
        func: Callable,
        minutes: int = 1,
        job_id: Optional[str] = None,
    ):
        """
        添加间隔任务（每N分钟执行一次）
        
        Args:
            func: 要执行的异步函数
            minutes: 间隔分钟数
            job_id: 任务ID
        """
        self.add_job(
            func,
            trigger=IntervalTrigger(minutes=minutes),
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
        job_id: Optional[str] = None,
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

    def start(self):
        """启动调度器"""
        self.scheduler.start()
        self.logger.info("任务调度器已启动")

    def shutdown(self, wait: bool = True):
        """
        关闭调度器
        
        Args:
            wait: 是否等待正在执行的任务完成
        """
        self.scheduler.shutdown(wait=wait)
        self.logger.info("任务调度器已关闭")

    async def run_forever(self):
        """运行调度器直到收到停止信号"""
        # 设置信号处理
        def signal_handler(signum, frame):
            self.logger.info(f"收到信号 {signum}，准备关闭...")
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # 启动调度器
        self.start()

        try:
            # 等待关闭信号
            await self._shutdown_event.wait()
        finally:
            # 关闭调度器
            self.shutdown(wait=True)
            self.logger.info("调度器已完全关闭")


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
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(console_handler)
    
    # 设置根日志记录器的级别和格式
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # 如果没有处理器，创建一个NullHandler避免警告
    if not root_logger.handlers:
        root_logger.addHandler(logging.NullHandler())

