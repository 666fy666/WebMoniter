"""夸克网盘签到任务

参考 only_for_happly/kuake.py：
- 使用 COOKIE_QUARK 中的 Cookie 列表为多个夸克账号执行每日签到，领取空间。

本任务改造点：
- 从 config.yml 的 kuake 节点读取配置（单 cookie + 多 cookies）
- 接入统一推送与免打扰逻辑
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)


@dataclass
class KuakeConfig:
    enable: bool
    cookie: str
    cookies: list[str]
    time: str
    push_channels: list[str]

    @classmethod
    def from_app_config(cls, config: AppConfig) -> "KuakeConfig":
        cookies = getattr(config, "kuake_cookies", None) or []
        single = (getattr(config, "kuake_cookie", None) or "").strip()
        if not cookies and single:
            cookies = [single]
        return cls(
            enable=getattr(config, "kuake_enable", False),
            cookie=single,
            cookies=[c.strip() for c in cookies if c.strip()],
            time=(getattr(config, "kuake_time", None) or "02:00").strip() or "02:00",
            push_channels=getattr(config, "kuake_push_channels", None) or [],
        )

    def validate(self) -> bool:
        if not self.enable:
            logger.debug("夸克签到未启用，跳过执行")
            return False
        if not self.cookies:
            logger.error("夸克签到配置不完整，缺少 cookie 或 cookies")
            return False
        return True


def _do_sign_for_cookie(cookie: str) -> str:
    """对单个 Cookie 执行签到逻辑，返回一行描述文本。"""
    url_info = "https://pan.quark.cn/account/info"
    url_growth_info = "https://drive-m.quark.cn/1/clouddrive/capacity/growth/info"
    url_sign = "https://drive-m.quark.cn/1/clouddrive/capacity/growth/sign"

    session = requests.Session()
    headers = {
        "content-type": "application/json",
        "cookie": cookie,
    }
    try:
        # 验证账号
        r_info = session.get(url_info, headers=headers, params={"fr": "pc", "platform": "pc"}, timeout=15)
        info = r_info.json()
        if not info.get("data"):
            return "❌ 登录失败，Cookie 可能已失效"
        nickname = info["data"].get("nickname", "")

        # 查询成长信息
        r_growth = session.get(
            url_growth_info,
            headers=headers,
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
            timeout=15,
        )
        growth = r_growth.json().get("data") or {}
        cap_sign = growth.get("cap_sign") or {}
        if cap_sign.get("sign_daily"):
            reward_mb = int((cap_sign.get("sign_daily_reward", 0) or 0) / 1024 / 1024)
            progress = f"{cap_sign.get('sign_progress', 0)}/{cap_sign.get('sign_target', 0)}"
            return f"🙍 账号 {nickname}：今日已签到 +{reward_mb}MB，连签进度 {progress}"

        # 执行签到
        r_sign = session.post(
            url_sign,
            json={"sign_cyclic": True},
            headers=headers,
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
            timeout=15,
        )
        sign_data = r_sign.json().get("data") or {}
        reward_mb = int((sign_data.get("sign_daily_reward", 0) or 0) / 1024 / 1024)
        progress = f"{(cap_sign.get('sign_progress', 0) or 0) + 1}/{cap_sign.get('sign_target', 0) or 0}"
        return f"🙍 账号 {nickname}：签到成功 +{reward_mb}MB，连签进度 {progress}"
    except Exception as exc:  # pragma: no cover - 防御性
        logger.warning("夸克签到：账号处理异常：%s", exc)
        return f"❌ 夸克签到异常：{exc}"


async def run_kuake_checkin_once() -> None:
    """执行一次夸克网盘签到任务（多 Cookie）。"""
    app_cfg = get_config(reload=True)
    cfg = KuakeConfig.from_app_config(app_cfg)
    if not cfg.validate():
        return

    lines: list[str] = []
    for idx, cookie in enumerate(cfg.cookies, start=1):
        logger.info("夸克签到：开始处理第 %d 个 Cookie", idx)
        msg = await asyncio.to_thread(_do_sign_for_cookie, cookie)
        lines.append(msg)

    if not lines:
        return

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        push: UnifiedPushManager | None = await build_push_manager(
            app_cfg.push_channel_list,
            session,
            logger,
            init_fail_prefix="夸克签到：",
            channel_names=cfg.push_channels or None,
        )
        if push and not is_in_quiet_hours(app_cfg):
            try:
                await push.send_news(
                    title="夸克网盘签到结果",
                    description="\n".join(lines),
                    to_url="https://pan.quark.cn/",
                    picurl="",
                    btntxt="打开夸克网盘",
                )
            except Exception as exc:  # pragma: no cover
                logger.error("夸克签到：推送失败：%s", exc, exc_info=True)
            finally:
                await push.close()


def _get_kuake_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "kuake_time", "02:00") or "02:00")
    return {"minute": minute, "hour": hour}


register_task("kuake_checkin", run_kuake_checkin_once, _get_kuake_trigger_kwargs)

