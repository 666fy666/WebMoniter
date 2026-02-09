"""天翼云盘签到任务模块

参考 only_for_happly 天翼云盘签到逻辑：
- 使用手机号+密码登录（RSA 加密），签到并抽奖
- 支持多账号（accounts）
- 依赖 rsa 库
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import time

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)

try:
    import rsa
except ImportError:
    rsa = None  # type: ignore[assignment]

B64MAP = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
BI_RM = list("0123456789abcdefghijklmnopqrstuvwxyz")


def _b64tohex(a: str) -> str:
    d = ""
    e = 0
    c = 0
    for i in range(len(a)):
        if list(a)[i] != "=":
            v = B64MAP.index(list(a)[i])
            if e == 0:
                e = 1
                d += BI_RM[v >> 2]
                c = 3 & v
            elif e == 1:
                e = 2
                d += BI_RM[c << 2 | v >> 4]
                c = 15 & v
            elif e == 2:
                e = 3
                d += BI_RM[c]
                d += BI_RM[v >> 2]
                c = 3 & v
            else:
                e = 0
                d += BI_RM[c << 2 | v >> 4]
                d += BI_RM[15 & v]
    if e == 1:
        d += BI_RM[c << 2]
    return d


def _rsa_encode(j_rsakey: str, string: str) -> str:
    if rsa is None:
        raise RuntimeError("天翼云盘签到需要 rsa 库，请安装: uv add rsa")
    rsa_key = f"-----BEGIN PUBLIC KEY-----\n{j_rsakey}\n-----END PUBLIC KEY-----"
    pubkey = rsa.PublicKey.load_pkcs1_openssl_pem(rsa_key.encode())
    result = _b64tohex((base64.b64encode(rsa.encrypt(string.encode(), pubkey))).decode())
    return result


def _run_tyyun_sync(username: str, password: str) -> tuple[bool, str]:
    """
    同步执行天翼云盘登录、签到与抽奖。

    Returns:
        (success, message)
    """
    if rsa is None:
        return False, "未安装 rsa 库，请执行: uv add rsa"

    session = requests.Session()
    try:
        url_token = "https://m.cloud.189.cn/udb/udb_login.jsp?pageId=1&pageKey=default&clientType=wap&redirectURL=https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html"
        r = session.get(url_token, timeout=15)
        r.raise_for_status()
        match = re.search(r"https?://[^\s'\"]+", r.text)
        if not match:
            return False, "未找到登录跳转 URL"
        url = match.group()
        r = session.get(url, timeout=15)
        r.raise_for_status()
        match = re.search(r']*href="([^"]+)"', r.text)
        if not match:
            return False, "未找到登录页 href"
        href = match.group(1)
        r = session.get(href, timeout=15)
        r.raise_for_status()
        text = r.text
        captcha_token = re.findall(r"captchaToken' value='(.+?)'", text)
        lt = re.findall(r'lt = "(.+?)"', text)
        return_url = re.findall(r"returnUrl= '(.+?)'", text)
        param_id = re.findall(r'paramId = "(.+?)"', text)
        j_rsakey = re.findall(r'j_rsaKey" value="(\S+)"', text, re.M)
        if not all([captcha_token, lt, return_url, param_id, j_rsakey]):
            return False, "登录页解析失败"
        session.headers.update({"lt": lt[0]})
        uname_enc = _rsa_encode(j_rsakey[0], username)
        pwd_enc = _rsa_encode(j_rsakey[0], password)
        login_url = "https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/76.0",
            "Referer": "https://open.e.189.cn/",
        }
        data = {
            "appKey": "cloud",
            "accountType": "01",
            "userName": f"{{RSA}}{uname_enc}",
            "password": f"{{RSA}}{pwd_enc}",
            "validateCode": "",
            "captchaToken": captcha_token[0],
            "returnUrl": return_url[0],
            "mailSuffix": "@189.cn",
            "paramId": param_id[0],
        }
        r = session.post(login_url, data=data, headers=headers, timeout=15)
        r.raise_for_status()
        j = r.json()
        if j.get("result") != 0:
            return False, j.get("msg", "登录失败")
        to_url = j.get("toUrl", "")
        if to_url:
            session.get(to_url, timeout=15)
        rand = str(round(time.time() * 1000))
        sign_url = f"https://api.cloud.189.cn/mkt/userSign.action?rand={rand}&clientType=TELEANDROID&version=8.6.3&model=SM-G930K"
        headers_m = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 5.1.1; SM-G930K Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/74.0.3729.136 Mobile Safari/537.36 Ecloud/8.6.3 Android/22 clientId/355325117317828 clientModel/SM-G930K imsi/460071114317824 clientChannelId/qq proVersion/1.0.6",
            "Referer": "https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp?albumBackupOpened=1",
            "Host": "m.cloud.189.cn",
        }
        resp = session.get(sign_url, headers=headers_m, timeout=15)
        resp.raise_for_status()
        j = resp.json()
        netdisk_bonus = j.get("netdiskBonus", "?")
        is_sign = j.get("isSign", "true") == "false"
        res1 = (
            f"未签到，签到获得{netdisk_bonus}M空间"
            if is_sign
            else f"已经签到过了，签到获得{netdisk_bonus}M空间"
        )
        parts = [res1]
        for task_id, act_id in [
            ("TASK_SIGNIN", "ACT_SIGNIN"),
            ("TASK_SIGNIN_PHOTOS", "ACT_SIGNIN"),
            ("TASK_2022_FLDFS_KJ", "ACT_SIGNIN"),
        ]:
            draw_url = f"https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action?taskId={task_id}&activityId={act_id}"
            r2 = session.get(draw_url, headers=headers_m, timeout=15)
            if r2.status_code == 200 and "errorCode" not in r2.text:
                try:
                    desc = r2.json().get("description", "")
                    if desc:
                        parts.append(f"抽奖获得{desc}")
                except Exception:
                    pass
        return True, " ".join(parts)
    except requests.RequestException as e:
        logger.warning("天翼云盘签到：请求失败 %s", e)
        return False, f"请求失败: {e}"
    except Exception as e:
        logger.warning("天翼云盘签到：异常 %s", e)
        return False, str(e)


async def run_tyyun_checkin_once() -> None:
    """执行一次天翼云盘签到（支持多账号），并接入统一推送。"""
    from dataclasses import dataclass

    @dataclass
    class TyyunConfig:
        enable: bool
        username: str
        password: str
        accounts: list[dict]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> TyyunConfig:
            accounts: list[dict] = getattr(config, "tyyun_accounts", None) or []
            single_u = (getattr(config, "tyyun_username", None) or "").strip()
            single_p = (getattr(config, "tyyun_password", None) or "").strip()
            if not accounts and (single_u or single_p):
                accounts = [{"username": single_u, "password": single_p}]
            push: list[str] = getattr(config, "tyyun_push_channels", None) or []
            return cls(
                enable=getattr(config, "tyyun_enable", False),
                username=single_u,
                password=single_p,
                accounts=accounts,
                time=(getattr(config, "tyyun_time", None) or "04:30").strip() or "04:30",
                push_channels=push,
            )

        def validate(self) -> bool:
            if not self.enable:
                logger.debug("天翼云盘签到未启用，跳过")
                return False
            effective = (
                self.accounts
                if self.accounts
                else (
                    [{"username": self.username, "password": self.password}]
                    if (self.username or self.password)
                    else []
                )
            )
            if not effective or not any(
                (a.get("username") or "").strip() and (a.get("password") or "").strip()
                for a in effective
            ):
                logger.error("天翼云盘签到配置不完整，缺少账号或 accounts")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = TyyunConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [
        {
            "username": (a.get("username") or "").strip(),
            "password": (a.get("password") or "").strip(),
        }
        for a in (cfg.accounts or [])
        if (a.get("username") or "").strip() and (a.get("password") or "").strip()
    ]
    if not effective and cfg.username and cfg.password:
        effective = [{"username": cfg.username, "password": cfg.password}]
    logger.info("天翼云盘签到：开始执行（共 %d 个账号）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="天翼云盘签到：",
            channel_names=cfg.push_channels if cfg.push_channels else None,
        )

        for idx, acc in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(_run_tyyun_sync, acc["username"], acc["password"])
            except Exception as e:
                logger.error("天翼云盘签到：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)

            if push_manager and not is_in_quiet_hours(app_config):
                masked_u = (
                    acc["username"][:3] + "****" + acc["username"][-4:]
                    if len(acc["username"]) >= 7
                    else "***"
                )
                title = "天翼云盘签到成功" if ok else "天翼云盘签到失败"
                body = f"{'✅' if ok else '❌'} 账号: {masked_u}\n{msg}\n\n执行时间配置: {cfg.time}"
                try:
                    await push_manager.send_news(
                        title=title,
                        description=body,
                        to_url="https://cloud.189.cn",
                        picurl="",
                        btntxt="打开云盘",
                    )
                except Exception as exc:
                    logger.error("天翼云盘签到：推送失败 %s", exc)

        if push_manager:
            await push_manager.close()

    logger.info("天翼云盘签到：结束（共处理 %d 个账号）", len(effective))


def _get_tyyun_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "tyyun_time", "04:30") or "04:30")
    return {"minute": minute, "hour": hour}


register_task("tyyun_checkin", run_tyyun_checkin_once, _get_tyyun_trigger_kwargs)
