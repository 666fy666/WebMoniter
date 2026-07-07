"""Log API routes."""

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from src.jobs.registry import MONITOR_JOBS, TASK_JOBS, discover_and_import
from src.web.auth import check_login

logger = logging.getLogger(__name__)
router = APIRouter()


def _read_log_file_sync(file_path: Path, num_lines: int) -> tuple[list, int]:
    """同步读取日志文件最后 N 行。处理文件写入时的读取冲突，带重试。返回 (最近行列表, 总行数)。"""

    def _do_read() -> tuple[list, int]:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()

            if file_size < 1024 * 1024:
                f.seek(0)
                all_lines = f.readlines()
            else:
                estimated_bytes = num_lines * 200
                read_start = max(0, file_size - estimated_bytes)
                f.seek(read_start)
                if read_start > 0:
                    f.readline()
                all_lines = f.readlines()

            if len(all_lines) > num_lines:
                recent_lines = all_lines[-num_lines:]
            else:
                recent_lines = all_lines
            return recent_lines, len(all_lines)

    def _do_read_binary() -> tuple[list, int]:
        with open(file_path, "rb") as f:
            content = f.read()
        text = content.decode("utf-8", errors="ignore")
        all_lines = text.splitlines(keepends=True)
        recent_lines = all_lines[-num_lines:] if len(all_lines) > num_lines else all_lines
        return recent_lines, len(all_lines)

    max_retries = 5
    retry_delay = 0.2

    for attempt in range(max_retries):
        try:
            return _do_read()
        except (OSError, PermissionError):
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            try:
                return _do_read_binary()
            except Exception as final_e:
                logger.error("读取日志文件失败（所有方法都失败）: %s", final_e)
                raise
        except Exception as e:
            logger.error("读取日志文件时发生未知错误: %s", e)
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise
    return [], 0


@router.get("/api/logs")
async def get_logs(request: Request, lines: int = 100, task: str | None = None):
    """获取日志内容。不传 task 时返回今日总日志，传 task 时返回指定任务的今日日志"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        from src.jobs.log_manager import LogManager

        log_manager = LogManager()

        if task:
            log_file = log_manager.get_task_log_file(task, date_format="%Y%m%d")
        else:
            log_file = log_manager.get_log_file("main", date_format="%Y%m%d")

        if not log_file.exists():
            return JSONResponse(
                {"logs": [], "message": "今日暂无日志" if not task else f"任务 {task} 今日暂无日志"}
            )

        try:
            recent_lines, total_lines = await asyncio.wait_for(
                asyncio.to_thread(_read_log_file_sync, log_file, lines),
                timeout=10.0,
            )
        except TimeoutError:
            logger.error("读取日志文件超时: %s", log_file)
            return JSONResponse({"error": "读取日志超时，请稍后重试"}, status_code=504)

        return JSONResponse({"logs": recent_lines, "total_lines": total_lines})
    except Exception as e:
        logger.error("读取日志失败: %s", e, exc_info=True)
        return JSONResponse({"error": f"读取日志失败: {str(e)}"}, status_code=500)


@router.get("/api/logs/tasks")
async def get_log_tasks_list(request: Request):
    """获取今日有日志文件的任务 ID 列表，以及全部任务列表（用于前端下拉选择）"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        from src.jobs.log_manager import LogManager

        discover_and_import()
        log_manager = LogManager()
        date_str = datetime.now().strftime("%Y%m%d")
        tasks_with_logs = log_manager.list_task_log_files_for_date(date_str)

        all_tasks = []
        for job in MONITOR_JOBS + TASK_JOBS:
            all_tasks.append({"job_id": job.job_id, "has_log_today": job.job_id in tasks_with_logs})

        return JSONResponse(
            {
                "all_tasks": all_tasks,
                "tasks_with_logs": tasks_with_logs,
            }
        )
    except Exception as e:
        logger.error("获取任务日志列表失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)
