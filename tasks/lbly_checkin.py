"""丽宝乐园小程序签到任务模块。参考 only_for_happly 丽宝乐园签到，请求体 JSON 调用 CheckinV2，支持多账号。"""

from __future__ import annotations

import asyncio
import logging

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

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


async def run_lbly_checkin_once() -> None:
    from dataclasses import dataclass

    @dataclass
    class LblyConfig:
        enable: bool
        request_body: str
        request_bodies: list[str]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> "LblyConfig":
            bodies: list[str] = getattr(config, "lbly_request_bodies", None) or []
            single = (getattr(config, "lbly_request_body", None) or "").strip()
            if not bodies and single:
                bodies = [single]
            push: list[str] = getattr(config, "lbly_push_channels", None) or []
            return cls(
                enable=getattr(config, "lbly_enable", False),
                request_body=single,
                request_bodies=bodies,
                time=(getattr(config, "lbly_time", None) or "05:30").strip() or "05:30",
                push_channels=push,
            )

        def validate(self) -> bool:
            if not self.enable:
                return False
            effective = self.request_bodies or ([self.request_body] if self.request_body else [])
            if not effective or not any(b.strip() for b in effective):
                logger.error("丽宝乐园签到配置不完整")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = LblyConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [b.strip() for b in cfg.request_bodies if b.strip()]
    if not effective and cfg.request_body:
        effective = [cfg.request_body.strip()]
    logger.info("丽宝乐园签到：开始执行（共 %d 个账号）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list, session, logger,
            init_fail_prefix="丽宝乐园签到：", channel_names=cfg.push_channels or None,
        )
        for idx, body in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(_run_lbly_sync, body)
            except Exception as e:
                logger.error("丽宝乐园签到：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)
            if push_manager and not is_in_quiet_hours(app_config):
                title = "丽宝乐园签到成功" if ok else "丽宝乐园签到失败"
                try:
                    await push_manager.send_news(title=title, description=msg, to_url="https://m.mallcoo.cn", picurl="", btntxt="打开")
                except Exception as exc:
                    logger.error("丽宝乐园签到：推送失败 %s", exc)
        if push_manager:
            await push_manager.close()
    logger.info("丽宝乐园签到：结束（共 %d 个账号）", len(effective))


def _get_lbly_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "lbly_time", "05:30") or "05:30")
    return {"minute": minute, "hour": hour}


register_task("lbly_checkin", run_lbly_checkin_once, _get_lbly_trigger_kwargs)
