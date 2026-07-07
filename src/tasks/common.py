"""定时任务公共辅助函数。

这里放置任务外壳的重复逻辑：配置列表规范化、Cron 参数、推送生命周期和结果汇总。
各站点的登录、签到、解析等脆弱业务逻辑仍保留在对应任务模块内。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import aiohttp

from src.push_channel.manager import UnifiedPushManager, build_push_manager
from src.settings.config import AppConfig, is_in_quiet_hours, parse_checkin_time


def cron_kwargs_from_config(config: AppConfig, time_field: str, default: str) -> dict[str, str]:
    """从 AppConfig 的时间字段生成 APScheduler CronTrigger 参数。"""
    raw = getattr(config, time_field, default) or default
    hour, minute = parse_checkin_time(raw)
    return {"minute": minute, "hour": hour}


def normalized_string_items(
    items: list[str] | None,
    single: str | None = None,
) -> list[str]:
    """多值优先；若多值为空则使用单值；最终去掉空白项。"""
    out = [str(item).strip() for item in (items or []) if str(item or "").strip()]
    if out:
        return out
    single_value = str(single or "").strip()
    return [single_value] if single_value else []


def normalized_accounts(
    accounts: list[dict] | None,
    required_fields: tuple[str, ...],
    *,
    single_account: dict[str, str] | None = None,
    optional_fields: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    """规范化多账号配置；多账号为空时可回退到单账号字段。"""
    fields = (*required_fields, *optional_fields)
    out: list[dict[str, str]] = []
    for item in accounts or []:
        if not isinstance(item, dict):
            continue
        account = {field: str(item.get(field, "")).strip() for field in fields}
        if all(account.get(field) for field in required_fields):
            out.append(account)
    if out or not single_account:
        return out

    fallback = {field: str(single_account.get(field, "")).strip() for field in fields}
    if all(fallback.get(field) for field in required_fields):
        return [fallback]
    return []


def task_push_channels(config: AppConfig, field_name: str) -> list[str]:
    """读取任务 push_channels 字段，非法或空值按空列表处理。"""
    raw = getattr(config, field_name, None)
    if not isinstance(raw, list):
        return []
    return [str(name).strip() for name in raw if str(name or "").strip()]


@asynccontextmanager
async def push_manager_context(
    config: AppConfig,
    logger: logging.Logger,
    *,
    push_channels: list[str] | None = None,
    init_fail_prefix: str = "",
    timeout_seconds: int = 20,
) -> AsyncIterator[UnifiedPushManager | None]:
    """创建并自动关闭任务推送 manager。"""
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout_seconds)
    ) as session:
        push = await build_push_manager(
            config.push_channel_list,
            session,
            logger,
            init_fail_prefix=init_fail_prefix,
            channel_names=push_channels or None,
        )
        try:
            yield push
        finally:
            if push is not None:
                await push.close()


async def send_news_if_allowed(
    push: UnifiedPushManager | None,
    config: AppConfig,
    logger: logging.Logger,
    *,
    quiet_log: str,
    error_log: str,
    **kwargs: Any,
) -> bool:
    """若有推送通道且不在免打扰时段，则发送图文推送。"""
    if push is None:
        return False
    if is_in_quiet_hours(config):
        logger.debug(quiet_log)
        return False
    try:
        await push.send_news(**kwargs)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(error_log, exc)
        return False


async def send_text_if_allowed(
    push: UnifiedPushManager | None,
    config: AppConfig,
    logger: logging.Logger,
    *,
    quiet_log: str,
    error_log: str,
    **kwargs: Any,
) -> bool:
    """若有推送通道且不在免打扰时段，则发送文本推送。"""
    if push is None:
        return False
    if is_in_quiet_hours(config):
        logger.debug(quiet_log)
        return False
    try:
        await push.send_text(**kwargs)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(error_log, exc)
        return False


@dataclass(frozen=True)
class AccountRunResult:
    success: bool
    message: str
    detail: str = ""


def any_success(results: list[AccountRunResult]) -> bool:
    return any(result.success for result in results)
