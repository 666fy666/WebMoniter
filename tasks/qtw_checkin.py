"""千图网签到任务模块

参考 only_for_happly/qtw.py：Cookie 获取 token 后提交签到，多 Cookie。
"""

from __future__ import annotations

import asyncio
import datetime
import logging

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

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


async def run_qtw_checkin_once() -> None:
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
            cookies: list[str] = getattr(config, "qtw_cookies", None) or []
            single = (getattr(config, "qtw_cookie", None) or "").strip()
            if not cookies and single:
                cookies = [single]
            return cls(
                enable=getattr(config, "qtw_enable", False),
                cookie=single,
                cookies=cookies,
                time=(getattr(config, "qtw_time", None) or "01:30").strip() or "01:30",
                push_channels=getattr(config, "qtw_push_channels", None) or [],
            )

        def validate(self) -> bool:
            if not self.enable:
                return False
            effective = self.cookies or ([self.cookie] if self.cookie else [])
            if not effective or not any(c.strip() for c in effective):
                logger.error("千图网配置不完整，缺少 cookie 或 cookies")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = QtwConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [c.strip() for c in cfg.cookies if c.strip()]
    if not effective and cfg.cookie:
        effective = [cfg.cookie.strip()]
    logger.info("千图网签到：开始执行（共 %d 个账号）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="千图网：",
            channel_names=cfg.push_channels or None,
        )
        for idx, cookie in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(_run_qtw_sync, cookie)
            except Exception as e:
                logger.error("千图网：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)
            if push_manager and not is_in_quiet_hours(app_config):
                title = "千图网签到成功" if ok else "千图网签到失败"
                try:
                    await push_manager.send_news(
                        title=title,
                        description=f"账号{idx + 1}: {msg}",
                        to_url="https://www.58pic.com",
                        picurl="",
                        btntxt="打开",
                    )
                except Exception as exc:
                    logger.error("千图网：推送失败 %s", exc)
        if push_manager:
            await push_manager.close()
    logger.info("千图网签到：结束（共处理 %d 个账号）", len(effective))


def _get_qtw_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "qtw_time", "01:30") or "01:30")
    return {"minute": minute, "hour": hour}


register_task("qtw_checkin", run_qtw_checkin_once, _get_qtw_trigger_kwargs)
