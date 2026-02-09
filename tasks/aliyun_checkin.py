"""阿里云盘签到任务模块

参考 only_for_happly 阿里云盘签到逻辑：
- 使用 refresh_token 换取 access_token，再调用签到与领奖接口
- 支持多 refresh_token（多账号）
"""

from __future__ import annotations

import asyncio
import json
import logging

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)

ALIYUN_TOKEN_URL = "https://auth.aliyundrive.com/v2/account/token"
ALIYUN_SIGN_LIST_URL = "https://member.aliyundrive.com/v1/activity/sign_in_list"
ALIYUN_SIGN_REWARD_URL = "https://member.aliyundrive.com/v1/activity/sign_in_reward"


def _run_aliyun_sync(refresh_token: str) -> tuple[bool, str]:
    """
    同步执行阿里云盘签到。

    Returns:
        (success, message)
    """
    try:
        # 使用 refresh_token 获取 access_token
        r = requests.post(
            ALIYUN_TOKEN_URL,
            json={"grant_type": "refresh_token", "refresh_token": refresh_token},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        access_token = data.get("access_token")
        if not access_token:
            return False, "获取 access_token 失败"
        headers = {
            "Authorization": access_token,
            "Content-Type": "application/json",
        }
        # 签到列表
        r2 = requests.post(ALIYUN_SIGN_LIST_URL, headers=headers, json={}, timeout=15)
        r2.raise_for_status()
        result = r2.json()
        res = result.get("result", {})
        sign_in_count = res.get("signInCount", 0)
        sign_in_logs = res.get("signInLogs", [])
        # 领取今日奖励
        reward_msg = ""
        for i, log in enumerate(sign_in_logs):
            if log.get("status") == "miss":
                if i > 0:
                    day_json = sign_in_logs[i - 1]
                    if not day_json.get("isReward"):
                        reward_msg = "今日未获得奖励"
                    else:
                        reward = day_json.get("reward", {})
                        reward_msg = "本月累计签到{}天，今日签到获得 {} {}".format(
                            sign_in_count,
                            reward.get("name", ""),
                            reward.get("description", ""),
                        )
                break
        else:
            reward_msg = f"本月累计签到{sign_in_count}天"
        # 领取接口（按需）
        sign_data = {"signInDay": sign_in_count}
        r3 = requests.post(
            ALIYUN_SIGN_REWARD_URL,
            headers=headers,
            data=json.dumps(sign_data),
            timeout=15,
        )
        if r3.status_code == 200:
            try:
                r3.json()
            except Exception:
                pass
        return True, reward_msg or "签到成功"
    except requests.RequestException as e:
        logger.warning("阿里云盘签到：请求失败 %s", e)
        return False, f"请求失败: {e}"
    except Exception as e:
        logger.warning("阿里云盘签到：异常 %s", e)
        return False, str(e)


async def run_aliyun_checkin_once() -> None:
    """执行一次阿里云盘签到（支持多 refresh_token），并接入统一推送。"""
    from dataclasses import dataclass

    @dataclass
    class AliyunConfig:
        enable: bool
        refresh_token: str
        refresh_tokens: list[str]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> AliyunConfig:
            tokens: list[str] = getattr(config, "aliyun_refresh_tokens", None) or []
            single = (getattr(config, "aliyun_refresh_token", None) or "").strip()
            if not tokens and single:
                tokens = [single]
            push: list[str] = getattr(config, "aliyun_push_channels", None) or []
            return cls(
                enable=getattr(config, "aliyun_enable", False),
                refresh_token=single,
                refresh_tokens=tokens,
                time=(getattr(config, "aliyun_time", None) or "05:30").strip() or "05:30",
                push_channels=push,
            )

        def validate(self) -> bool:
            if not self.enable:
                logger.debug("阿里云盘签到未启用，跳过")
                return False
            effective = (
                self.refresh_tokens
                if self.refresh_tokens
                else ([self.refresh_token] if self.refresh_token else [])
            )
            if not effective or not any(t.strip() for t in effective):
                logger.error("阿里云盘签到配置不完整，缺少 refresh_token 或 refresh_tokens")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = AliyunConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [t.strip() for t in cfg.refresh_tokens if t.strip()]
    if not effective and cfg.refresh_token:
        effective = [cfg.refresh_token.strip()]
    logger.info("阿里云盘签到：开始执行（共 %d 个账号）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="阿里云盘签到：",
            channel_names=cfg.push_channels if cfg.push_channels else None,
        )

        for idx, token in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(_run_aliyun_sync, token)
            except Exception as e:
                logger.error("阿里云盘签到：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)

            if push_manager and not is_in_quiet_hours(app_config):
                masked = token[:8] + "***" + token[-4:] if len(token) > 12 else "***"
                title = "阿里云盘签到成功" if ok else "阿里云盘签到失败"
                body = f"{'✅' if ok else '❌'} 账号: {masked}\n{msg}\n\n执行时间配置: {cfg.time}"
                try:
                    await push_manager.send_news(
                        title=title,
                        description=body,
                        to_url="https://www.aliyundrive.com",
                        picurl="",
                        btntxt="打开云盘",
                    )
                except Exception as exc:
                    logger.error("阿里云盘签到：推送失败 %s", exc)

        if push_manager:
            await push_manager.close()

    logger.info("阿里云盘签到：结束（共处理 %d 个账号）", len(effective))


def _get_aliyun_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "aliyun_time", "05:30") or "05:30")
    return {"minute": minute, "hour": hour}


register_task("aliyun_checkin", run_aliyun_checkin_once, _get_aliyun_trigger_kwargs)
