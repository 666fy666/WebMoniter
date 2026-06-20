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

from src.core.utils import mask_cookie_for_log
from src.jobs.registry import register_task
from src.jobs.task_outcome import TASK_FAILED, TASK_SUCCESS
from src.push_channel.manager import UnifiedPushManager, build_push_manager
from src.settings.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time

logger = logging.getLogger(__name__)

SIGN_KEY = "apr1$AwP!wRRT$gJ/q.X24poeBInlUJC"
SMZDM_TOKEN_URL = "https://user-api.smzdm.com/robot/token"
SMZDM_CHECKIN_URL = "https://user-api.smzdm.com/checkin"
SMZDM_ALL_REWARD_URL = "https://user-api.smzdm.com/checkin/all_reward"

# SMZDM 移动端 API 成功时 error_code 为 0 或字符串 "0"（见 hex-ci/smzdm_script bot.js）
_SMZDM_SUCCESS_CODES = frozenset({None, 0, "0"})


def _smzdm_api_success(body: object) -> bool:
    """判断 SMZDM API JSON 是否表示成功。"""
    if not isinstance(body, dict):
        return False
    return body.get("error_code") in _SMZDM_SUCCESS_CODES


def _smzdm_data(body: dict) -> dict:
    """安全读取 SMZDM API 的 data 字段（可能为 null 或非 dict）。"""
    data = body.get("data")
    return data if isinstance(data, dict) else {}


def _smzdm_error_msg(body: dict, default: str) -> str:
    msg = body.get("error_msg")
    if isinstance(msg, str) and msg.strip():
        return msg.strip()
    return default


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
            "sign": hashlib.md5(f"f=android&time={ts}&v=10.4.1&weixin=1&key={SIGN_KEY}".encode())
            .hexdigest()
            .upper(),
        }
        r = requests.post(SMZDM_TOKEN_URL, headers=headers, data=data_token, timeout=15)
        r.raise_for_status()
        result = r.json()
        if not isinstance(result, dict):
            return False, "获取 token 失败：响应格式异常"
        if not _smzdm_api_success(result):
            return False, _smzdm_error_msg(result, "获取 token 失败")
        token = _smzdm_data(result).get("token")
        if not token:
            return False, _smzdm_error_msg(result, "获取 token 失败")
        ts2 = int(round(time.time() * 1000))
        sk = "ierkM0OZZbsuBKLoAgQ6OJneLMXBQXmzX+LXkNTuKch8Ui2jGlahuFyWIzBiDq/L"
        sign2 = (
            hashlib.md5(
                f"f=android&sk={sk}&time={ts2}&token={token}&v=10.4.1&weixin=1&key={SIGN_KEY}".encode()
            )
            .hexdigest()
            .upper()
        )
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
        check_result = r2.json()
        if not isinstance(check_result, dict):
            return False, "签到失败：响应格式异常"
        if not _smzdm_api_success(check_result):
            return False, _smzdm_error_msg(check_result, "签到失败")
        check_data = _smzdm_data(check_result)
        if not check_data:
            return False, _smzdm_error_msg(check_result, "签到失败：响应数据为空")
        err_msg = _smzdm_error_msg(check_result, "签到成功")
        r3 = requests.post(SMZDM_ALL_REWARD_URL, headers=headers, data=data_check, timeout=15)
        if r3.status_code == 200:
            try:
                reward_result = r3.json()
                if isinstance(reward_result, dict) and _smzdm_api_success(reward_result):
                    reward_data = _smzdm_data(reward_result)
                    normal = reward_data.get("normal_reward") if isinstance(
                        reward_data.get("normal_reward"), dict
                    ) else {}
                    reward_add = normal.get("reward_add") if isinstance(
                        normal.get("reward_add"), dict
                    ) else {}
                    reward_title = reward_add.get("title")
                    reward_content = reward_add.get("content")
                    if isinstance(reward_title, str) and reward_title.strip():
                        extra = reward_title.strip()
                        if isinstance(reward_content, str) and reward_content.strip():
                            extra = f"{extra}: {reward_content.strip()}"
                        err_msg = f"{err_msg}\n{extra}"
            except Exception:
                pass
        return True, err_msg
    except requests.RequestException as e:
        logger.warning("什么值得买签到：请求失败 %s", e)
        return False, f"请求失败: {e}"
    except Exception as e:
        logger.warning("什么值得买签到：异常 %s", e)
        return False, str(e)


async def run_smzdm_checkin_once() -> bool:
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
        def from_app_config(cls, config: AppConfig) -> SmzdmConfig:
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
        return TASK_FAILED

    effective = [c.strip() for c in cfg.cookies if c.strip()]
    if not effective and cfg.cookie:
        effective = [cfg.cookie.strip()]
    logger.info("什么值得买签到：开始执行（共 %d 个 Cookie）", len(effective))
    any_success = False

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

            if ok:
                any_success = True

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
    return TASK_SUCCESS if any_success else TASK_FAILED


def _get_smzdm_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "smzdm_time", "00:30") or "00:30")
    return {"minute": minute, "hour": hour}


register_task(
    "smzdm_checkin",
    run_smzdm_checkin_once,
    _get_smzdm_trigger_kwargs,
    description="什么值得买签到",
)
