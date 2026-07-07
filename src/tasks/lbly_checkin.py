"""丽宝乐园小程序签到任务模块。参考 only_for_happly 丽宝乐园签到，请求体 JSON 调用 CheckinV2，支持多账号。"""

from __future__ import annotations

import asyncio
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

LBLY_CHECKIN_URL = "https://m.mallcoo.cn/api/user/User/CheckinV2"


def _run_lbly_sync(request_body: str) -> tuple[bool, str]:
    try:
        headers = {
            "content-type": "application/json",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.34(0x1800222f) NetType/4G Language/zh_CN",
        }
        r = requests.post(LBLY_CHECKIN_URL, headers=headers, data=request_body, timeout=15)
        r.raise_for_status()
        data = r.json()
        d = data.get("d", {})
        return True, f"{d.get('NickName', '')}\n{d.get('Msg', '')}"
    except Exception as e:
        logger.warning("丽宝乐园签到：请求失败 %s", e)
        return False, str(e)


async def run_lbly_checkin_once() -> bool:
    from dataclasses import dataclass

    @dataclass
    class LblyConfig:
        enable: bool
        request_body: str
        request_bodies: list[str]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> LblyConfig:
            single = (getattr(config, "lbly_request_body", None) or "").strip()
            return cls(
                enable=getattr(config, "lbly_enable", False),
                request_body=single,
                request_bodies=normalized_string_items(
                    getattr(config, "lbly_request_bodies", None), single
                ),
                time=(getattr(config, "lbly_time", None) or "05:30").strip() or "05:30",
                push_channels=task_push_channels(config, "lbly_push_channels"),
            )

        def validate(self) -> bool:
            if not self.enable:
                return False
            if not self.request_bodies:
                logger.error("丽宝乐园签到配置不完整")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = LblyConfig.from_app_config(app_config)
    if not cfg.validate():
        return TASK_FAILED

    effective = cfg.request_bodies
    any_success = False
    logger.info("丽宝乐园签到：开始执行（共 %d 个账号）", len(effective))

    async with push_manager_context(
        app_config,
        logger,
        push_channels=cfg.push_channels,
        init_fail_prefix="丽宝乐园签到：",
        timeout_seconds=30,
    ) as push_manager:
        for idx, body in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(_run_lbly_sync, body)
            except Exception as e:
                logger.error("丽宝乐园签到：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)
            if ok:
                any_success = True
            title = "丽宝乐园签到成功" if ok else "丽宝乐园签到失败"
            await send_news_if_allowed(
                push_manager,
                app_config,
                logger,
                quiet_log="丽宝乐园签到：免打扰时段，不发送推送",
                error_log="丽宝乐园签到：推送失败 %s",
                title=title,
                description=msg,
                to_url="https://m.mallcoo.cn",
                picurl="",
                btntxt="打开",
            )
    logger.info("丽宝乐园签到：结束（共 %d 个账号）", len(effective))
    return TASK_SUCCESS if any_success else TASK_FAILED


def _get_lbly_trigger_kwargs(config: AppConfig) -> dict:
    return cron_kwargs_from_config(config, "lbly_time", "05:30")


register_task(
    "lbly_checkin",
    run_lbly_checkin_once,
    _get_lbly_trigger_kwargs,
    description="丽宝乐园签到",
)
