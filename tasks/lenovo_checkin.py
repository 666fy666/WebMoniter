"""联想乐豆签到与任务模块。参考 only_for_happly：access_token 调用 ssoCheck 后签到并执行任务列表，支持多 token。依赖 pycryptodome。"""

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

try:
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_v1_5
except ImportError:
    RSA = None  # type: ignore[assignment]
    PKCS1_v1_5 = None  # type: ignore[assignment]

PT = ["cD", "BT", "Uzn", "Po", "Luu", "Yhc", "Cj", "FP", "al", "Tq"]
HT = ["MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJB", "L7qpP6mG6ZHdDKEIdTqQDo/WQ", "6NaWftXwOTHnnbnwUEX2/2jI4qALxRWMliYI80cszh6", "ySbap0KIljDCN", "w0CAwEAAQ=="]


def _get_sign_key() -> str:
    if RSA is None or PKCS1_v1_5 is None:
        raise RuntimeError("联想乐豆需要 pycryptodome，请执行: uv add pycryptodome")
    key_str = ""
    for i, val in enumerate(HT):
        key_str += val + (["A", "b", "C", "D", ""][i] if i < 5 else "")
    try:
        pub = RSA.import_key(f"-----BEGIN PUBLIC KEY-----\n{key_str}\n-----END PUBLIC KEY-----")
        cipher = PKCS1_v1_5.new(pub)
        t = str(random.randint(0, 10**8 - 1)).zfill(8)
        e = "".join(PT[int(c)] for c in t)
        enc = cipher.encrypt(base64.b64encode(f"{t}:{e}".encode()))
        return base64.b64encode(enc).decode()
    except Exception as e:
        logger.warning("联想乐豆 getSignKey 失败: %s", e)
        return ""


def _run_lenovo_sync(access_token: str) -> tuple[bool, str]:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; MI 8 Lite Build/QKQ1.190910.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/80.0.3987.99 Mobile Safari/537.36/lenovoofficialapp/9e4bb0e5bc326fb1_10219183246/newversion/versioncode-1000112/",
            "accesstoken": access_token,
            "signkey": _get_sign_key(),
            "origin": "https://mmembership.lenovo.com.cn",
            "servicetoken": "",
            "tenantid": "25",
            "clientid": "2",
            "x-requested-with": "com.lenovo.club.app",
            "referer": "https://mmembership.lenovo.com.cn/app?pmf_source=P0000005611M0002",
        }
        r = requests.post(
            "https://mmembership.lenovo.com.cn/member-center-api/v2/access/ssoCheck?lenovoId=&unionId=&clientId=2",
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != "0":
            return False, data.get("message", "ssoCheck 失败")
        token = data["data"]["serviceToken"]
        lenovo_id = data["data"]["lenovoId"]
        headers["servicetoken"] = token
        headers["lenovoid"] = lenovo_id
        headers.pop("signkey", None)

        # 签到
        r2 = requests.post(
            f"https://mmembership.lenovo.com.cn/member-hp-task-center/v1/task/checkIn?lenovoId={lenovo_id}&OSType=10011",
            headers=headers,
            timeout=15,
        )
        r2.raise_for_status()
        j2 = r2.json()
        if j2.get("code") != "0":
            return False, j2.get("message", "签到失败")
        msg_parts = ["签到成功"]

        # 任务列表
        r3 = requests.post(
            "https://mmembership.lenovo.com.cn/member-hp-task-center/v1/task/getUserTaskList",
            headers=headers,
            timeout=15,
        )
        if r3.status_code == 200:
            j3 = r3.json()
            if j3.get("code") == "0":
                for task in j3.get("data", []):
                    if task.get("taskState") == 0 and task.get("type") != 13:
                        tid = task.get("taskId")
                        r4 = requests.post(
                            f"https://mmembership.lenovo.com.cn/member-hp-task-center/v1/checkin/selectTaskPrize?taskId={tid}&channelId=1",
                            headers=headers,
                            timeout=15,
                        )
                        if r4.status_code == 200 and r4.json().get("code") == "0":
                            r5 = requests.post(
                                f"https://mmembership.lenovo.com.cn/member-hp-task-center/v1/Task/userFinishTask?taskId={tid}&channelId=1&state=1",
                                headers=headers,
                                timeout=15,
                            )
                            if r5.status_code == 200 and r5.json().get("code") == "0":
                                msg_parts.append(f"任务{tid}完成")
        return True, "\n".join(msg_parts)
    except Exception as e:
        logger.warning("联想乐豆签到：请求失败 %s", e)
        return False, str(e)


async def run_lenovo_checkin_once() -> None:
    from dataclasses import dataclass

    @dataclass
    class LenovoConfig:
        enable: bool
        access_token: str
        access_tokens: list[str]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> "LenovoConfig":
            tokens: list[str] = getattr(config, "lenovo_access_tokens", None) or []
            single = (getattr(config, "lenovo_access_token", None) or "").strip()
            if not tokens and single:
                tokens = [single]
            push: list[str] = getattr(config, "lenovo_push_channels", None) or []
            return cls(
                enable=getattr(config, "lenovo_enable", False),
                access_token=single,
                access_tokens=tokens,
                time=(getattr(config, "lenovo_time", None) or "05:30").strip() or "05:30",
                push_channels=push,
            )

        def validate(self) -> bool:
            if not self.enable:
                return False
            effective = self.access_tokens or ([self.access_token] if self.access_token else [])
            if not effective or not any(t.strip() for t in effective):
                logger.error("联想乐豆签到配置不完整")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = LenovoConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [t.strip() for t in cfg.access_tokens if t.strip()]
    if not effective and cfg.access_token:
        effective = [cfg.access_token.strip()]
    logger.info("联想乐豆签到：开始执行（共 %d 个账号）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list, session, logger,
            init_fail_prefix="联想乐豆签到：", channel_names=cfg.push_channels or None,
        )
        for idx, token in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(_run_lenovo_sync, token)
            except Exception as e:
                logger.error("联想乐豆签到：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)
            if push_manager and not is_in_quiet_hours(app_config):
                masked = token[:8] + "***" if len(token) > 8 else "***"
                title = "联想乐豆签到成功" if ok else "联想乐豆签到失败"
                try:
                    await push_manager.send_news(title=title, description=f"账号 {masked}\n{msg}", to_url="https://mmembership.lenovo.com.cn", picurl="", btntxt="打开")
                except Exception as exc:
                    logger.error("联想乐豆签到：推送失败 %s", exc)
        if push_manager:
            await push_manager.close()
    logger.info("联想乐豆签到：结束（共 %d 个账号）", len(effective))


def _get_lenovo_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "lenovo_time", "05:30") or "05:30")
    return {"minute": minute, "hour": hour}


register_task("lenovo_checkin", run_lenovo_checkin_once, _get_lenovo_trigger_kwargs)
