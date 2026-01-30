"""定时任务：按配置时间清理过期日志文件"""

import logging

from src.config import AppConfig, get_config
from src.job_registry import register_task
from src.log_manager import LogManager

logger = logging.getLogger(__name__)


async def cleanup_logs() -> None:
    """清理旧日志文件任务。从配置读取保留天数与执行时间。"""
    config = get_config(reload=True)
    log_manager = LogManager(retention_days=config.retention_days)
    log_manager.cleanup_old_logs()


def _get_cleanup_logs_trigger_kwargs(config: AppConfig) -> dict:
    """供注册表与配置热重载使用。"""
    return {
        "minute": str(config.cleanup_logs_minute),
        "hour": str(config.cleanup_logs_hour),
    }


register_task("cleanup_logs", cleanup_logs, _get_cleanup_logs_trigger_kwargs)
