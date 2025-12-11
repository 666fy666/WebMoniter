"""日志管理模块 - 统一管理日志文件"""
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class LogManager:
    """日志管理器 - 负责日志文件的创建、清理等操作"""

    def __init__(self, log_dir: str = "logs", retention_days: int = 3):
        """
        初始化日志管理器
        
        Args:
            log_dir: 日志目录路径
            retention_days: 日志保留天数，超过此天数的日志将被删除
        """
        self.log_dir = Path(log_dir)
        self.retention_days = retention_days
        self.logger = logging.getLogger(self.__class__.__name__)

        # 确保日志目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def get_log_file(self, name: str, date_format: str = "%Y%m%d") -> Path:
        """
        获取日志文件路径（按日期分割）
        
        Args:
            name: 日志文件名前缀
            date_format: 日期格式
            
        Returns:
            日志文件路径
        """
        date_str = datetime.now().strftime(date_format)
        return self.log_dir / f"{name}_{date_str}.log"

    def setup_file_logging(
        self,
        name: str,
        log_level: str = "INFO",
        date_format: str = "%Y%m%d",
    ) -> logging.FileHandler:
        """
        设置文件日志处理器
        
        Args:
            name: 日志文件名前缀
            log_level: 日志级别
            date_format: 日期格式
            
        Returns:
            文件处理器
        """
        log_file = self.get_log_file(name, date_format)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        return file_handler

    def cleanup_old_logs(self, cleanup_log_name: str = "cleanup"):
        """
        清理旧的日志文件
        
        Args:
            cleanup_log_name: 清理日志的文件名前缀
        """
        self.logger.info(f"开始清理超过{self.retention_days}天的日志文件...")

        deleted_count = 0
        cutoff_time = time.time() - (self.retention_days * 24 * 3600)

        try:
            for log_file in self.log_dir.glob("*.log"):
                # 跳过清理日志本身
                if cleanup_log_name in log_file.name:
                    continue

                try:
                    # 检查文件修改时间
                    if log_file.stat().st_mtime < cutoff_time:
                        log_file.unlink()
                        deleted_count += 1
                        self.logger.debug(f"已删除: {log_file.name}")
                except Exception as e:
                    self.logger.warning(f"删除日志文件失败 {log_file.name}: {e}")

            if deleted_count == 0:
                self.logger.info("清理完成: 没有需要删除的日志文件")
            else:
                self.logger.info(f"清理完成: 共删除 {deleted_count} 个日志文件")

        except Exception as e:
            self.logger.error(f"清理日志文件时出错: {e}")

    def get_log_size(self) -> int:
        """
        获取日志目录总大小（字节）
        
        Returns:
            日志目录总大小
        """
        total_size = 0
        try:
            for log_file in self.log_dir.glob("*.log"):
                total_size += log_file.stat().st_size
        except Exception as e:
            self.logger.warning(f"计算日志目录大小时出错: {e}")
        return total_size

    def format_size(self, size_bytes: int) -> str:
        """
        格式化文件大小
        
        Args:
            size_bytes: 字节数
            
        Returns:
            格式化后的大小字符串
        """
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

