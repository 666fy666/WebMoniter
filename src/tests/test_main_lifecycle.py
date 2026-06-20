"""main.py 中 config_watcher 生命周期：启动后无论成败都应 stop。"""

from __future__ import annotations

import logging

import pytest

from main import _stop_config_watcher

logger = logging.getLogger("test")


class _RecordingWatcher:
    def __init__(self) -> None:
        self.stop_calls = 0

    async def stop(self) -> None:
        self.stop_calls += 1


async def _run_watcher_lifecycle(
    *,
    assign_watcher: bool,
    start_raises: bool,
    run_raises: bool,
) -> tuple[int, bool]:
    """复刻 main.py 中 config_watcher 的嵌套 try/finally 语义。"""
    config_watcher: _RecordingWatcher | None = None
    stop_calls = 0

    async def stop_and_count(watcher: _RecordingWatcher | None) -> None:
        nonlocal stop_calls
        if watcher is None:
            return
        await watcher.stop()
        stop_calls += 1

    try:
        if assign_watcher:
            config_watcher = _RecordingWatcher()
            if start_raises:
                raise RuntimeError("start failed")
            try:
                if run_raises:
                    raise RuntimeError("run failed")
            finally:
                await stop_and_count(config_watcher)
                config_watcher = None
    except RuntimeError:
        pass
    finally:
        await stop_and_count(config_watcher)

    return stop_calls, config_watcher is None


@pytest.mark.asyncio
async def test_stop_config_watcher_skips_none() -> None:
    await _stop_config_watcher(None, logger)


@pytest.mark.asyncio
async def test_watcher_not_stopped_when_never_created() -> None:
    stop_calls, cleared = await _run_watcher_lifecycle(
        assign_watcher=False,
        start_raises=False,
        run_raises=False,
    )
    assert stop_calls == 0
    assert cleared is True


@pytest.mark.asyncio
async def test_watcher_stopped_once_when_run_forever_raises() -> None:
    stop_calls, cleared = await _run_watcher_lifecycle(
        assign_watcher=True,
        start_raises=False,
        run_raises=True,
    )
    assert stop_calls == 1
    assert cleared is True


@pytest.mark.asyncio
async def test_watcher_stopped_when_start_raises_after_assignment() -> None:
    """ConfigWatcher 已构造但 start() 失败：仅外层 finally stop 一次。"""
    stop_calls, _ = await _run_watcher_lifecycle(
        assign_watcher=True,
        start_raises=True,
        run_raises=False,
    )
    assert stop_calls == 1


@pytest.mark.asyncio
async def test_recording_watcher_stop_via_helper() -> None:
    watcher = _RecordingWatcher()
    await _stop_config_watcher(watcher, logger)
    assert watcher.stop_calls == 1
