"""什么值得买签到任务模块

参考 only_for_happly 什么值得买签到逻辑：
- 使用 Cookie 先获取 token，再请求签到与全部奖励
- 支持多 Cookie（多账号）
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager
from src.utils import mask_cookie_for_log

logger = logging.getLogger(__name__)

SIGN_KEY = "apr1$AwP!wRRT$gJ/q.X24poeBInlUJC"
SMZDM_TOKEN_URL = "https://user-api.smzdm.com/robot/token"
SMZDM_CHECKIN_URL = "https://user-api.smzdm.com/checkin"
SMZDM_ALL_REWARD_URL = "https://user-api.smzdm.com/checkin/all_reward"


def _run_smzdm_sync(cookie: str) -> tuple[bool, str]:
    """
    同步执行什么值得买签到。

    Returns:
        (success, message)
    """
    try:
        ts = int(round(time.time() * 1000))
        headers = {
            "Host": "user-api.smzdm.com",
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": cookie,
            "User-Agent": "smzdm_android_V10.4.1 rv:841 (22021211RC;Android12;zh)smzdmapp",
        }
        data_token = {
            "f": "android",
            "v": "10.4.1",
            "weixin": 1,
            "time": ts,
            "sign": hashlib.md5(
                f"f=android&time={ts}&v=10.4.1&weixin=1&key={SIGN_KEY}".encode("utf-8")
            ).hexdigest().upper(),
        }
        r = requests.post(SMZDM_TOKEN_URL, headers=headers, data=data_token, timeout=15)
        r.raise_for_status()
        result = r.json()
        token = result.get("data", {}).get("token")
        if not token:
            return False, result.get("error_msg", "获取 token 失败")
        ts2 = int(round(time.time() * 1000))
        sk = "ierkM0OZZbsuBKLoAgQ6OJneLMXBQXmzX+LXkNTuKch8Ui2jGlahuFyWIzBiDq/L"
        sign2 = hashlib.md5(
            f"f=android&sk={sk}&time={ts2}&token={token}&v=10.4.1&weixin=1&key={SIGN_KEY}".encode(
                "utf-8"
            )
        ).hexdigest().upper()
        data_check = {
            "f": "android",
            "v": "10.4.1",
            "sk": sk,
            "weixin": 1,
            "time": ts2,
            "token": token,
            "sign": sign2,
        }
        r2 = requests.post(SMZDM_CHECKIN_URL, headers=headers, data=data_check, timeout=15)
        r2.raise_for_status()
        err_msg = r2.json().get("error_msg", "签到成功")
        r3 = requests.post(SMZDM_ALL_REWARD_URL, headers=headers, data=data_check, timeout=15)
        if r3.status_code == 200:
            try:
                r3.json()
            except Exception:
                pass
        return True, err_msg
    except requests.RequestException as e:
        logger.warning("什么值得买签到：请求失败 %s", e)
        return False, f"请求失败: {e}"
    except Exception as e:
        logger.warning("什么值得买签到：异常 %s", e)
        return False, str(e)


async def run_smzdm_checkin_once() -> None:
    """执行一次什么值得买签到（支持多 Cookie），并接入统一推送。"""
    from dataclasses import dataclass

    @dataclass
    class SmzdmConfig:
        enable: bool
        cookie: str
        cookies: list[str]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> "SmzdmConfig":
            cookies: list[str] = getattr(config, "smzdm_cookies", None) or []
            single = (getattr(config, "smzdm_cookie", None) or "").strip()
            if not cookies and single:
                cookies = [single]
            push: list[str] = getattr(config, "smzdm_push_channels", None) or []
            return cls(
                enable=getattr(config, "smzdm_enable", False),
                cookie=single,
                cookies=cookies,
                time=(getattr(config, "smzdm_time", None) or "00:30").strip() or "00:30",
                push_channels=push,
            )

        def validate(self) -> bool:
            if not self.enable:
                logger.debug("什么值得买签到未启用，跳过")
                return False
            effective = self.cookies if self.cookies else ([self.cookie] if self.cookie else [])
            if not effective or not any(c.strip() for c in effective):
                logger.error("什么值得买签到配置不完整，缺少 cookie 或 cookies")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = SmzdmConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [c.strip() for c in cfg.cookies if c.strip()]
    if not effective and cfg.cookie:
        effective = [cfg.cookie.strip()]
    logger.info("什么值得买签到：开始执行（共 %d 个 Cookie）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="什么值得买签到：",
            channel_names=cfg.push_channels if cfg.push_channels else None,
        )

        for idx, cookie_str in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(_run_smzdm_sync, cookie_str)
            except Exception as e:
                logger.error("什么值得买签到：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)

            if push_manager and not is_in_quiet_hours(app_config):
                masked = mask_cookie_for_log(cookie_str)
                title = "什么值得买签到成功" if ok else "什么值得买签到失败"
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
                    logger.error("什么值得买签到：推送失败 %s", exc)

        if push_manager:
            await push_manager.close()

    logger.info("什么值得买签到：结束（共处理 %d 个账号）", len(effective))


def _get_smzdm_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "smzdm_time", "00:30") or "00:30")
    return {"minute": minute, "hour": hour}


register_task("smzdm_checkin", run_smzdm_checkin_once, _get_smzdm_trigger_kwargs)
