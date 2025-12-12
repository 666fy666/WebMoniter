"""日志管理模块 - 统一管理日志文件"""

import logging
import logging.handlers
import time
from datetime import datetime
from pathlib import Path


class DailyRotatingFileHandler(logging.FileHandler):
    """按日期自动轮转的文件处理器

    每次写入日志时检查当前日期，如果日期变化则切换到新的日志文件
    """

    def __init__(
        self,
        log_dir: Path,
        name: str,
        date_format: str = "%Y%m%d",
        encoding: str = "utf-8",
    ):
        """
        初始化按日期轮转的文件处理器

        Args:
            log_dir: 日志目录
            name: 日志文件名前缀
            date_format: 日期格式
            encoding: 文件编码
        """
        # 先保存自定义属性（使用不同的属性名避免与父类的name属性冲突）
        self.log_dir = log_dir
        self.log_name = name  # 使用 log_name 避免与父类的 name 属性冲突
        self.date_format = date_format
        self.current_date = None

        # 初始化当前日期和文件路径
        today = datetime.now().strftime(self.date_format)
        self.current_date = today
        current_file = self.log_dir / f"{self.log_name}_{today}.log"

        # 确保目录存在
        current_file.parent.mkdir(parents=True, exist_ok=True)

        # 调用父类构造函数
        super().__init__(str(current_file), encoding=encoding, delay=False)

    def _update_file(self):
        """更新当前日期和文件路径"""
        today = datetime.now().strftime(self.date_format)

        # 如果日期没有变化，不需要更新
        if today == self.current_date:
            return

        # 日期变化了，更新文件路径
        self.current_date = today
        new_file = self.log_dir / f"{self.log_name}_{today}.log"
        new_file_str = str(new_file)

        # 如果文件路径变化了，需要关闭旧文件并打开新文件
        if self.baseFilename != new_file_str:
            # 关闭旧文件
            if self.stream:
                self.stream.close()
                self.stream = None

            # 更新文件路径
            self.baseFilename = new_file_str

            # 确保目录存在
            new_file.parent.mkdir(parents=True, exist_ok=True)

            # 重新打开新文件
            if not self.delay:
                self.stream = self._open()

    def emit(self, record):
        """发送日志记录（在写入前检查日期）"""
        # 检查日期是否变化
        self._update_file()

        # 调用父类的emit方法写入日志
        super().emit(record)


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
    ) -> DailyRotatingFileHandler:
        """
        设置文件日志处理器（按日期自动轮转）

        Args:
            name: 日志文件名前缀
            log_level: 日志级别
            date_format: 日期格式

        Returns:
            文件处理器（DailyRotatingFileHandler，每次写入时检查日期并自动切换）
        """
        # 使用自定义的 DailyRotatingFileHandler，每次写入时检查日期
        file_handler = DailyRotatingFileHandler(
            log_dir=self.log_dir,
            name=name,
            date_format=date_format,
            encoding="utf-8",
        )

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
