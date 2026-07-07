"""Runtime helpers for bounded asyncio shutdown."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
import weakref
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures.thread import _threads_queues, _worker
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_EXECUTOR_MAX_WORKERS = 32
PENDING_TASK_CANCEL_TIMEOUT_SEC = 5.0
DEFAULT_EXECUTOR_SHUTDOWN_TIMEOUT_SEC = 5.0
FORCE_EXIT_AFTER_SIGNAL_SEC = 12.0

_shutdown_requested = False
_shutdown_exit_code = 130
_watchdog_timer: threading.Timer | None = None
_watchdog_lock = threading.Lock()


def _force_process_exit(exit_code: int) -> None:
    logger.warning("关闭流程仍未结束，强制退出进程")
    logging.shutdown()
    os._exit(exit_code)


def arm_shutdown_watchdog(
    timeout: float = FORCE_EXIT_AFTER_SIGNAL_SEC,
    *,
    exit_code: int = 130,
) -> None:
    """Mark shutdown as signal-triggered and arm a last-resort process exit."""
    global _shutdown_exit_code, _shutdown_requested, _watchdog_timer
    with _watchdog_lock:
        _shutdown_requested = True
        _shutdown_exit_code = exit_code
        if _watchdog_timer is not None and _watchdog_timer.is_alive():
            return
        _watchdog_timer = threading.Timer(timeout, _force_process_exit, args=(exit_code,))
        _watchdog_timer.daemon = True
        _watchdog_timer.start()


def _exit_if_signal_shutdown_completed() -> None:
    if not _shutdown_requested:
        return
    logging.shutdown()
    os._exit(_shutdown_exit_code)


class DaemonThreadPoolExecutor(ThreadPoolExecutor):
    """ThreadPoolExecutor variant whose workers do not keep the process alive."""

    def _worker_args(self, executor_ref: weakref.ReferenceType) -> tuple:
        if hasattr(self, "_create_worker_context"):
            return (executor_ref, self._create_worker_context(), self._work_queue)
        return (
            executor_ref,
            self._work_queue,
            getattr(self, "_initializer", None),
            getattr(self, "_initargs", ()),
        )

    def _adjust_thread_count(self) -> None:
        if self._idle_semaphore.acquire(timeout=0):
            return

        def weakref_cb(_, q=self._work_queue):
            q.put(None)

        num_threads = len(self._threads)
        if num_threads < self._max_workers:
            thread_name = f"{self._thread_name_prefix or self}_{num_threads}"
            thread = threading.Thread(
                name=thread_name,
                target=_worker,
                args=self._worker_args(weakref.ref(self, weakref_cb)),
            )
            thread.daemon = True
            thread.start()
            self._threads.add(thread)
            _threads_queues[thread] = self._work_queue


def _new_event_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.new_event_loop()
    loop.set_default_executor(
        DaemonThreadPoolExecutor(
            max_workers=DEFAULT_EXECUTOR_MAX_WORKERS,
            thread_name_prefix="webmoniter",
        )
    )
    return loop


def _cancel_pending_tasks(loop: asyncio.AbstractEventLoop) -> None:
    pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
    if not pending:
        return

    for task in pending:
        task.cancel()

    done, still_pending = loop.run_until_complete(
        asyncio.wait(pending, timeout=PENDING_TASK_CANCEL_TIMEOUT_SEC)
    )
    for task in done:
        if task.cancelled():
            continue
        exc = task.exception()
        if exc is not None:
            loop.call_exception_handler(
                {
                    "message": "unhandled exception during shutdown",
                    "exception": exc,
                    "task": task,
                }
            )

    if still_pending:
        logger.warning("仍有 %d 个异步任务未能在超时内取消，将继续退出", len(still_pending))


def _shutdown_default_executor(loop: asyncio.AbstractEventLoop) -> None:
    executor = getattr(loop, "_default_executor", None)
    if executor is None:
        return

    # Avoid loop.shutdown_default_executor(timeout=...) here: CPython implements it
    # with a non-daemon helper thread, which can itself keep the process alive.
    executor.shutdown(wait=False, cancel_futures=True)
    setattr(loop, "_executor_shutdown_called", True)

    deadline = time.monotonic() + DEFAULT_EXECUTOR_SHUTDOWN_TIMEOUT_SEC
    alive_threads = []
    for thread in list(getattr(executor, "_threads", ())):
        remaining = max(0.0, deadline - time.monotonic())
        if remaining:
            thread.join(timeout=remaining)
        if thread.is_alive():
            alive_threads.append(thread)

    if alive_threads:
        for thread in alive_threads:
            _threads_queues.pop(thread, None)
        logger.warning("默认线程池仍有 %d 个线程未结束，将继续退出", len(alive_threads))


def run_async_app(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    Run the main coroutine with bounded executor shutdown.

    asyncio.run() waits up to Python's default thread-join timeout (300s on
    Python 3.13). This project uses asyncio.to_thread() for network/Selenium
    tasks, so Ctrl+C should not inherit that long wait during normal shutdown.
    """
    loop = _new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        try:
            _cancel_pending_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
            _shutdown_default_executor(loop)
        finally:
            asyncio.set_event_loop(None)
            loop.close()
            _exit_if_signal_shutdown_completed()
