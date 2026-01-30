"""
二次开发示例：定时任务 Demo

本模块演示如何在不改动主流程的前提下，新增一个定时任务：
1. 在 config.yml 的 plugins.demo_task 下配置 enable、time 等
2. 实现 run_demo_task_once() 并在模块末尾调用 register_task()
3. 在 src/job_registry.TASK_MODULES 中追加 "tasks.demo_task"

详见 docs/SECONDARY_DEVELOPMENT.md。
"""

from __future__ import annotations

import logging

import aiohttp

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)

# 插件配置中的 key，与 config.yml 中 plugins.demo_task 对应
PLUGIN_KEY = "demo_task"


def _get_plugin_config(config: AppConfig) -> dict:
    """从 config.plugins 读取 demo_task 配置。"""
    return config.plugins.get(PLUGIN_KEY) or {}


async def run_demo_task_once() -> None:
    """
    执行一次 Demo 定时任务。
    若 plugins.demo_task.enable 为 false 或未配置，则直接返回。
    """
    config = get_config(reload=True)
    plug = _get_plugin_config(config)

    if not plug.get("enable", False):
        logger.debug("demo_task 未启用，跳过执行")
        return

    logger.info("demo_task：开始执行")

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            config.push_channel_list,
            session,
            logger,
            init_fail_prefix="demo_task：",
        )

        # 示例：仅记录一条消息，并可选择推送
        message = plug.get("message", "Demo 定时任务执行完成。")
        logger.info("demo_task：%s", message)

        if push_manager and not is_in_quiet_hours(config):
            try:
                await push_manager.send_news(
                    title="Demo 任务执行完成",
                    description=message,
                    to_url="https://github.com",
                    picurl="",
                    btntxt="查看",
                )
            except Exception as e:
                logger.error("demo_task：推送失败: %s", e, exc_info=True)

        if push_manager is not None:
            await push_manager.close()

    logger.info("demo_task：结束")


def _get_demo_task_trigger_kwargs(config: AppConfig) -> dict:
    """从 config.plugins.demo_task.time 解析 cron 的 hour、minute。"""
    plug = _get_plugin_config(config)
    time_str = (plug.get("time") or "08:00").strip()
    hour, minute = parse_checkin_time(time_str)
    return {"minute": minute, "hour": hour}


# 自注册到任务注册表（需在 src/job_registry.TASK_MODULES 中加入 "tasks.demo_task"）
register_task("demo_task", run_demo_task_once, _get_demo_task_trigger_kwargs)
