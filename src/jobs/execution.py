"""Bounded execution shared by HTTP, startup and scheduled jobs.

Run records are local operational state, independent of the mirrored business DB.
Interrupted jobs are never replayed automatically: a task may have external effects.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite

from src.core.paths import DATA_DIR

logger = logging.getLogger(__name__)
RunFunction = Callable[[], Awaitable[object]]


class QueueFullError(RuntimeError):
    pass


class ExecutionService:
    def __init__(self, path: Path, concurrency: int = 4, capacity: int = 100):
        self.path = path
        self.concurrency = concurrency
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=capacity)
        self.active: dict[str, str] = {}
        self.workers: list[asyncio.Task] = []
        self.lock = asyncio.Lock()
        self.db: aiosqlite.Connection | None = None
        self.accepting = False

    async def start(self) -> None:
        async with self.lock:
            if self.db is not None:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = await aiosqlite.connect(self.path)
            try:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA busy_timeout=5000")
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, "
                    "source TEXT NOT NULL, status TEXT NOT NULL, created_at REAL NOT NULL, "
                    "started_at REAL, finished_at REAL, message TEXT NOT NULL DEFAULT '')"
                )
                await db.execute("CREATE INDEX IF NOT EXISTS runs_created ON runs(created_at DESC)")
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS runs_job ON runs(job_id, created_at DESC)"
                )
                await db.execute(
                    "UPDATE runs SET status='interrupted', finished_at=?, message='服务重启，执行已中断' "
                    "WHERE status IN ('queued', 'running')",
                    (time.time(),),
                )
                await db.commit()
            except BaseException:
                await db.close()
                raise
            self.db = db
            self.accepting = True
            self.workers = [
                asyncio.create_task(self._worker(), name=f"job-worker-{i}")
                for i in range(self.concurrency)
            ]

    async def submit(self, job_id: str, func: RunFunction, source: str = "manual") -> dict:
        async with self.lock:
            if not self.accepting or self.db is None:
                raise QueueFullError("执行服务尚未就绪或正在关闭")
            if job_id in self.active:
                return {"run_id": self.active[job_id], "duplicate": True}
            if self.queue.full():
                raise QueueFullError("任务队列已满，请稍后重试")
            run_id = uuid.uuid4().hex
            await self.db.execute(
                "INSERT INTO runs(run_id,job_id,source,status,created_at) VALUES(?,?,?,'queued',?)",
                (run_id, job_id, source, time.time()),
            )
            await self.db.commit()
            self.active[job_id] = run_id
            self.queue.put_nowait((run_id, job_id, func))
            return {"run_id": run_id, "duplicate": False}

    async def _update(self, run_id: str, status: str, message: str = "") -> None:
        async with self.lock:
            if self.db is None:
                return
            column = "started_at" if status == "running" else "finished_at"
            await self.db.execute(
                f"UPDATE runs SET status=?, {column}=?, message=? WHERE run_id=?",
                (status, time.time(), message[:500], run_id),
            )
            # A bounded operational history; active records are always retained.
            await self.db.execute(
                "DELETE FROM runs WHERE status NOT IN ('queued','running') AND run_id NOT IN "
                "(SELECT run_id FROM runs ORDER BY created_at DESC LIMIT 10000)"
            )
            await self.db.commit()

    async def _worker(self) -> None:
        while True:
            run_id, job_id, func = await self.queue.get()
            try:
                await self._update(run_id, "running")
                result = await func()
                from src.jobs.task_outcome import TaskResult

                state = (
                    result.status
                    if isinstance(result, TaskResult)
                    else ("failed" if result is False else "success")
                )
                await self._update(run_id, state)
            except asyncio.CancelledError:
                await self._update(run_id, "interrupted", "服务关闭，执行已中断")
                raise
            except TimeoutError:
                await self._update(run_id, "timeout", "任务执行超时")
            except Exception as exc:
                # Exception text may contain credentials or upstream response bodies.
                logger.error("任务执行失败 job=%s error=%s", job_id, type(exc).__name__)
                await self._update(run_id, "failed", "执行失败，请检查任务配置和日志")
            finally:
                self.active.pop(job_id, None)
                self.queue.task_done()

    async def list_runs(
        self, limit: int = 50, run_id: str | None = None, *, latest_per_job: bool = False
    ) -> list[dict]:
        async with self.lock:
            if self.db is None:
                return []
            query = "SELECT run_id,job_id,source,status,created_at,started_at,finished_at,message FROM runs"
            params: tuple = ()
            if run_id:
                query += " WHERE run_id=?"
                params = (run_id,)
            elif latest_per_job:
                query += (
                    " WHERE rowid IN (SELECT r.rowid FROM runs r WHERE r.rowid="
                    "(SELECT n.rowid FROM runs n WHERE n.job_id=r.job_id "
                    "ORDER BY n.created_at DESC,n.rowid DESC LIMIT 1))"
                )
            query += " ORDER BY created_at DESC LIMIT ?"
            async with self.db.execute(query, (*params, min(max(limit, 1), 200))) as cursor:
                names = [column[0] for column in cursor.description]
                return [dict(zip(names, row, strict=True)) for row in await cursor.fetchall()]

    async def healthy(self) -> bool:
        async with self.lock:
            if not self.accepting or self.db is None or any(w.done() for w in self.workers):
                return False
            await self.db.execute("SELECT 1")
            return True

    async def stop(self) -> None:
        self.accepting = False
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        async with self.lock:
            if self.db is not None:
                await self.db.execute(
                    "UPDATE runs SET status='interrupted',finished_at=? "
                    "WHERE status IN ('queued','running')",
                    (time.time(),),
                )
                await self.db.commit()
                await self.db.close()
                self.db = None
            self.active.clear()
            self.workers.clear()
            while not self.queue.empty():
                self.queue.get_nowait()
                self.queue.task_done()


_service: ExecutionService | None = None


def get_execution_service() -> ExecutionService:
    global _service
    if _service is None:
        _service = ExecutionService(DATA_DIR / "runs.db")
    return _service


def scheduled_runner(job_id: str, func: RunFunction) -> RunFunction:
    async def submit():
        service = get_execution_service()
        await service.start()
        try:
            await service.submit(job_id, func, "scheduled")
        except QueueFullError:
            logger.warning("任务队列已满，跳过本次调度 job=%s", job_id)

    return submit
