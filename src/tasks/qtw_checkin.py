"""千图网签到任务模块

参考 only_for_happly/qtw.py：Cookie 获取 token 后提交签到，多 Cookie。
"""

from __future__ import annotations

import asyncio
import datetime
import logging

import requests

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

GET_TOKEN_URL = "https://www.58pic.com/index.php?m=ajax&a=getApiToken"
SIGN_URL = "https://ajax-api.58pic.com/Growing/user-task/index"


def _run_qtw_sync(cookie: str) -> tuple[bool, str]:
    """同步执行千图网签到。"""
    try:
        headers1 = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
            "Cookie": cookie,
            "Referer": "https://www.58pic.com/",
        }
        r1 = requests.post(GET_TOKEN_URL, headers=headers1, timeout=15)
        r1.raise_for_status()
        token = (r1.json() or {}).get("data", {}).get("token", "")
        if not token:
            return False, "获取 token 失败"
        weekday = datetime.date.today().weekday() + 1
        r2 = requests.post(
            SIGN_URL,
            headers={"User-Agent": headers1["User-Agent"]},
            data={"token": token},
            timeout=15,
        )
        r2.raise_for_status()
        data = (r2.json() or {}).get("data", {})
        day_data = data.get("signData", {}).get(str(weekday), {})
        is_sign = day_data.get("isSign", 0)
        reward = day_data.get("title", "")
        if is_sign == 1:
            return True, f"今日签到成功，获得: {reward}"
        return False, "签到失败或已签到"
    except Exception as e:
        logger.warning("千图网签到：请求失败 %s", e)
        return False, str(e)


async def run_qtw_checkin_once() -> bool:
    """执行一次千图网签到（多 Cookie），并接入统一推送。"""
    from dataclasses import dataclass

    @dataclass
    class QtwConfig:
        enable: bool
        cookie: str
        cookies: list[str]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> QtwConfig:
            single = (getattr(config, "qtw_cookie", None) or "").strip()
            return cls(
                enable=getattr(config, "qtw_enable", False),
                cookie=single,
                cookies=normalized_string_items(getattr(config, "qtw_cookies", None), single),
                time=(getattr(config, "qtw_time", None) or "01:30").strip() or "01:30",
                push_channels=task_push_channels(config, "qtw_push_channels"),
            )

        def validate(self) -> bool:
            if not self.enable:
                return False
            if not self.cookies:
                logger.error("千图网配置不完整，缺少 cookie 或 cookies")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = QtwConfig.from_app_config(app_config)
    if not cfg.validate():
        return TASK_FAILED

    effective = cfg.cookies
    any_success = False
    logger.info("千图网签到：开始执行（共 %d 个账号）", len(effective))

    async with push_manager_context(
        app_config,
        logger,
        push_channels=cfg.push_channels,
        init_fail_prefix="千图网：",
        timeout_seconds=30,
    ) as push_manager:
        for idx, cookie in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(_run_qtw_sync, cookie)
            except Exception as e:
                logger.error("千图网：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)
            if ok:
                any_success = True
            title = "千图网签到成功" if ok else "千图网签到失败"
            await send_news_if_allowed(
                push_manager,
                app_config,
                logger,
                quiet_log="千图网：免打扰时段，不发送推送",
                error_log="千图网：推送失败 %s",
                title=title,
                description=f"账号{idx + 1}: {msg}",
                to_url="https://www.58pic.com",
                picurl="",
                btntxt="打开",
            )
    logger.info("千图网签到：结束（共处理 %d 个账号）", len(effective))
    return TASK_SUCCESS if any_success else TASK_FAILED


def _get_qtw_trigger_kwargs(config: AppConfig) -> dict:
    return cron_kwargs_from_config(config, "qtw_time", "01:30")


register_task(
    "qtw_checkin",
    run_qtw_checkin_once,
    _get_qtw_trigger_kwargs,
    description="千图网签到",
)
