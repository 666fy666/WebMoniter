"""监控任务在目标列表为空时应于创建 semaphore 前提前返回。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.monitors.bilibili_monitor import BilibiliMonitor
from src.monitors.douyin_monitor import DouyinMonitor
from src.monitors.douyu_monitor import DouyuMonitor
from src.monitors.xhs_monitor import XhsMonitor
from src.settings.config import AppConfig

EMPTY_CONFIG = AppConfig()


@pytest.mark.parametrize(
    ("monitor_cls", "config_patch", "semaphore_patch"),
    [
        (
            DouyinMonitor,
            "src.monitors.douyin_monitor.get_config",
            "src.monitors.douyin_monitor.asyncio.Semaphore",
        ),
        (
            DouyuMonitor,
            "src.monitors.douyu_monitor.get_config",
            "src.monitors.douyu_monitor.asyncio.Semaphore",
        ),
        (
            XhsMonitor,
            "src.monitors.xhs_monitor.get_config",
            "src.monitors.xhs_monitor.asyncio.Semaphore",
        ),
        (
            BilibiliMonitor,
            "src.monitors.bilibili_monitor.get_config",
            "src.monitors.bilibili_monitor.asyncio.Semaphore",
        ),
    ],
)
@pytest.mark.asyncio
async def test_run_skips_before_semaphore_when_targets_empty(
    monitor_cls,
    config_patch: str,
    semaphore_patch: str,
) -> None:
    monitor = monitor_cls(EMPTY_CONFIG)
    monitor.initialize = AsyncMock()
    monitor.close = AsyncMock()

    with (
        patch(config_patch, return_value=EMPTY_CONFIG),
        patch(semaphore_patch) as semaphore_mock,
    ):
        async with monitor:
            await monitor.run()

    semaphore_mock.assert_not_called()
