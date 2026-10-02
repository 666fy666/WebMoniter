"""main.py 中 config_watcher 生命周期：启动后无论成败都应 stop。"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from main import _stop_config_watcher
from src.jobs.lifecycle import _run_initial_pass, build_uvicorn_server
from src.jobs.registry import JobDescriptor
from src.jobs.scheduler import TaskScheduler
from src.jobs.task_outcome import TASK_SUCCESS
from src.settings.config import AppConfig
from src.settings.watcher import ConfigWatcher

logger = logging.getLogger("test")


@pytest.mark.asyncio
@pytest.mark.parametrize("replace_pending", [False, True])
async def test_watcher_retries_failed_callback_with_latest_configuration(
    tmp_path, monkeypatch, replace_pending
):
    from src.settings import watcher as module

    path = tmp_path / "config.yml"
    path.write_text("initial")
    initial = AppConfig(weibo_monitor_interval_seconds=100)
    pending = AppConfig(weibo_monitor_interval_seconds=200)
    latest = AppConfig(weibo_monitor_interval_seconds=300)
    current = initial
    monkeypatch.setattr(module, "get_config", lambda *args: current)
    applied = asyncio.Event()
    calls = []

    async def on_change(old, new):
        nonlocal current
        calls.append((old, new))
        if len(calls) == 1:
            if replace_pending:
                current = latest
                stat = path.stat()
                replacement = tmp_path / "replacement"
                replacement.write_text("updated")
                os.utime(replacement, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                replacement.replace(path)
            raise RuntimeError("temporary apply failure")
        applied.set()

    watcher = ConfigWatcher(str(path), check_interval=0.001, on_config_changed=on_change)
    await watcher.start()
    try:
        current = pending
        path.write_text("updated")
        await asyncio.wait_for(applied.wait(), 1)
        assert calls == [(initial, pending), (initial, latest if replace_pending else pending)]
        assert watcher._last_config is (latest if replace_pending else pending)
        assert not watcher._retry_pending
    finally:
        await watcher.stop()


@pytest.mark.asyncio
async def test_config_cleanup_propagates_partial_failure_and_can_be_retried(monkeypatch):
    from src.settings import db_sync

    db = AsyncMock()
    db.__aenter__.return_value = db
    db.execute_update.side_effect = [True, False, True, True]
    monkeypatch.setattr(db_sync, "AsyncDatabase", lambda: db)
    old = AppConfig(bilibili_uids="removed")
    new = AppConfig(bilibili_uids="")
    with pytest.raises(RuntimeError, match="清理未完成"):
        await db_sync.sync_config_to_db(old, new)
    await db_sync.sync_config_to_db(old, new)
    calls = db.execute_update.await_args_list
    assert calls[:2] == calls[2:]
    assert all(call.args[1] == {"pk": "removed"} for call in calls)


@pytest.mark.asyncio
async def test_config_reload_propagates_scheduler_failure(monkeypatch):
    from src.jobs import lifecycle
    from src.storage import database

    monkeypatch.setattr(database, "reconfigure_database", AsyncMock())
    monkeypatch.setattr(lifecycle, "sync_config_to_db", AsyncMock())
    descriptor = JobDescriptor("test", AsyncMock(), "interval", lambda config: {"seconds": 1})
    monkeypatch.setattr(lifecycle, "MONITOR_JOBS", [descriptor])
    monkeypatch.setattr(lifecycle, "monitor_job_enabled", lambda *args: True)
    scheduler = SimpleNamespace(resume_job=lambda job_id: False)
    with pytest.raises(RuntimeError, match="恢复任务失败"):
        await lifecycle.on_scheduler_config_changed(AppConfig(), AppConfig(), scheduler)


@pytest.mark.asyncio
async def test_reapplying_schedule_preserves_next_run_and_can_change_interval():
    scheduler = TaskScheduler(AppConfig())
    scheduler.scheduler.add_job(AsyncMock(), "interval", seconds=60, id="interval")
    scheduler.scheduler.add_job(AsyncMock(), "cron", hour="3", minute="15", id="cron")
    scheduler.scheduler.start(paused=True)
    try:
        expected = {job.id: job.next_run_time for job in scheduler.scheduler.get_jobs()}
        for _ in range(2):
            assert scheduler.resume_job("interval")
            assert scheduler.update_interval_job("interval", seconds=60)
            assert scheduler.resume_job("cron")
            assert scheduler.update_cron_job("cron", hour="3", minute="15")
        assert {job.id: job.next_run_time for job in scheduler.scheduler.get_jobs()} == expected
        assert scheduler.update_interval_job("interval", seconds=120)
        job = scheduler.scheduler.get_job("interval")
        assert job.trigger.interval.total_seconds() == 120
        assert job.next_run_time > expected["interval"]
        assert scheduler.pause_job("interval")
        assert scheduler.scheduler.get_job("interval").next_run_time is None
        assert scheduler.resume_job("interval")
        assert scheduler.scheduler.get_job("interval").next_run_time is not None
    finally:
        scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_watcher_reloads_restored_file_with_older_timestamp(tmp_path, monkeypatch):
    from src.settings import watcher as module

    path = tmp_path / "config.yml"
    path.write_text("initial")
    configs = iter([AppConfig(weibo_enable=False), AppConfig(weibo_enable=True)])
    monkeypatch.setattr(module, "get_config", lambda *args: next(configs))
    changed = asyncio.Event()

    async def on_change(old, new):
        assert not old.weibo_enable
        assert new.weibo_enable
        changed.set()

    watcher = ConfigWatcher(str(path), check_interval=0.001, on_config_changed=on_change)
    await watcher.start()
    try:
        earlier = path.stat().st_mtime - 60
        path.write_text("restored")
        os.utime(path, (earlier, earlier))
        await asyncio.wait_for(changed.wait(), 1)
    finally:
        await watcher.stop()


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
