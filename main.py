#!/usr/bin/env python3
"""
Web监控系统主入口
使用APScheduler进行任务调度，支持多平台监控任务
"""
import asyncio
import logging

from monitors.huya_monitor import HuyaMonitor
from monitors.weibo_monitor import WeiboMonitor
from src.config import AppConfig, get_config
from src.config_watcher import ConfigWatcher
from src.cookie_cache_manager import cookie_cache
from src.database import close_shared_connection
from src.log_manager import LogManager
from src.scheduler import TaskScheduler, setup_logging


async def run_huya_monitor():
    """运行虎牙监控任务（支持配置热重载）"""
    # 重新加载配置文件，获取最新的cookie
    config = get_config(reload=True)
    logger = logging.getLogger(__name__)
    logger.debug(f"虎牙监控：已重新加载配置文件 (Cookie长度: {len(config.huya_cookie)} 字符)")

    async with HuyaMonitor(config) as monitor:
        await monitor.run()


async def run_weibo_monitor():
    """运行微博监控任务（支持配置热重载）"""
    # 重新加载配置文件，获取最新的cookie
    config = get_config(reload=True)
    logger = logging.getLogger(__name__)
    logger.debug(f"微博监控：已重新加载配置文件 (Cookie长度: {len(config.weibo_cookie)} 字符)")

    async with WeiboMonitor(config) as monitor:
        await monitor.run()


async def cleanup_logs():
    """清理旧日志文件任务"""
    log_manager = LogManager(retention_days=3)
    log_manager.cleanup_old_logs()


async def register_monitors(scheduler: TaskScheduler):
    """
    注册所有监控任务到调度器

    在这里添加新的监控任务：
    1. 创建监控类（继承BaseMonitor）
    2. 创建运行函数（如上面的run_xxx_monitor）
    3. 使用scheduler.add_interval_job或add_cron_job注册任务
    """
    # 加载配置以获取调度间隔时间
    config = get_config()

    # 虎牙直播监控 - 间隔时间从配置文件配置，默认65秒
    scheduler.add_interval_job(
        func=run_huya_monitor,
        seconds=config.huya_monitor_interval_seconds,
        job_id="huya_monitor",
    )

    # 微博监控 - 间隔时间从配置文件配置，默认300秒（5分钟）
    scheduler.add_interval_job(
        func=run_weibo_monitor,
        seconds=config.weibo_monitor_interval_seconds,
        job_id="weibo_monitor",
    )

    # 日志清理 - 执行时间从配置文件配置，默认每天凌晨2点
    scheduler.add_cron_job(
        func=cleanup_logs,
        minute=str(config.cleanup_logs_minute),
        hour=str(config.cleanup_logs_hour),
        job_id="cleanup_logs",
    )

    # 项目启动时立即执行一次监控任务
    logger = logging.getLogger(__name__)
    logger.debug("正在启动时立即执行一次监控任务...")

    # 立即执行虎牙监控
    try:
        await run_huya_monitor()
    except Exception as e:
        logger.error(f"虎牙监控启动时首次执行失败: {e}", exc_info=True)

    # 立即执行微博监控
    try:
        await run_weibo_monitor()
    except Exception as e:
        logger.error(f"微博监控启动时首次执行失败: {e}", exc_info=True)

    # 可以添加更多监控任务，例如：
    # scheduler.add_interval_job(
    #     func=run_douyin_monitor,
    #     minutes=3,
    #     job_id="douyin_monitor",
    # )


async def on_config_changed(new_config: AppConfig, scheduler: TaskScheduler):
    """
    配置变化时的回调函数 - 更新调度器中的任务间隔时间

    Args:
        new_config: 新的配置对象
        scheduler: 任务调度器
    """
    logger = logging.getLogger(__name__)
    logger.info("配置已更新，开始更新调度器任务间隔...")

    try:
        # 更新虎牙监控间隔
        scheduler.update_interval_job(
            job_id="huya_monitor",
            seconds=new_config.huya_monitor_interval_seconds,
        )

        # 更新微博监控间隔
        scheduler.update_interval_job(
            job_id="weibo_monitor",
            seconds=new_config.weibo_monitor_interval_seconds,
        )

        # 更新日志清理任务的执行时间
        scheduler.update_cron_job(
            job_id="cleanup_logs",
            minute=str(new_config.cleanup_logs_minute),
            hour=str(new_config.cleanup_logs_hour),
        )

        logger.info("调度器任务间隔已更新完成")
    except Exception as e:
        logger.error(f"更新调度器任务间隔失败: {e}", exc_info=True)


async def main():
    """主函数"""
    # 检测是否为后台运行（非交互式终端）
    import sys

    is_background = not sys.stdout.isatty()

    # 设置日志：后台运行时只输出到文件，前台运行时同时输出到控制台和文件
    setup_logging(log_level="INFO", console_output=not is_background)
    logger = logging.getLogger(__name__)

    # 设置文件日志
    log_manager = LogManager()
    file_handler = log_manager.setup_file_logging("main", log_level="INFO")
    logging.root.addHandler(file_handler)

    try:
        # 加载配置
        config = get_config()
        logger.info("配置加载成功")
    except Exception as e:
        logger.error(f"配置加载失败: {e}")
        logger.error("请确保已创建config.yml文件并配置了必要的配置项")
        logger.error("参考config.yml.sample文件")
        sys.exit(1)

    # 初始化Cookie缓存：项目启动时重置所有Cookie状态为有效
    await cookie_cache.reset_all()
    logger.info("Cookie缓存已初始化，所有Cookie状态已重置为有效")

    # 创建调度器
    scheduler = TaskScheduler(config)

    logger.info("=" * 50)
    logger.info("Web监控系统启动")
    logger.info("=" * 50)
    logger.info("开始注册所有监控任务（启动时将立即执行一次）...")

    await register_monitors(scheduler)

    logger.info("已注册的监控任务:")
    for job in scheduler.scheduler.get_jobs():
        logger.info(f"  - {job.id}: {job.trigger}")

    # 创建配置监控器，支持热重载
    # 使用闭包创建回调函数，捕获 scheduler 引用
    async def config_changed_callback(cfg: AppConfig):
        """配置变化回调函数"""
        await on_config_changed(cfg, scheduler)

    config_watcher = ConfigWatcher(
        config_path="config.yml",
        check_interval=5,  # 每5秒检查一次配置文件
        on_config_changed=config_changed_callback,
    )

    # 启动配置监控器
    await config_watcher.start()
    logger.info("配置文件热重载监控已启动（每5秒检查一次）")

    # 运行调度器（阻塞直到收到停止信号）
    try:
        await scheduler.run_forever()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"调度器运行出错: {e}")
        raise
    finally:
        # 停止配置监控器
        await config_watcher.stop()
        # 关闭共享数据库连接
        await close_shared_connection()
        logger.info("程序退出")


if __name__ == "__main__":
    asyncio.run(main())
