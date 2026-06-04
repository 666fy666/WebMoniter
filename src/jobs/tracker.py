"""
任务运行跟踪模块 - 记录定时任务的运行历史，支持检查当天是否已运行过。

功能：
- 记录任务的最后运行日期
- 检查任务当天是否已经运行过
- 提供装饰器简化使用
"""

import asyncio
import functools
import logging
import sys
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import ParamSpec, TypeVar

import aiosqlite

from src.core.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)

# 数据库文件路径（与主数据库在同一目录）；打包为 exe 时以可执行文件所在目录为基准
_base_path = (
    Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else PROJECT_ROOT
)
_data_dir = _base_path / "data"
_data_dir.mkdir(parents=True, exist_ok=True)
TASK_TRACKER_DB_PATH = (_data_dir / "data.db").resolve()

# 类型变量
P = ParamSpec("P")
T = TypeVar("T")

# 共享连接（避免每次查询都 open/close）
_shared_conn: aiosqlite.Connection | None = None
_conn_lock = asyncio.Lock()
_table_ensured = False


async def _get_connection() -> aiosqlite.Connection:
    """获取或创建共享数据库连接，首次调用时建表"""
    global _shared_conn, _table_ensured

    if _shared_conn is not None and _table_ensured:
        return _shared_conn

    async with _conn_lock:
        if _shared_conn is None:
            TASK_TRACKER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _shared_conn = await aiosqlite.connect(str(TASK_TRACKER_DB_PATH), timeout=30.0)
            await _shared_conn.execute("PRAGMA journal_mode=WAL")
            await _shared_conn.execute("PRAGMA busy_timeout=30000")
            await _shared_conn.commit()
        if not _table_ensured:
            await _shared_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_run_history (
                    job_id TEXT PRIMARY KEY,
                    last_run_date TEXT NOT NULL
                )
                """
            )
            await _shared_conn.commit()
            _table_ensured = True

    return _shared_conn


async def has_run_today(job_id: str) -> bool:
    """
    检查指定任务今天是否已经运行过。

    Args:
        job_id: 任务ID

    Returns:
        True 如果今天已经运行过，False 否则
    """
    conn = await _get_connection()
    today_str = date.today().isoformat()

    async with conn.execute(
        "SELECT last_run_date FROM task_run_history WHERE job_id = ?",
        (job_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return False
        return row[0] == today_str


async def mark_as_run_today(job_id: str) -> None:
    """
    标记指定任务今天已经运行过。

    Args:
        job_id: 任务ID
    """
    conn = await _get_connection()
    today_str = date.today().isoformat()

    await conn.execute(
        """
        INSERT OR REPLACE INTO task_run_history (job_id, last_run_date)
        VALUES (?, ?)
        """,
        (job_id, today_str),
    )
    await conn.commit()


def skip_if_run_today(
    job_id: str,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T | None]]]:
    """
    装饰器：如果任务当天已经运行过，则跳过执行。

    使用方法：
        @skip_if_run_today("my_task_id")
        async def my_task():
            # 任务逻辑
            pass

    Args:
        job_id: 任务ID

    Returns:
        装饰器函数
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T | None]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            # 检查今天是否已经运行过
            if await has_run_today(job_id):
                logger.info("%s: 当天已经运行过了，跳过该任务", job_id)
                return None

            # 执行任务
            try:
                result = await func(*args, **kwargs)
                # 任务执行成功后，标记为已运行
                await mark_as_run_today(job_id)
                return result
            except Exception:
                # 任务执行失败，不标记为已运行，允许重试
                raise

        return wrapper

    return decorator


async def run_task_if_not_run_today(
    job_id: str,
    task_func: Callable[[], Awaitable[None]],
) -> bool:
    """
    如果任务当天未运行过，则执行任务。

    这是一个辅助函数，用于在不使用装饰器的情况下检查并执行任务。

    Args:
        job_id: 任务ID
        task_func: 任务执行函数

    Returns:
        True 如果任务被执行了，False 如果跳过了
    """
    if await has_run_today(job_id):
        logger.info("%s: 当天已经运行过了，跳过该任务", job_id)
        return False

    try:
        await task_func()
        await mark_as_run_today(job_id)
        return True
    except Exception:
        # 任务执行失败，不标记为已运行
        raise


async def clear_run_history(job_id: str | None = None) -> None:
    """
    清除任务运行记录。

    Args:
        job_id: 指定任务ID则只清除该任务的记录，None 则清除所有记录
    """
    conn = await _get_connection()

    if job_id is None:
        await conn.execute("DELETE FROM task_run_history")
    else:
        await conn.execute(
            "DELETE FROM task_run_history WHERE job_id = ?",
            (job_id,),
        )
    await conn.commit()
