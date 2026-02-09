"""品赞代理签到任务模块。参考 only_for_happly 品赞逻辑：账号#密码登录后领取 IP，支持多账号。"""

from __future__ import annotations

import asyncio
import base64
import logging
import random

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)

PINZAN_LOGIN_URL = "https://service.ipzan.com/users-login"
PINZAN_RECEIVE_URL = "https://service.ipzan.com/home/userWallet-receive"
FIXED_KEY = "QWERIPZAN1290QWER"


def _encrypt_account(account: str, password: str) -> str:
    plain = f"{account}{FIXED_KEY}{password}"
    encoded = base64.b64encode(plain.encode("utf-8")).decode("utf-8")
    random_hex = "".join(hex(int(random.random() * 10**16))[2:] for _ in range(80)).ljust(400, "0")[:400]
    parts = [
        random_hex[:100], encoded[:8],
        random_hex[100:200], encoded[8:20],
        random_hex[200:300], encoded[20:],
        random_hex[300:400],
    ]
    return "".join(parts)


def _run_pinzan_sync(account: str, password: str) -> tuple[bool, str]:
    try:
        session = requests.Session()
        session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://ipzan.com",
            "Referer": "https://ipzan.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        })
        enc = _encrypt_account(account, password)
        r = session.post(PINZAN_LOGIN_URL, json={"account": enc, "source": "ipzan-home-one"}, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            return False, data.get("message", "登录失败")
        token = (data.get("data") or {}).get("token")
        if not token:
            return False, "未返回 Token"
        session.headers["Authorization"] = f"Bearer {token}"
        r2 = session.get(PINZAN_RECEIVE_URL, timeout=15)
        r2.raise_for_status()
        rec = r2.json()
        code = rec.get("code")
        msg = rec.get("message", "")
        if code == 0:
            return True, f"领取成功：{rec.get('data', '')}"
        if code == -1 and "领取过" in str(msg):
            return True, f"本周已领：{msg}"
        return False, msg or "领取失败"
    except Exception as e:
        logger.warning("品赞签到：请求失败 %s", e)
        return False, str(e)


async def run_pinzan_checkin_once() -> None:
    from dataclasses import dataclass

    @dataclass
    class PinzanConfig:
        enable: bool
        account: str
        password: str
        accounts: list[dict]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> "PinzanConfig":
            accounts: list[dict] = getattr(config, "pinzan_accounts", None) or []
            single_a = (getattr(config, "pinzan_account", None) or "").strip()
            single_p = (getattr(config, "pinzan_password", None) or "").strip()
            if not accounts and (single_a or single_p):
                accounts = [{"account": single_a, "password": single_p}]
            push: list[str] = getattr(config, "pinzan_push_channels", None) or []
            return cls(
                enable=getattr(config, "pinzan_enable", False),
                account=single_a,
                password=single_p,
                accounts=accounts,
                time=(getattr(config, "pinzan_time", None) or "08:00").strip() or "08:00",
                push_channels=push,
            )

        def validate(self) -> bool:
            if not self.enable:
                return False
            effective = self.accounts or ([{"account": self.account, "password": self.password}] if (self.account or self.password) else [])
            if not effective or not any((a.get("account") or "").strip() and (a.get("password") or "").strip() for a in effective):
                logger.error("品赞签到配置不完整")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = PinzanConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [{"account": (a.get("account") or "").strip(), "password": (a.get("password") or "").strip()} for a in (cfg.accounts or []) if (a.get("account") or "").strip() and (a.get("password") or "").strip()]
    if not effective and cfg.account and cfg.password:
        effective = [{"account": cfg.account, "password": cfg.password}]
    logger.info("品赞签到：开始执行（共 %d 个账号）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list, session, logger,
            init_fail_prefix="品赞签到：", channel_names=cfg.push_channels or None,
        )
        for idx, acc in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(_run_pinzan_sync, acc["account"], acc["password"])
            except Exception as e:
                logger.error("品赞签到：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)
            if push_manager and not is_in_quiet_hours(app_config):
                masked = acc["account"][:3] + "****" + acc["account"][-4:] if len(acc["account"]) >= 7 else "***"
                title = "品赞签到成功" if ok else "品赞签到失败"
                try:
                    await push_manager.send_news(title=title, description=f"账号 {masked}\n{msg}", to_url="https://www.ipzan.com", picurl="", btntxt="打开")
                except Exception as exc:
                    logger.error("品赞签到：推送失败 %s", exc)
        if push_manager:
            await push_manager.close()
    logger.info("品赞签到：结束（共 %d 个账号）", len(effective))


def _get_pinzan_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "pinzan_time", "08:00") or "08:00")
    return {"minute": minute, "hour": hour}


register_task("pinzan_checkin", run_pinzan_checkin_once, _get_pinzan_trigger_kwargs)
