"""星空代理签到任务模块。参考 only_for_happly/xingkong.py。"""

from __future__ import annotations

import asyncio
import logging

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import build_push_manager

logger = logging.getLogger(__name__)
LOGIN_URL = "https://www.xkdaili.com/tools/submit_ajax.ashx?action=user_login&site_id=1"
SIGN_URL = "https://www.xkdaili.com/tools/submit_ajax.ashx?action=user_receive_point"


def _run_xingkong_sync(username: str, password: str) -> tuple[bool, str]:
    try:
        session = requests.Session()
        session.verify = False
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 Chrome/86.0.4240.198 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": "https://www.xkdaili.com/",
            }
        )
        r1 = session.post(
            LOGIN_URL, data={"username": username, "password": password, "remember": 1}, timeout=15
        )
        r1.raise_for_status()
        login_msg = (r1.json() or {}).get("msg", "")
        if not session.cookies:
            return False, "登录失败: " + login_msg
        r2 = session.post(SIGN_URL, data={"type": "login"}, timeout=15)
        r2.raise_for_status()
        sign_msg = (r2.json() or {}).get("msg", r2.text)
        return True, f"登录: {login_msg}; 签到: {sign_msg}"
    except Exception as e:
        logger.warning("星空代理签到：请求失败 %s", e)
        return False, str(e)


async def run_xingkong_checkin_once() -> None:
    from dataclasses import dataclass

    @dataclass
    class XingkongConfig:
        enable: bool
        username: str
        password: str
        accounts: list[dict]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> XingkongConfig:
            accounts = getattr(config, "xingkong_accounts", None) or []
            u = (getattr(config, "xingkong_username", None) or "").strip()
            p = (getattr(config, "xingkong_password", None) or "").strip()
            if not accounts and (u or p):
                accounts = [{"username": u, "password": p}]
            return cls(
                enable=getattr(config, "xingkong_enable", False),
                username=u,
                password=p,
                accounts=accounts,
                time=(getattr(config, "xingkong_time", None) or "07:30").strip() or "07:30",
                push_channels=getattr(config, "xingkong_push_channels", None) or [],
            )

        def validate(self) -> bool:
            if not self.enable:
                return False
            effective = self.accounts or []
            if not effective or not any(a.get("username") for a in effective):
                return False
            return True

    app_config = get_config(reload=True)
    cfg = XingkongConfig.from_app_config(app_config)
    if not cfg.validate():
        return
    effective = [a for a in cfg.accounts if a.get("username")]
    logger.info("星空代理签到：开始执行（共 %d 个账号）", len(effective))
    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        push_manager = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="星空代理：",
            channel_names=cfg.push_channels or None,
        )
        for idx, acc in enumerate(effective):
            u, p = acc.get("username", ""), acc.get("password", "")
            try:
                ok, msg = await asyncio.to_thread(_run_xingkong_sync, u, p)
            except Exception as e:
                ok, msg = False, str(e)
            if push_manager and not is_in_quiet_hours(app_config):
                try:
                    await push_manager.send_news(
                        title="星空代理签到成功" if ok else "星空代理签到失败",
                        description=f"账号{idx + 1}: {msg}",
                        to_url="https://www.xkdaili.com",
                        picurl="",
                        btntxt="打开",
                    )
                except Exception:
                    pass
        if push_manager:
            await push_manager.close()
    logger.info("星空代理签到：结束（共 %d 个账号）", len(effective))


register_task(
    "xingkong_checkin",
    run_xingkong_checkin_once,
    lambda c: {
        "minute": parse_checkin_time(getattr(c, "xingkong_time", "07:30") or "07:30")[1],
        "hour": parse_checkin_time(getattr(c, "xingkong_time", "07:30") or "07:30")[0],
    },
)
