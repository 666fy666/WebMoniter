"""科技玩家网站签到任务

参考 only_for_happly/kjwj.py：
- 使用用户名+密码登录 https://www.kejiwanjia.net
- 调用签到接口获取今日积分

本任务改造点：
- 多账号配置从 config.yml 的 kjwj.accounts 读取
- 接入统一推送与免打扰逻辑
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import requests

from src.jobs.registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager
from src.settings.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time

logger = logging.getLogger(__name__)


@dataclass
class KjwjAccount:
    username: str
    password: str


@dataclass
class KjwjConfig:
    enable: bool
    accounts: list[KjwjAccount]
    time: str
    push_channels: list[str]

    @classmethod
    def from_app_config(cls, config: AppConfig) -> KjwjConfig:
        raw = getattr(config, "kjwj_accounts", None) or []
        accounts: list[KjwjAccount] = []
        for a in raw:
            if not isinstance(a, dict):
                continue
            u = str(a.get("username", "")).strip()
            p = str(a.get("password", "")).strip()
            if u and p:
                accounts.append(KjwjAccount(username=u, password=p))
        return cls(
            enable=getattr(config, "kjwj_enable", False),
            accounts=accounts,
            time=(getattr(config, "kjwj_time", None) or "07:30").strip() or "07:30",
            push_channels=getattr(config, "kjwj_push_channels", None) or [],
        )

    def validate(self) -> bool:
        if not self.enable:
            logger.debug("科技玩家签到未启用，跳过执行")
            return False
        if not self.accounts:
            logger.error("科技玩家签到配置不完整，缺少 accounts")
            return False
        return True


def _sign_for_account(username: str, password: str) -> str:
    """为单个账号执行科技玩家签到逻辑，返回描述文本。"""
    url_token = "https://www.kejiwanjia.net/wp-json/jwt-auth/v1/token"
    headers = {
        "user-agent": (
            "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
        ),
        "origin": "https://www.kejiwanjia.net",
        "referer": "https://www.kejiwanjia.net/",
    }
    data = {"username": username, "password": password}

    try:
        html = requests.post(url=url_token, headers=headers, data=data, timeout=20)
        result = html.json()
        if "token" not in result:
            return f"❌ 账号 {username} 登录失败：{result}"
        name = result.get("name", username)
        token = result["token"]

        check_url = "https://www.kejiwanjia.net/wp-json/b2/v1/getUserMission"
        sign_url = "https://www.kejiwanjia.net/wp-json/b2/v1/userMission"
        sign_headers = {
            "Host": "www.kejiwanjia.net",
            "Connection": "keep-alive",
            "Accept": "application/json, text/plain, */*",
            "authorization": "Bearer " + token,
            "cookie": f"b2_token={token};",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": headers["user-agent"],
        }

        html_1 = requests.post(url=check_url, headers=sign_headers, timeout=20)
        info_1 = html_1.json()
        credit = info_1.get("mission", {}).get("credit", 0)
        if credit == 0:
            # 未签到，尝试签到
            html_2 = requests.post(url=sign_url, headers=sign_headers, timeout=20)
            info_2 = html_2.json()
            return f"🙍 账号 {name}：签到成功，获得 {info_2} 积分"
        return f"🙍 账号 {name}：今日已签到，获得 {credit} 积分"
    except Exception as exc:  # pragma: no cover
        logger.warning("科技玩家签到：账号 %s 异常：%s", username, exc)
        return f"❌ 账号 {username} 签到异常：{exc}"


async def run_kjwj_checkin_once() -> None:
    """执行一次科技玩家签到任务（多账号）。"""
    app_cfg = get_config(reload=True)
    cfg = KjwjConfig.from_app_config(app_cfg)
    if not cfg.validate():
        return

    lines: list[str] = []
    for idx, acc in enumerate(cfg.accounts, start=1):
        logger.info("科技玩家签到：开始处理第 %d 个账号（%s）", idx, acc.username)
        msg = await asyncio.to_thread(_sign_for_account, acc.username, acc.password)
        lines.append(msg)

    if not lines:
        return

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        push: UnifiedPushManager | None = await build_push_manager(
            app_cfg.push_channel_list,
            session,
            logger,
            init_fail_prefix="科技玩家签到：",
            channel_names=cfg.push_channels or None,
        )
        if push and not is_in_quiet_hours(app_cfg):
            try:
                await push.send_news(
                    title="科技玩家签到结果",
                    description="\n".join(lines),
                    to_url="https://www.kejiwanjia.net/",
                    picurl="",
                    btntxt="打开科技玩家",
                )
            except Exception as exc:  # pragma: no cover
                logger.error("科技玩家签到：推送失败：%s", exc, exc_info=True)
            finally:
                await push.close()


def _get_kjwj_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "kjwj_time", "07:30") or "07:30")
    return {"minute": minute, "hour": hour}


register_task(
    "kjwj_checkin",
    run_kjwj_checkin_once,
    _get_kjwj_trigger_kwargs,
    description="科技玩家签到",
)
