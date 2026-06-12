"""任务运行跟踪 - 记录定时任务运行历史（实现见 storage.database）。"""

from src.storage.database import clear_run_history, has_run_today, mark_as_run_today

__all__ = ["has_run_today", "mark_as_run_today", "clear_run_history"]
