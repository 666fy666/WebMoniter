#!/usr/bin/env python3
"""
Web监控系统主入口
使用APScheduler进行任务调度，支持多平台监控和定时任务。
新增监控/定时任务只需在 src/job_registry 中追加模块并在对应模块内注册，详见 docs/SECONDARY_DEVELOPMENT.md。
"""

import asyncio
import logging

from src.config import AppConfig, get_config
from src.config_watcher import ConfigWatcher
from src.cookie_cache import get_cookie_cache
from src.database import close_shared_connection
from src.job_registry import (
    MONITOR_JOBS,
    TASK_JOBS,
    discover_and_import,
)
from src.log_manager import LogManager
from src.scheduler import TaskScheduler, setup_logging

cookie_cache = get_cookie_cache()


async def register_monitors(scheduler: TaskScheduler) -> None:
    """
    通过注册表注册所有监控任务与定时任务到调度器，并启动时各执行一次。
    新增任务：在 src/job_registry 的 MONITOR_MODULES/TASK_MODULES 中追加模块路径，并在该模块内调用 register_monitor/register_task。
    """
    discover_and_import()
    config = get_config()
    logger = logging.getLogger(__name__)

    # 注册监控任务和定时任务
    job_registrations = [
        (MONITOR_JOBS, scheduler.add_interval_job),
        (TASK_JOBS, scheduler.add_cron_job),
    ]

    for job_list, register_func in job_registrations:
        for desc in job_list:
            kwargs = desc.get_trigger_kwargs(config)
            register_func(
                func=desc.run_func,
                job_id=desc.job_id,
                **kwargs,
            )

    # 启动时立即执行一次所有任务
    # 监控任务每次都执行，定时任务会自动检查当天是否已运行过
    logger.debug("正在启动时立即执行一次监控任务和定时任务...")
    all_jobs = MONITOR_JOBS + TASK_JOBS

    for desc in all_jobs:
        try:
            await desc.run_func()
        except Exception as e:  # noqa: BLE001
            logger.error("%s 启动时首次执行失败: %s", desc.job_id, e, exc_info=True)


async def on_config_changed(
    old_config: AppConfig | None, new_config: AppConfig, scheduler: TaskScheduler
) -> None:
    """
    配置变化时的回调 - 按注册表更新调度器中的任务间隔/执行时间。
    """
    logger = logging.getLogger(__name__)

    try:
        updates = []

        for desc in MONITOR_JOBS:
            kwargs = desc.get_trigger_kwargs(new_config)
            update_info = scheduler.update_interval_job(
                job_id=desc.job_id,
                **kwargs,
            )
            if update_info:
                updates.append(update_info)

        for desc in TASK_JOBS:
            kwargs = desc.get_trigger_kwargs(new_config)
            update_info = scheduler.update_cron_job(
                job_id=desc.job_id,
                **kwargs,
            )
            if update_info:
                updates.append(update_info)

        if old_config is not None:
            if (
                old_config.quiet_hours_enable != new_config.quiet_hours_enable
                or old_config.quiet_hours_start != new_config.quiet_hours_start
                or old_config.quiet_hours_end != new_config.quiet_hours_end
            ):
                status = "启用" if new_config.quiet_hours_enable else "禁用"
                updates.append(
                    f"免打扰时段({status}, {new_config.quiet_hours_start}-{new_config.quiet_hours_end})"
                )

        if updates:
            logger.info("配置已更新: %s", ", ".join(updates))
    except Exception as e:
        logger.error("更新调度器任务间隔失败: %s", e, exc_info=True)


async def main() -> None:
    """主函数"""
    import sys

    is_background = not sys.stdout.isatty()
    setup_logging(log_level="INFO", console_output=not is_background)
    logger = logging.getLogger(__name__)

    import uvicorn

    from src.web_server import create_web_app

    web_app = create_web_app()

    uvicorn_logger = logging.getLogger("uvicorn.error")

    class InvalidRequestFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if "Invalid HTTP request" in str(record.getMessage()):
                return False
            return True

    invalid_request_filter = InvalidRequestFilter()
    uvicorn_logger.addFilter(invalid_request_filter)

    server_config = uvicorn.Config(
        app=web_app,
        host="0.0.0.0",
        port=8866,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(server_config)

    async def run_web_server() -> None:
        try:
            await server.serve()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Web服务器运行出错: %s", e, exc_info=True)

    web_task = asyncio.create_task(run_web_server())
    logger.info("Web: http://0.0.0.0:8866")

    log_manager = LogManager()
    file_handler = log_manager.setup_file_logging("main", log_level="INFO")
    logging.root.addHandler(file_handler)

    try:
        config = get_config()
    except Exception as e:
        logger.error("配置加载失败: %s", e)
        logger.error("请确保已创建 config.yml 并配置必要项，可参考 config.yml.sample")
        sys.exit(1)

    await cookie_cache.reset_all()

    scheduler = TaskScheduler(config)
    await register_monitors(scheduler)
    jobs = scheduler.scheduler.get_jobs()
    logger.info("Web监控系统已启动，已注册 %d 个任务", len(jobs))

    async def config_changed_callback(old_cfg: AppConfig | None, new_cfg: AppConfig) -> None:
        await on_config_changed(old_cfg, new_cfg, scheduler)

    config_watcher = ConfigWatcher(
        config_path="config.yml",
        check_interval=5,
        on_config_changed=config_changed_callback,
    )

    await config_watcher.start()

    try:
        await scheduler.run_forever()
    except KeyboardInterrupt:
        logger.info("正在关闭...")
    except Exception as e:
        logger.error("程序运行出错: %s", e)
        raise
    finally:
        if "server" in locals():
            try:
                server.should_exit = True
                if "web_task" in locals() and not web_task.done():
                    try:
                        await asyncio.wait_for(web_task, timeout=5.0)
                    except asyncio.TimeoutError:
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
        elif "web_task" in locals() and not web_task.done():
            web_task.cancel()
            try:
                await web_task
            except (asyncio.CancelledError, Exception):
                pass
        await config_watcher.stop()
        await close_shared_connection()


if __name__ == "__main__":
    asyncio.run(main())
