"""main.py 中 config_watcher 生命周期：启动后无论成败都应 stop。"""

from __future__ import annotations

import logging
import signal

import pytest

from main import _stop_config_watcher
from src.jobs.lifecycle import _run_initial_pass, build_uvicorn_server
from src.jobs.registry import JobDescriptor
from src.jobs.scheduler import TaskScheduler
from src.jobs.task_outcome import TASK_SUCCESS
from src.settings.config import AppConfig

logger = logging.getLogger("test")


class _RecordingWatcher:
    def __init__(self) -> None:
        self.stop_calls = 0

    async def stop(self) -> None:
        self.stop_calls += 1


@pytest.mark.asyncio
async def test_stop_config_watcher_skips_none() -> None:
    await _stop_config_watcher(None, logger)


@pytest.mark.asyncio
async def test_recording_watcher_stop_via_helper() -> None:
    watcher = _RecordingWatcher()
    await _stop_config_watcher(watcher, logger)
    assert watcher.stop_calls == 1


def test_background_uvicorn_server_does_not_install_signal_handlers(monkeypatch) -> None:
    async def app(scope, receive, send):
        return None

    def fail_signal_install(*args):
        raise AssertionError("background uvicorn must not own process signals")

    server = build_uvicorn_server(app, port=0)
    monkeypatch.setattr(signal, "signal", fail_signal_install)

    with server.capture_signals():
        pass


def test_scheduler_signal_handlers_are_idempotent(monkeypatch) -> None:
    installed = []

    def record_signal(sig, handler):
        installed.append(sig)

    monkeypatch.setattr(signal, "signal", record_signal)

    scheduler = TaskScheduler(AppConfig())
    scheduler.install_signal_handlers()
    scheduler.install_signal_handlers()

    assert installed.count(signal.SIGINT) == 1


@pytest.mark.asyncio
async def test_initial_pass_skips_remaining_jobs_after_shutdown_request() -> None:
    calls = []

    async def first_run():
        calls.append("first")
        return TASK_SUCCESS

    async def second_run():
        calls.append("second")
        return TASK_SUCCESS

    jobs = [
        JobDescriptor("first", first_run, "cron", lambda config: {}),
        JobDescriptor("second", second_run, "cron", lambda config: {}),
    ]

    await _run_initial_pass(jobs, should_stop=lambda: bool(calls))

    assert calls == ["first"]


@pytest.mark.asyncio
async def test_initial_pass_skips_jobs_opted_out_of_startup() -> None:
    calls = []

    async def cron_only():
        calls.append("cron-only")
        return TASK_SUCCESS

    async def regular():
        calls.append("regular")
        return TASK_SUCCESS

    jobs = [
        JobDescriptor("cron-only", cron_only, "cron", lambda config: {}, run_on_startup=False),
        JobDescriptor("regular", regular, "cron", lambda config: {}),
    ]

    await _run_initial_pass(jobs)

    assert calls == ["regular"]
