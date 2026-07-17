"""应用生命周期编排。

职责概览：
- 日志：控制台初始化后主日志文件、Uvicorn 噪声过滤
- Web：组装 Uvicorn、后台 serve 任务、退出时收尾
- 调度：注册监控/定时任务、启动首轮执行、配置热重载后同步 APScheduler
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import Callable, Generator
from typing import Any

import uvicorn

from src.jobs.log_manager import LogManager
from src.jobs.registry import (
    MONITOR_JOBS,
    TASK_JOBS,
    JobDescriptor,
    discover_and_import,
    monitor_job_enabled,
    task_job_enabled,
)
from src.jobs.scheduler import TaskScheduler, setup_logging
from src.settings.config import AppConfig
from src.settings.db_sync import sync_config_to_db

logger = logging.getLogger(__name__)

DEFAULT_BIND_HOST = "0.0.0.0"
ENV_PORT = "PORT"
DEFAULT_PORT = 8866
WEB_SHUTDOWN_WAIT_SEC = 5.0


class BackgroundUvicornServer(uvicorn.Server):
    """Uvicorn server used as a child task under WebMoniter's signal handling."""

    @contextlib.contextmanager
    def capture_signals(self) -> Generator[None, None, None]:
        # The scheduler owns SIGINT/SIGTERM. Letting Uvicorn capture and replay
        # signals from a background task causes noisy KeyboardInterrupt tracebacks.
        yield


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------


class _InvalidHttpProbeLogFilter(logging.Filter):
    """屏蔽端口扫描产生的「Invalid HTTP request」刷屏。"""

    def filter(self, record: logging.LogRecord) -> bool:
        return "Invalid HTTP request" not in str(record.getMessage())


def setup_main_file_logging() -> None:
    """在 root logger 上挂载 main 日志文件（须先调用 setup_logging）。"""
    file_handler = LogManager().setup_file_logging("main", log_level="INFO")
    logging.root.addHandler(file_handler)


def attach_uvicorn_noise_filter() -> None:
    logging.getLogger("uvicorn.error").addFilter(_InvalidHttpProbeLogFilter())


# ---------------------------------------------------------------------------
# Web（Uvicorn）
# ---------------------------------------------------------------------------


def build_uvicorn_server(
    app: Any,
    *,
    host: str = DEFAULT_BIND_HOST,
    port: int | None = None,
) -> uvicorn.Server:
    if port is not None:
        resolved_port = port
    else:
        resolved_port = int(os.environ.get(ENV_PORT, str(DEFAULT_PORT)))
    cfg = uvicorn.Config(
        app=app,
        host=host,
        port=resolved_port,
        log_level="info",
        access_log=False,
    )
    return BackgroundUvicornServer(cfg)


def start_uvicorn_background(server: uvicorn.Server, log: logging.Logger) -> asyncio.Task[None]:
    """在后台运行 Uvicorn，返回可 await / cancel 的 Task。"""

    async def _serve() -> None:
        try:
            await server.serve()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error("Web服务器运行出错: %s", e, exc_info=True)

    return asyncio.create_task(_serve())


async def shutdown_web_server(server: uvicorn.Server, web_task: asyncio.Task[Any]) -> None:
    """请求 Uvicorn 退出并等待后台任务结束（带超时）。"""
    try:
        server.should_exit = True
        if web_task.done():
            return
        try:
            await asyncio.wait_for(web_task, timeout=WEB_SHUTDOWN_WAIT_SEC)
        except TimeoutError:
            logger.debug("Web服务器关闭超时，强制取消")
            web_task.cancel()
            try:
                await web_task
            except (asyncio.CancelledError, Exception):
                pass
        except (asyncio.CancelledError, Exception):
            pass
    except Exception as e:
        logger.debug("停止Web服务器时出错（可忽略）: %s", e)


async def cancel_web_task(web_task: asyncio.Task[Any]) -> None:
    """无 Server 实例时仅取消后台任务（防御性）。"""
    if web_task.done():
        return
    web_task.cancel()
    try:
        await web_task
    except (asyncio.CancelledError, Exception):
        pass


# ---------------------------------------------------------------------------
# 调度器注册与配置热重载
# ---------------------------------------------------------------------------


def _add_interval_jobs(scheduler: TaskScheduler, config: AppConfig) -> None:
    for desc in MONITOR_JOBS:
        kw = desc.get_trigger_kwargs(config)
        scheduler.add_interval_job(func=desc.run_func, job_id=desc.job_id, **kw)


def _add_cron_jobs(scheduler: TaskScheduler, config: AppConfig) -> None:
    for desc in TASK_JOBS:
        kw = desc.get_trigger_kwargs(config)
        scheduler.add_cron_job(func=desc.run_func, job_id=desc.job_id, **kw)


def _pause_monitors_disabled_in_config(scheduler: TaskScheduler, config: AppConfig) -> None:
    for desc in MONITOR_JOBS:
        if not monitor_job_enabled(desc.job_id, config):
            scheduler.pause_job(desc.job_id)


def _pause_tasks_disabled_in_config(scheduler: TaskScheduler, config: AppConfig) -> None:
    for desc in TASK_JOBS:
        if not task_job_enabled(desc.job_id, config):
            scheduler.pause_job(desc.job_id)


async def _run_initial_pass(
    jobs: list[JobDescriptor],
    should_stop: Callable[[], bool] | None = None,
) -> None:
    logger.debug("正在启动时立即执行一次监控任务和定时任务...")
    for desc in jobs:
        if not desc.run_on_startup:
            logger.debug("%s: 配置为仅按触发器执行，跳过启动首轮", desc.job_id)
            continue
        if should_stop is not None and should_stop():
            logger.info("收到停止信号，跳过剩余启动首轮任务")
            break
        try:
            await desc.run_func()
        except Exception as e:  # noqa: BLE001
            logger.error("%s 启动时首次执行失败: %s", desc.job_id, e, exc_info=True)


async def register_and_prime_jobs(scheduler: TaskScheduler, config: AppConfig) -> None:
    """发现模块、注册任务、暂停未启用监控，并对所有任务执行启动首轮。"""
    discover_and_import()
    _add_interval_jobs(scheduler, config)
    _add_cron_jobs(scheduler, config)
    _pause_monitors_disabled_in_config(scheduler, config)
    _pause_tasks_disabled_in_config(scheduler, config)
    await _run_initial_pass(MONITOR_JOBS + TASK_JOBS, lambda: scheduler.shutdown_requested)


def _format_reload_summary(updates: list[str]) -> str:
    monitor_count = sum(1 for u in updates if "间隔:" in u)
    cron_count = sum(1 for u in updates if "执行时间:" in u)
    other = [u for u in updates if "间隔:" not in u and "执行时间:" not in u]
    parts: list[str] = []
    if monitor_count:
        parts.append(f"{monitor_count} 个监控任务")
    if cron_count:
        parts.append(f"{cron_count} 个定时任务")
    if other:
        parts.extend(other)
    return ", ".join(parts)


def _reload_note_for_quiet_hours(old: AppConfig | None, new: AppConfig) -> list[str]:
    if old is None:
        return []
    qh_unchanged = (
        old.quiet_hours_enable == new.quiet_hours_enable
        and old.quiet_hours_start == new.quiet_hours_start
        and old.quiet_hours_end == new.quiet_hours_end
    )
    if qh_unchanged:
        return []
    status = "启用" if new.quiet_hours_enable else "禁用"
    return [f"免打扰时段({status}, {new.quiet_hours_start}-{new.quiet_hours_end})"]


def _apply_monitor_jobs_after_config_reload(
    scheduler: TaskScheduler, new_config: AppConfig
) -> list[str]:
    out: list[str] = []
    for desc in MONITOR_JOBS:
        if monitor_job_enabled(desc.job_id, new_config):
            scheduler.resume_job(desc.job_id)
            kw = desc.get_trigger_kwargs(new_config)
            if info := scheduler.update_interval_job(job_id=desc.job_id, **kw):
                out.append(info)
        else:
            scheduler.pause_job(desc.job_id)
            out.append(f"{desc.job_id}(已暂停)")
    return out


def _apply_cron_jobs_after_config_reload(
    scheduler: TaskScheduler, new_config: AppConfig
) -> list[str]:
    out: list[str] = []
    for desc in TASK_JOBS:
        if task_job_enabled(desc.job_id, new_config):
            scheduler.resume_job(desc.job_id)
            kw = desc.get_trigger_kwargs(new_config)
            if info := scheduler.update_cron_job(job_id=desc.job_id, **kw):
                out.append(info)
        else:
            scheduler.pause_job(desc.job_id)
            out.append(f"{desc.job_id}(已暂停)")
    return out


async def on_scheduler_config_changed(
    old_config: AppConfig | None,
    new_config: AppConfig,
    scheduler: TaskScheduler,
) -> None:
    """热重载：DB 与配置对齐，并按注册表更新 APScheduler。"""
    try:
        await sync_config_to_db(old_config, new_config)
        updates: list[str] = []
        updates.extend(_apply_monitor_jobs_after_config_reload(scheduler, new_config))
        updates.extend(_apply_cron_jobs_after_config_reload(scheduler, new_config))
        updates.extend(_reload_note_for_quiet_hours(old_config, new_config))
        if updates:
            logger.info("配置已更新: %s", _format_reload_summary(updates))
    except Exception as e:
        logger.error("更新调度器任务间隔失败: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------


__all__ = [
    "attach_uvicorn_noise_filter",
    "build_uvicorn_server",
    "cancel_web_task",
    "DEFAULT_BIND_HOST",
    "DEFAULT_PORT",
    "ENV_PORT",
    "on_scheduler_config_changed",
    "register_and_prime_jobs",
    "setup_main_file_logging",
    "shutdown_web_server",
    "setup_logging",
    "start_uvicorn_background",
    "WEB_SHUTDOWN_WAIT_SEC",
]
