"""小米社区签到与成长值任务模块。参考 only_for_happly：账号+密码登录后签到、点赞、拔萝卜等。需 pycryptodome，有封号风险。"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import logging
import random
import re
import string
import time

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)

try:
    from Crypto.Cipher import AES, PKCS1_v1_5
    from Crypto.PublicKey import RSA
    from Crypto.Util.Padding import pad
except ImportError:
    AES = None  # type: ignore[assignment]
    PKCS1_v1_5 = None
    RSA = None
    pad = None

MIUI_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArxfNLkuAQ/BYHzkzVwtu
g+0abmYRBVCEScSzGxJIOsfxVzcuqaKO87H2o2wBcacD3bRHhMjTkhSEqxPjQ/FE
XuJ1cdbmr3+b3EQR6wf/cYcMx2468/QyVoQ7BADLSPecQhtgGOllkC+cLYN6Md34
Uii6U+VJf0p0q/saxUTZvhR2ka9fqJ4+6C6cOghIecjMYQNHIaNW+eSKunfFsXVU
+QfMD0q2EM9wo20aLnos24yDzRjh9HJc6xfr37jRlv1/boG/EABMG9FnTm35xWrV
R0nw3cpYF7GZg13QicS/ZwEsSd4HyboAruMxJBPvK3Jdr4ZS23bpN0cavWOJsBqZ
VwIDAQAB
-----END PUBLIC KEY-----"""


def _rand_str(length: int, chars: str = None) -> str:
    chars = chars or (string.ascii_letters + string.digits + "!@#$%^&*()-=_+~`{}[]|:<>?/.")
    return "".join(random.choice(chars) for _ in range(length))


def _aes_encrypt(key: str, data: str) -> str:
    if AES is None or pad is None:
        raise RuntimeError("小米社区需要 pycryptodome")
    iv = b"0102030405060708"
    cipher = AES.new(key.encode(), AES.MODE_CBC, iv)
    padded = pad(data.encode(), AES.block_size, style="pkcs7")
    return base64.b64encode(cipher.encrypt(padded)).decode()


def _rsa_encrypt_pem(key_pem: str, data: str) -> str:
    if RSA is None or PKCS1_v1_5 is None:
        raise RuntimeError("小米社区需要 pycryptodome")
    pub = RSA.import_key(key_pem)
    cipher = PKCS1_v1_5.new(pub)
    enc = cipher.encrypt(base64.b64encode(data.encode()))
    return base64.b64encode(enc).decode()


def _phone_login(account: str, password: str) -> dict:
    h = hashlib.md5(password.encode()).hexdigest().upper()
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; M2007J17C Build/SKQ1.211006.001) APP/xiaomi.vipaccount APPV/220301 MK/UmVkbWkgTm90ZSA5IFBybw== PassportSDK/3.7.8 passport-ui/3.7.8",
        "Cookie": "deviceId=X0jMu7b0w-jcne-S; pass_o=2d25bb648d023d7f; sdkVersion=accountsdk-2020.01.09",
        "Host": "account.xiaomi.com",
    })
    data = {
        "cc": "+86",
        "qs": "%3F_json%3Dtrue%26sid%3Dmiui_vip%26_locale%3Dzh_CN",
        "callback": "https://api.vip.miui.com/sts",
        "_json": "true",
        "user": account,
        "hash": h,
        "sid": "miui_vip",
        "_sign": "ZJxpm3Q5cu0qDOMkKdWYRPeCwps%3D",
        "_locale": "zh_CN",
    }
    r = session.post("https://account.xiaomi.com/pass/serviceLoginAuth2", data=data, timeout=15)
    r.raise_for_status()
    text = r.text.replace("&&&START&&&", "")
    auth = json.loads(text)
    ssecurity = auth.get("ssecurity")
    nonce = auth.get("nonce")
    if not ssecurity or nonce is None:
        return {}
    s1 = hashlib.sha1(f"nonce={nonce}&{ssecurity}".encode()).hexdigest()
    client_sign = base64.encodebytes(binascii.a2b_hex(s1.encode())).decode().strip()
    nurl = auth.get("location", "") + "&_userIdNeedEncrypt=true&clientSign=" + client_sign
    session.get(nurl, timeout=15)
    return requests.utils.dict_from_cookiejar(session.cookies)


def _get_miui_token() -> str:
    if RSA is None or AES is None or PKCS1_v1_5 is None or pad is None:
        raise RuntimeError("小米社区需要 pycryptodome")
    key = _rand_str(16)
    ts = round(time.time() * 1000)
    uid = _rand_str(27)
    t, r = round(time.time()), round(time.time())
    payload = f'{{"type":0,"startTs":{ts},"endTs":{ts},"env":{{"p19":5,"p22":5}},"action":{{}},"force":false,"talkBack":false,"uid":"{uid}","nonce":{{"t":{t},"r":{r}}},"version":"2.0","scene":"GROW_UP_CHECKIN"}}'
    s = _rsa_encrypt_pem(MIUI_PUBLIC_KEY, key)
    d = _aes_encrypt(key, payload)
    r = requests.post(
        "https://verify.sec.xiaomi.com/captcha/v2/data?k=3dc42a135a8d45118034d1ab68213073&locale=zh_CN",
        data={"s": s, "d": d, "a": "GROW_UP_CHECKIN"},
        timeout=15,
    )
    if r.status_code != 200:
        return ""
    j = r.json()
    if j.get("msg") == "参数错误":
        return ""
    return (j.get("data") or {}).get("token", "")


def _run_miui_sync(account: str, password: str) -> tuple[bool, str]:
    try:
        if RSA is None:
            return False, "未安装 pycryptodome，请执行: uv add pycryptodome"
        cookies = _phone_login(account, password)
        if not cookies:
            return False, "登录失败，请检查账号密码或验证码"
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        miui_vip_ph = "".join(re.findall(r"miui_vip_ph=(.*?);", cookie_str, re.S))
        if not miui_vip_ph:
            return False, "未获取到 miui_vip_ph"
        token = _get_miui_token()
        if not token:
            return False, "获取签到 token 失败"
        boundary = "WebKitFormBoundary" + _rand_str(16, string.ascii_letters + string.digits)
        headers = {
            "Host": "api.vip.miui.com",
            "Accept": "application/json",
            "Cookie": cookie_str,
            "Content-Type": f"multipart/form-data; boundary=----{boundary}",
            "Origin": "https://web.vip.miui.com",
            "Referer": "https://web.vip.miui.com/",
        }
        params = {"ref": "vipAccountShortcut", "pathname": "/mio/checkIn", "version": "dev.231026", "miui_vip_ph": miui_vip_ph}
        body = f'------{boundary}\r\nContent-Disposition: form-data; name="miui_vip_ph"\r\n\r\n{miui_vip_ph}\r\n------{boundary}\r\nContent-Disposition: form-data; name="token"\r\n\r\n{token}\r\n------{boundary}--\r\n'
        r = requests.post(
            "https://api.vip.miui.com/mtop/planet/vip/user/checkinV2",
            headers=headers,
            params=params,
            data=body,
            timeout=15,
        )
        r.raise_for_status()
        j = r.json()
        if j.get("status") == 200:
            msg = "签到成功，获得成长值+" + str(j.get("entity", ""))
        elif j.get("status") == 401:
            return False, "Cookie 失效"
        else:
            return False, j.get("message", "签到失败")
        # 拔萝卜
        try:
            r2 = requests.post("https://api.vip.miui.com/api/carrot/pull", headers=headers, params=params, timeout=15)
            if r2.status_code == 200:
                j2 = r2.json()
                if j2.get("code") == 200:
                    msg += "\n拔萝卜: " + str((j2.get("entity") or {}).get("message", ""))
        except Exception:
            pass
        return True, msg
    except requests.RequestException as e:
        logger.warning("小米社区签到：请求失败 %s", e)
        return False, str(e)
    except Exception as e:
        logger.warning("小米社区签到：异常 %s", e)
        return False, str(e)


async def run_miui_checkin_once() -> None:
    from dataclasses import dataclass

    @dataclass
    class MiuiConfig:
        enable: bool
        account: str
        password: str
        accounts: list[dict]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> "MiuiConfig":
            accounts: list[dict] = getattr(config, "miui_accounts", None) or []
            single_a = (getattr(config, "miui_account", None) or "").strip()
            single_p = (getattr(config, "miui_password", None) or "").strip()
            if not accounts and (single_a or single_p):
                accounts = [{"account": single_a, "password": single_p}]
            push: list[str] = getattr(config, "miui_push_channels", None) or []
            return cls(
                enable=getattr(config, "miui_enable", False),
                account=single_a,
                password=single_p,
                accounts=accounts,
                time=(getattr(config, "miui_time", None) or "08:30").strip() or "08:30",
                push_channels=push,
            )

        def validate(self) -> bool:
            if not self.enable:
                return False
            effective = self.accounts or ([{"account": self.account, "password": self.password}] if (self.account or self.password) else [])
            if not effective or not any((a.get("account") or "").strip() and (a.get("password") or "").strip() for a in effective):
                logger.error("小米社区签到配置不完整")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = MiuiConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [{"account": (a.get("account") or "").strip(), "password": (a.get("password") or "").strip()} for a in (cfg.accounts or []) if (a.get("account") or "").strip() and (a.get("password") or "").strip()]
    if not effective and cfg.account and cfg.password:
        effective = [{"account": cfg.account, "password": cfg.password}]
    logger.info("小米社区签到：开始执行（共 %d 个账号）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list, session, logger,
            init_fail_prefix="小米社区签到：", channel_names=cfg.push_channels or None,
        )
        for idx, acc in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(_run_miui_sync, acc["account"], acc["password"])
            except Exception as e:
                logger.error("小米社区签到：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)
            if push_manager and not is_in_quiet_hours(app_config):
                masked = acc["account"][:3] + "****" + acc["account"][-4:] if len(acc["account"]) >= 7 else "***"
                title = "小米社区签到成功" if ok else "小米社区签到失败"
                try:
                    await push_manager.send_news(title=title, description=f"账号 {masked}\n{msg}", to_url="https://web.vip.miui.com", picurl="", btntxt="打开")
                except Exception as exc:
                    logger.error("小米社区签到：推送失败 %s", exc)
        if push_manager:
            await push_manager.close()
    logger.info("小米社区签到：结束（共 %d 个账号）", len(effective))


def _get_miui_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "miui_time", "08:30") or "08:30")
    return {"minute": minute, "hour": hour}


register_task("miui_checkin", run_miui_checkin_once, _get_miui_trigger_kwargs)
