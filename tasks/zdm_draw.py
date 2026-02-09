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

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager
from src.utils import mask_cookie_for_log

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
    try:
        for active_id in ids:
            url = f"https://zhiyou.smzdm.com/user/lottery/jsonp_draw?active_id={active_id}"
            r = requests.post(url, headers=headers, timeout=15)
            if r.status_code != 200:
                messages.append(f"active_id={active_id} 请求失败")
                continue
            text = r.text
            # 解析 jsonp 或 json 结果
            msg_m = re.search(r'"error_msg"\s*:\s*"([^"]*)"', text)
            if msg_m:
                messages.append(msg_m.group(1))
            else:
                messages.append("已抽奖")
        return True, "；".join(messages) if messages else "抽奖请求已提交"
    except Exception as e:
        logger.warning("值得买抽奖：请求失败 %s", e)
        return False, str(e)


async def run_zdm_draw_once() -> None:
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
            cookies: list[str] = getattr(config, "zdm_draw_cookies", None) or []
            single = (getattr(config, "zdm_draw_cookie", None) or "").strip()
            if not cookies and single:
                cookies = [single]
            push: list[str] = getattr(config, "zdm_draw_push_channels", None) or []
            return cls(
                enable=getattr(config, "zdm_draw_enable", False),
                cookie=single,
                cookies=cookies,
                time=(getattr(config, "zdm_draw_time", None) or "07:30").strip() or "07:30",
                push_channels=push,
            )

        def validate(self) -> bool:
            if not self.enable:
                logger.debug("值得买抽奖未启用，跳过")
                return False
            effective = self.cookies if self.cookies else ([self.cookie] if self.cookie else [])
            if not effective or not any(c.strip() for c in effective):
                logger.error("值得买抽奖配置不完整，缺少 cookie 或 cookies")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = ZdmDrawConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [c.strip() for c in cfg.cookies if c.strip()]
    if not effective and cfg.cookie:
        effective = [cfg.cookie.strip()]
    logger.info("值得买抽奖：开始执行（共 %d 个 Cookie）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="值得买抽奖：",
            channel_names=cfg.push_channels if cfg.push_channels else None,
        )

        for idx, cookie_str in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(
                    _run_zdm_draw_sync, cookie_str, DEFAULT_ACTIVE_IDS
                )
            except Exception as e:
                logger.error("值得买抽奖：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)

            if push_manager and not is_in_quiet_hours(app_config):
                masked = mask_cookie_for_log(cookie_str)
                title = "值得买抽奖成功" if ok else "值得买抽奖失败"
                body = f"{'✅' if ok else '❌'} Cookie: {masked}\n{msg}\n\n执行时间配置: {cfg.time}"
                try:
                    await push_manager.send_news(
                        title=title,
                        description=body,
                        to_url="https://www.smzdm.com",
                        picurl="",
                        btntxt="打开值得买",
                    )
                except Exception as exc:
                    logger.error("值得买抽奖：推送失败 %s", exc)

        if push_manager:
            await push_manager.close()

    logger.info("值得买抽奖：结束（共处理 %d 个账号）", len(effective))


def _get_zdm_draw_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "zdm_draw_time", "07:30") or "07:30")
    return {"minute": minute, "hour": hour}


register_task("zdm_draw", run_zdm_draw_once, _get_zdm_draw_trigger_kwargs)
