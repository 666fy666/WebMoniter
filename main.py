#!/usr/bin/env python3
"""
Web任务系统主入口（异步调度 + FastAPI 管理界面）。

扩展方式：在 monitors/、tasks/ 实现逻辑并调用 register_monitor / register_task，
再到 src/jobs/metadata.py 添加对应 TaskSpec。详见 docs/SECONDARY_DEVELOPMENT.md。
"""

import asyncio
import logging
import sys

from src.core.preflight import run_startup_preflight
from src.core.runtime import run_async_app

CONFIG_FILE = "config.yml"
CONFIG_POLL_INTERVAL_SEC = 5
SHUTDOWN_STEP_TIMEOUT_SEC = 5.0


async def _shutdown_step(name: str, awaitable, logger: logging.Logger) -> None:
    try:
        await asyncio.wait_for(awaitable, timeout=SHUTDOWN_STEP_TIMEOUT_SEC)
    except TimeoutError:
        logger.warning("%s 关闭超时，继续退出", name)
    except Exception as e:
        logger.warning("%s 关闭时出错（继续退出）: %s", name, e)


async def _stop_config_watcher(
    watcher,
    logger: logging.Logger,
) -> None:
    """停止配置热重载监控；未创建或未启动时无操作。"""
    if watcher is None:
        return
    await _shutdown_step("配置监控器", watcher.stop(), logger)


async def main() -> None:
    """启动顺序：日志 → Web → 业务配置与调度 → 配置热监视 → 阻塞至收到退出信号。"""
    from src.core.paths import CONFIG_YAML_FILE, resolve_config_sample_path
    from src.jobs.lifecycle import (
        attach_uvicorn_noise_filter,
        build_uvicorn_server,
        on_scheduler_config_changed,
        register_and_prime_jobs,
        setup_logging,
        setup_main_file_logging,
        shutdown_web_server,
        start_uvicorn_background,
    )
    from src.jobs.scheduler import TaskScheduler
    from src.settings.config import AppConfig, get_config
    from src.settings.watcher import ConfigWatcher
    from src.storage.cookie_cache import get_cookie_cache
    from src.storage.database import close_shared_connection

    is_background = not sys.stdout.isatty()
    setup_logging(log_level="INFO", console_output=not is_background)
    logger = logging.getLogger(__name__)
    cookie_cache = get_cookie_cache()

    try:
        config = get_config()
    except Exception as e:
        logger.error("配置加载失败: %s", e)
        logger.error(
            "请确保已在当前目录创建 %s 并配置必要项，可参考 %s",
            CONFIG_YAML_FILE.as_posix(),
            resolve_config_sample_path().as_posix(),
        )
        sys.exit(1)

    # Web 延后 import，避免在未使用 Web 的测试/脚本场景里提前加载 FastAPI 栈
    from src.web.app import create_web_app

    web_app = create_web_app()
    attach_uvicorn_noise_filter()
    server = build_uvicorn_server(web_app)
    web_task = start_uvicorn_background(server, logger)
    logger.info("Web: http://%s:%s", server.config.host, server.config.port)

    setup_main_file_logging()

    config_watcher: ConfigWatcher | None = None
    try:
        await cookie_cache.reset_all()

        scheduler = TaskScheduler(config)
        scheduler.install_signal_handlers()
        await register_and_prime_jobs(scheduler, config)
        if scheduler.shutdown_requested:
            logger.info("启动期间收到停止信号，正在关闭")
            scheduler.shutdown(wait=False)
            return
        logger.info(
            "Web任务系统已启动，已注册 %d 个任务",
            len(scheduler.scheduler.get_jobs()),
        )

        async def on_config_changed(
            old_cfg: AppConfig | None,
            new_cfg: AppConfig,
        ) -> None:
            await on_scheduler_config_changed(old_cfg, new_cfg, scheduler)

        config_watcher = ConfigWatcher(
            config_path=CONFIG_FILE,
            check_interval=CONFIG_POLL_INTERVAL_SEC,
            on_config_changed=on_config_changed,
        )
        await config_watcher.start()
        try:
            await scheduler.run_forever()
        finally:
            # run_forever 正常/异常退出时先停热重载，避免关闭过程中仍触发回调
            await _stop_config_watcher(config_watcher, logger)
            config_watcher = None
    except KeyboardInterrupt:
        logger.info("正在关闭...")
    except Exception as e:
        logger.error("程序运行出错: %s", e)
        raise
    finally:
        # start() 之后、进入 run_forever 之前若失败，此处仍会 stop 已启动的 watcher
        await _stop_config_watcher(config_watcher, logger)
        await _shutdown_step("Web服务器", shutdown_web_server(server, web_task), logger)
        await _shutdown_step("数据库连接", close_shared_connection(), logger)


if __name__ == "__main__":
    run_startup_preflight()
    run_async_app(main())
