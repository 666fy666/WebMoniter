"""Tests for runtime event-loop helpers."""

from __future__ import annotations

import asyncio
import threading

from src.core.runtime import DaemonThreadPoolExecutor, run_async_app


def test_daemon_thread_pool_executor_runs_daemon_workers() -> None:
    executor = DaemonThreadPoolExecutor(max_workers=1, thread_name_prefix="test-webmoniter")
    try:
        future = executor.submit(lambda: threading.current_thread().daemon)
        assert future.result(timeout=2) is True
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_run_async_app_supports_asyncio_to_thread() -> None:
    async def run_in_thread() -> str:
        return await asyncio.to_thread(lambda: "ok")

    assert run_async_app(run_in_thread()) == "ok"
