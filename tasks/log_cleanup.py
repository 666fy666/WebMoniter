"""定时任务：按配置时间清理过期日志文件"""

import logging

from src.config import get_config
from src.log_manager import LogManager

logger = logging.getLogger(__name__)


async def cleanup_logs() -> None:
    """清理旧日志文件任务。从配置读取保留天数与执行时间。"""
    config = get_config(reload=True)
    log_manager = LogManager(retention_days=config.retention_days)
    log_manager.cleanup_old_logs()
