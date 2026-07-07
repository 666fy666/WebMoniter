"""值得买每日抽奖任务模块

参考 only_for_happly 值得买每日转盘逻辑：
- 使用 Cookie 请求抽奖接口（可与 smzdm 共用 Cookie）
- 支持多 Cookie（多账号）
"""

from __future__ import annotations

import asyncio
import logging
import re

import requests

from src.core.utils import mask_cookie_for_log
from src.jobs.registry import register_task
from src.jobs.task_outcome import TASK_FAILED, TASK_SUCCESS
from src.settings.config import AppConfig, get_config
from src.tasks.common import (
    cron_kwargs_from_config,
    normalized_string_items,
    push_manager_context,
    send_news_if_allowed,
    task_push_channels,
)

logger = logging.getLogger(__name__)

# 活动 ID 列表（与 only_for_happly 一致，可配置扩展）
DEFAULT_ACTIVE_IDS = ["ljX8qVlEA7", "A6X1veWE2O", "ar7gwYZEq3"]


def _run_zdm_draw_sync(cookie: str, active_ids: list[str]) -> tuple[bool, str]:
    """
    同步执行值得买每日抽奖。

    Returns:
        (success, message)
    """
    ids = active_ids or DEFAULT_ACTIVE_IDS
    headers = {
        "Host": "zhiyou.smzdm.com",
        "Accept": "*/*",
        "Cookie": cookie,
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/smzdm 10.4.6 rv:130.1"
        ),
        "Referer": "https://m.smzdm.com/",
    }
    messages = []
    all_ok = True
    try:
        for active_id in ids:
            url = f"https://zhiyou.smzdm.com/user/lottery/jsonp_draw?active_id={active_id}"
            r = requests.post(url, headers=headers, timeout=15)
            if r.status_code != 200:
                messages.append(f"active_id={active_id} 请求失败")
                all_ok = False
                continue
            text = r.text
            # 解析 jsonp 或 json 结果
            msg_m = re.search(r'"error_msg"\s*:\s*"([^"]*)"', text)
            if msg_m:
                messages.append(msg_m.group(1))
            else:
                messages.append("已抽奖")
        return all_ok, "；".join(messages) if messages else "抽奖请求已提交"
    except Exception as e:
        logger.warning("值得买抽奖：请求失败 %s", e)
        return False, str(e)


async def run_zdm_draw_once() -> bool:
    """执行一次值得买每日抽奖（支持多 Cookie），并接入统一推送。"""
    from dataclasses import dataclass

    @dataclass
    class ZdmDrawConfig:
        enable: bool
        cookie: str
        cookies: list[str]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> ZdmDrawConfig:
            single = (getattr(config, "zdm_draw_cookie", None) or "").strip()
            return cls(
                enable=getattr(config, "zdm_draw_enable", False),
                cookie=single,
                cookies=normalized_string_items(getattr(config, "zdm_draw_cookies", None), single),
                time=(getattr(config, "zdm_draw_time", None) or "07:30").strip() or "07:30",
                push_channels=task_push_channels(config, "zdm_draw_push_channels"),
            )

        def validate(self) -> bool:
            if not self.enable:
                logger.debug("值得买抽奖未启用，跳过")
                return False
            if not self.cookies:
                logger.error("值得买抽奖配置不完整，缺少 cookie 或 cookies")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = ZdmDrawConfig.from_app_config(app_config)
    if not cfg.validate():
        return TASK_FAILED

    effective = cfg.cookies
    logger.info("值得买抽奖：开始执行（共 %d 个 Cookie）", len(effective))
    any_success = False

    async with push_manager_context(
        app_config,
        logger,
        push_channels=cfg.push_channels,
        init_fail_prefix="值得买抽奖：",
        timeout_seconds=30,
    ) as push_manager:
        for idx, cookie_str in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(
                    _run_zdm_draw_sync, cookie_str, DEFAULT_ACTIVE_IDS
                )
            except Exception as e:
                logger.error("值得买抽奖：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)

            if ok:
                any_success = True

            masked = mask_cookie_for_log(cookie_str)
            title = "值得买抽奖成功" if ok else "值得买抽奖失败"
            body = f"{'✅' if ok else '❌'} Cookie: {masked}\n{msg}\n\n执行时间配置: {cfg.time}"
            await send_news_if_allowed(
                push_manager,
                app_config,
                logger,
                quiet_log="值得买抽奖：免打扰时段，不发送推送",
                error_log="值得买抽奖：推送失败 %s",
                title=title,
                description=body,
                to_url="https://www.smzdm.com",
                picurl="",
                btntxt="打开值得买",
            )

    logger.info("值得买抽奖：结束（共处理 %d 个账号）", len(effective))
    return TASK_SUCCESS if any_success else TASK_FAILED


def _get_zdm_draw_trigger_kwargs(config: AppConfig) -> dict:
    return cron_kwargs_from_config(config, "zdm_draw_time", "07:30")


register_task(
    "zdm_draw",
    run_zdm_draw_once,
    _get_zdm_draw_trigger_kwargs,
    description="值得买每日抽奖",
)
