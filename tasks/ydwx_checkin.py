"""一点万象签到任务模块。参考 only_for_happly/ydwx.py。"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)
GATEWAY_URL = "https://app.mixcapp.com/mixc/gateway"


def _run_ydwx_sync(device_params: str, token: str) -> tuple[bool, str]:
    try:
        timestamp = str(int(round(time.time() * 1000)))
        sig_str = (
            "action=mixc.app.memberSign.sign&apiVersion=1.0&appId=68a91a5bac6a4f3e91bf4b42856785c6"
            "&appVersion=3.53.0&deviceParams={}&imei=2333&mallNo=20014&osVersion=12.0.1"
            "&params=eyJtYWxsTm8iOiIyMDAxNCJ9&platform=h5&timestamp={}&token={}&P@Gkbu0shTNHjhM!7F"
        ).format(device_params, timestamp, token)
        sign = hashlib.md5(sig_str.encode("utf-8")).hexdigest()
        data = (
            "mallNo=20014&appId=68a91a5bac6a4f3e91bf4b42856785c6&platform=h5&imei=2333&appVersion=3.53.0"
            "&osVersion=12.0.1&action=mixc.app.memberSign.sign&apiVersion=1.0&timestamp={}"
            "&deviceParams={}&token={}&params=eyJtYWxsTm8iOiIyMDAxNCJ9&sign={}"
        ).format(timestamp, device_params, token, sign)
        headers = {
            "Host": "app.mixcapp.com",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; wv) AppleWebKit/537.36 Chrome/77.0.3865.92 Mobile Safari/537.36/MIXCAPP/3.42.2",
            "Referer": "https://app.mixcapp.com/m/m-20014/signIn?showWebNavigation=true&timestamp=1676906528979&appVersion=3.53.0&mallNo=20014",
        }
        r = requests.post(GATEWAY_URL, headers=headers, data=data, timeout=15)
        r.raise_for_status()
        msg = (r.json() or {}).get("message", r.text)
        return True, msg
    except Exception as e:
        logger.warning("一点万象签到：请求失败 %s", e)
        return False, str(e)


async def run_ydwx_checkin_once() -> None:
    from dataclasses import dataclass

    @dataclass
    class YdwxConfig:
        enable: bool
        device_params: str
        token: str
        accounts: list[dict]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> "YdwxConfig":
            accounts = getattr(config, "ydwx_accounts", None) or []
            dp = (getattr(config, "ydwx_device_params", None) or "").strip()
            tk = (getattr(config, "ydwx_token", None) or "").strip()
            if not accounts and (dp or tk):
                accounts = [{"device_params": dp, "token": tk}]
            return cls(
                enable=getattr(config, "ydwx_enable", False),
                device_params=dp,
                token=tk,
                accounts=accounts,
                time=(getattr(config, "ydwx_time", None) or "06:00").strip() or "06:00",
                push_channels=getattr(config, "ydwx_push_channels", None) or [],
            )

        def validate(self) -> bool:
            if not self.enable:
                return False
            effective = self.accounts or []
            if not effective or not any(a.get("device_params") or a.get("token") for a in effective):
                return False
            return True

    app_config = get_config(reload=True)
    cfg = YdwxConfig.from_app_config(app_config)
    if not cfg.validate():
        return
    effective = [a for a in cfg.accounts if a.get("device_params") or a.get("token")]
    logger.info("一点万象签到：开始执行（共 %d 个账号）", len(effective))
    import aiohttp
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        push_manager = await build_push_manager(
            app_config.push_channel_list, session, logger,
            init_fail_prefix="一点万象：", channel_names=cfg.push_channels or None,
        )
        for idx, acc in enumerate(effective):
            dp, tk = acc.get("device_params", ""), acc.get("token", "")
            try:
                ok, msg = await asyncio.to_thread(_run_ydwx_sync, dp, tk)
            except Exception as e:
                ok, msg = False, str(e)
            if push_manager and not is_in_quiet_hours(app_config):
                try:
                    await push_manager.send_news(
                        title="一点万象签到成功" if ok else "一点万象签到失败",
                        description="账号%d: %s" % (idx + 1, msg),
                        to_url="https://app.mixcapp.com", picurl="", btntxt="打开",
                    )
                except Exception:
                    pass
        if push_manager:
            await push_manager.close()
    logger.info("一点万象签到：结束（共 %d 个账号）", len(effective))


register_task("ydwx_checkin", run_ydwx_checkin_once, lambda c: {"minute": parse_checkin_time(getattr(c, "ydwx_time", "06:00") or "06:00")[1], "hour": parse_checkin_time(getattr(c, "ydwx_time", "06:00") or "06:00")[0]})
