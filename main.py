#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web监控系统主入口
使用APScheduler进行任务调度，支持多平台监控任务
"""
import asyncio
import logging
import sys
from typing import Callable

from src.config import get_config
from src.scheduler import TaskScheduler, setup_logging
from src.log_manager import LogManager
from monitors.huya_monitor import HuyaMonitor
from monitors.weibo_monitor import WeiboMonitor


async def run_huya_monitor():
    """运行虎牙监控任务"""
    config = get_config()
    async with HuyaMonitor(config) as monitor:
        await monitor.run()


async def run_weibo_monitor():
    """运行微博监控任务"""
    config = get_config()
    async with WeiboMonitor(config) as monitor:
        await monitor.run()


async def cleanup_logs():
    """清理旧日志文件任务"""
    log_manager = LogManager(retention_days=3)
    log_manager.cleanup_old_logs()


def register_monitors(scheduler: TaskScheduler):
    """
    注册所有监控任务到调度器
    
    在这里添加新的监控任务：
    1. 创建监控类（继承BaseMonitor）
    2. 创建运行函数（如上面的run_xxx_monitor）
    3. 使用scheduler.add_interval_job或add_cron_job注册任务
    """
    # 虎牙直播监控 - 每2分钟执行一次
    scheduler.add_interval_job(
        func=run_huya_monitor,
        minutes=2,
        job_id="huya_monitor",
    )

    # 微博监控 - 每5分钟执行一次
    scheduler.add_interval_job(
        func=run_weibo_monitor,
        minutes=5,
        job_id="weibo_monitor",
    )

    # 日志清理 - 每天凌晨2点执行
    scheduler.add_cron_job(
        func=cleanup_logs,
        minute="0",
        hour="2",
        job_id="cleanup_logs",
    )

    # 可以添加更多监控任务，例如：
    # scheduler.add_interval_job(
    #     func=run_douyin_monitor,
    #     minutes=3,
    #     job_id="douyin_monitor",
    # )


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
        logger.error("请确保已创建.env文件并配置了必要的环境变量")
        logger.error("参考.env.example文件")
        sys.exit(1)

    # 创建调度器
    scheduler = TaskScheduler(config)

    # 注册所有监控任务
    register_monitors(scheduler)

    logger.info("=" * 50)
    logger.info("Web监控系统启动")
    logger.info("=" * 50)
    logger.info("已注册的监控任务:")
    for job in scheduler.scheduler.get_jobs():
        logger.info(f"  - {job.id}: {job.trigger}")

    # 运行调度器（阻塞直到收到停止信号）
    try:
        await scheduler.run_forever()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"调度器运行出错: {e}")
        raise
    finally:
        logger.info("程序退出")


if __name__ == "__main__":
    asyncio.run(main())

