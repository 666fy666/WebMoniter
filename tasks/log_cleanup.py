"""定时任务：按配置时间清理过期日志文件"""

import logging

from src.config import AppConfig, get_config, parse_checkin_time
from src.job_registry import register_task
from src.log_manager import LogManager

logger = logging.getLogger(__name__)


async def cleanup_logs() -> None:
    """清理旧日志文件任务。从配置读取保留天数。"""
    config = get_config(reload=True)
    log_manager = LogManager(retention_days=config.retention_days)
    log_manager.cleanup_old_logs()


def _get_cleanup_logs_trigger_kwargs(config: AppConfig) -> dict:
    """供注册表与配置热重载使用。"""
    hour, minute = parse_checkin_time(getattr(config, "log_cleanup_time", "02:10") or "02:10")
    return {
        "minute": minute,
        "hour": hour,
    }


register_task("log_cleanup", cleanup_logs, _get_cleanup_logs_trigger_kwargs)
