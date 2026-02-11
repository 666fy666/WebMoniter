"""日志管理模块 - 统一管理日志文件"""

import contextvars
import logging
import logging.handlers
import re
import time
from datetime import datetime
from pathlib import Path

# 当前执行中的任务 ID，用于任务专属日志文件只记录该任务的日志（避免多任务并发时混在一起）
_current_job_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_job_id", default=None
)


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


class TaskLogFilter(logging.Filter):
    """仅当「当前执行中的任务」与 handler 所属任务一致时才写入，避免多任务并发时各任务日志混入同一文件。"""

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id

    def filter(self, record: logging.LogRecord) -> bool:
        current = _current_job_id.get()
        return current == self.job_id


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

    def get_task_log_file(self, job_id: str, date_format: str = "%Y%m%d") -> Path:
        """
        获取任务专属日志文件路径（按任务名和日期分类）

        Args:
            job_id: 任务ID
            date_format: 日期格式

        Returns:
            任务日志文件路径，格式为 task_{job_id}_{YYYYMMDD}.log
        """
        date_str = datetime.now().strftime(date_format)
        # 任务名中可能包含非法文件名字符，用下划线替换
        safe_job_id = job_id.replace("/", "_").replace("\\", "_")
        return self.log_dir / f"task_{safe_job_id}_{date_str}.log"

    def list_task_log_files_for_date(self, date_str: str) -> list[str]:
        """
        列出指定日期下所有任务日志文件对应的 job_id 列表

        Args:
            date_str: 日期字符串，格式 YYYYMMDD

        Returns:
            job_id 列表（从 task_xxx_YYYYMMDD.log 中解析出 xxx）
        """
        prefix = "task_"
        date_suffix = f"_{date_str}"
        job_ids = []
        try:
            for log_file in self.log_dir.glob("task_*.log"):
                name = log_file.stem  # task_xxx_YYYYMMDD
                if name.endswith(date_suffix) and name.startswith(prefix):
                    middle = name[len(prefix) : -len(date_suffix)]
                    if middle:
                        job_ids.append(middle)
        except Exception as e:
            self.logger.warning(f"列出任务日志文件时出错: {e}")
        return sorted(set(job_ids))

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

    def setup_task_file_logging(
        self,
        job_id: str,
        log_level: str = "INFO",
        date_format: str = "%Y%m%d",
    ) -> DailyRotatingFileHandler:
        """
        创建设置任务专属文件日志处理器（按日期自动轮转）

        Args:
            job_id: 任务ID
            log_level: 日志级别
            date_format: 日期格式

        Returns:
            文件处理器，日志文件格式为 task_{job_id}_{YYYYMMDD}.log
        """
        safe_job_id = job_id.replace("/", "_").replace("\\", "_")
        name = f"task_{safe_job_id}"
        return self.setup_file_logging(name=name, log_level=log_level, date_format=date_format)

    def cleanup_old_logs(self, cleanup_log_name: str = "cleanup"):
        """
        清理旧的日志文件

        Args:
            cleanup_log_name: 清理日志的文件名前缀
        """
        self.logger.debug("开始清理超过 %s 天的日志文件", self.retention_days)

        deleted_count = 0
        today = datetime.now().date()

        try:
            for log_file in self.log_dir.glob("*.log"):
                # 跳过清理日志本身
                if cleanup_log_name in log_file.name:
                    continue

                try:
                    # 从文件名中提取日期（格式：name_YYYYMMDD.log）
                    # 尝试匹配日期格式 YYYYMMDD
                    date_match = re.search(r"(\d{8})", log_file.name)
                    if date_match:
                        date_str = date_match.group(1)
                        try:
                            file_date = datetime.strptime(date_str, "%Y%m%d").date()
                            # 计算文件日期距离今天的天数
                            days_ago = (today - file_date).days
                            # 如果超过保留天数，删除文件
                            # 保留N天意味着保留今天、昨天、...、N-1天前，所以删除 >= N 天的
                            if days_ago >= self.retention_days:
                                log_file.unlink()
                                deleted_count += 1
                                self.logger.debug(
                                    f"已删除: {log_file.name} (文件日期: {file_date}, 距今{days_ago}天)"
                                )
                        except ValueError:
                            # 如果日期格式解析失败，使用文件修改时间作为备选方案
                            cutoff_time = time.time() - (self.retention_days * 24 * 3600)
                            if log_file.stat().st_mtime < cutoff_time:
                                log_file.unlink()
                                deleted_count += 1
                                self.logger.debug(
                                    f"已删除: {log_file.name} (无法解析日期，使用修改时间)"
                                )
                    else:
                        # 如果文件名中没有日期格式，使用文件修改时间作为备选方案
                        cutoff_time = time.time() - (self.retention_days * 24 * 3600)
                        if log_file.stat().st_mtime < cutoff_time:
                            log_file.unlink()
                            deleted_count += 1
                            self.logger.debug(
                                f"已删除: {log_file.name} (文件名无日期格式，使用修改时间)"
                            )
                except Exception as e:
                    self.logger.warning(f"删除日志文件失败 {log_file.name}: {e}")

            if deleted_count > 0:
                self.logger.info("日志清理: 删除 %d 个文件", deleted_count)

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
