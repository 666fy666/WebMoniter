"""main.py 中 config_watcher 生命周期：启动后无论成败都应 stop。"""

from __future__ import annotations

import asyncio
import logging
import signal
from types import SimpleNamespace

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

    await _run_initial_pass(jobs, should_stop=lambda: True)

    assert calls == []


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

    from src.jobs.execution import get_execution_service

    service = get_execution_service()
    try:
        await _run_initial_pass(jobs)
        await service.queue.join()
        assert calls == ["regular"]
    finally:
        await service.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["normal", "startup_stop", "watcher_failure"])
async def test_main_warmup_runs_after_initialization_and_stops_before_database_close(
    monkeypatch, mode
):
    import main as entry
    from src.jobs import lifecycle, scheduler
    from src.settings import config, watcher
    from src.storage import cookie_cache, database
    from src.web import app, warmup

    events = []

    async def reset_cookie_cache():
        events.append("cookies")

    async def configure_database(cfg):
        events.append("database_ready")

    async def prime_jobs(*args):
        events.append("jobs_ready")

    async def close_database():
        events.append("database_closed")

    async def stop_web(*args):
        events.append("web_stopped")

    async def warm():
        events.append("warmup_started")
        try:
            await asyncio.Event().wait()
        finally:
            events.append("warmup_stopped")

    class Scheduler:
        def __init__(self, cfg):
            self.shutdown_requested = mode == "startup_stop"
            self.scheduler = SimpleNamespace(get_jobs=lambda: [])

        def install_signal_handlers(self):
            pass

        def shutdown(self, **kwargs):
            pass

        async def run_forever(self):
            await asyncio.sleep(0)
            assert events[:5] == [
                "cookies",
                "database_ready",
                "jobs_ready",
                "watcher_started",
                "warmup_started",
            ]

    class Watcher:
        def __init__(self, **kwargs):
            pass

        async def start(self):
            events.append("watcher_started")
            if mode == "watcher_failure":
                raise RuntimeError("watcher failed")

        async def stop(self):
            events.append("watcher_stopped")

    monkeypatch.setattr(config, "get_config", lambda: AppConfig())
    monkeypatch.setattr(
        cookie_cache, "get_cookie_cache", lambda: SimpleNamespace(reset_all=reset_cookie_cache)
    )
    monkeypatch.setattr(database, "reconfigure_database", configure_database)
    monkeypatch.setattr(database, "close_shared_connection", close_database)
    monkeypatch.setattr(scheduler, "TaskScheduler", Scheduler)
    monkeypatch.setattr(watcher, "ConfigWatcher", Watcher)
    from src.web import auth

    monkeypatch.setattr(auth, "load_auth", lambda: {})
    monkeypatch.setattr(app, "create_web_app", lambda: SimpleNamespace(state=SimpleNamespace()))
    monkeypatch.setattr(warmup, "warmup_web_resources", warm)
    monkeypatch.setattr(lifecycle, "register_and_prime_jobs", prime_jobs)
    monkeypatch.setattr(lifecycle, "shutdown_web_server", stop_web)
    monkeypatch.setattr(
        lifecycle,
        "build_uvicorn_server",
        lambda _: SimpleNamespace(config=SimpleNamespace(host="127.0.0.1", port=0)),
    )
    monkeypatch.setattr(lifecycle, "start_uvicorn_background", lambda *args: None)
    for name in ("setup_logging", "setup_main_file_logging", "attach_uvicorn_noise_filter"):
        monkeypatch.setattr(lifecycle, name, lambda **kwargs: None)

    if mode == "watcher_failure":
        with pytest.raises(RuntimeError, match="watcher failed"):
            await entry.main()
    else:
        await entry.main()
    assert events[-2:] == ["web_stopped", "database_closed"]
    if mode == "normal":
        assert events.index("warmup_stopped") < events.index("database_closed")
    else:
        assert "warmup_started" not in events
