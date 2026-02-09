"""Freenom 免费域名续期任务

参考 only_for_happly/freenom.py：
- 使用邮箱 + 密码登录 Freenom
- 获取即将到期的免费域名列表（<14 天）
- 尝试将其续期 12 个月

本任务改造点：
- 改为从 config.yml 中读取多账号配置 freenom.accounts
- 接入统一推送与免打扰逻辑
- 使用 asyncio.to_thread 运行同步 requests 逻辑
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)

LOGIN_URL = "https://my.freenom.com/dologin.php"
DOMAIN_STATUS_URL = "https://my.freenom.com/domains.php?a=renewals"
RENEW_DOMAIN_URL = "https://my.freenom.com/domains.php?submitrenewals=true"

TOKEN_PTN = re.compile(r'name="token" value="(.*?)"', re.I)
DOMAIN_INFO_PTN = re.compile(r" (.*?) [^<]+ [^<]+.*? ", re.I)
LOGIN_STATUS_PTN = re.compile(r" Logout ", re.I)


@dataclass
class FreenomAccount:
    email: str
    password: str


@dataclass
class FreenomTaskConfig:
    enable: bool
    accounts: list[FreenomAccount]
    time: str
    push_channels: list[str]

    @classmethod
    def from_app_config(cls, config: AppConfig) -> "FreenomTaskConfig":
        raw_accounts = getattr(config, "freenom_accounts", None) or []
        accounts: list[FreenomAccount] = []
        for a in raw_accounts:
            if not isinstance(a, dict):
                continue
            email = str(a.get("email", "")).strip()
            password = str(a.get("password", "")).strip()
            if email and password:
                accounts.append(FreenomAccount(email=email, password=password))
        return cls(
            enable=getattr(config, "freenom_enable", False),
            accounts=accounts,
            time=(getattr(config, "freenom_time", None) or "07:33").strip() or "07:33",
            push_channels=getattr(config, "freenom_push_channels", None) or [],
        )

    def validate(self) -> bool:
        if not self.enable:
            logger.debug("Freenom 续期未启用，跳过执行")
            return False
        if not self.accounts:
            logger.error("Freenom 续期配置不完整：freenom.accounts 为空")
            return False
        return True


def _renew_for_account(email: str, password: str) -> dict[str, Any]:
    """对单个 Freenom 账户执行续期逻辑（同步，供 asyncio.to_thread 调用）。"""
    sess = requests.Session()
    sess.headers.update(
        {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "Chrome/103.0.5060.134 Safari/537.36"
            ),
            "content-type": "application/x-www-form-urlencoded",
            "referer": "https://my.freenom.com/clientarea.php",
        }
    )

    domains_list: list[str] = []
    renew_success: list[str] = []
    renew_failed: list[str] = []

    try:
        r = sess.post(LOGIN_URL, data={"username": email, "password": password}, timeout=20)
        if r.status_code != 200:
            return {
                "ok": False,
                "message": "无法登录（HTTP 状态码异常），请检查网络或账号密码",
                "detail": "",
            }
        sess.headers.update({"referer": "https://my.freenom.com/clientarea.php"})
        r = sess.get(DOMAIN_STATUS_URL, timeout=20)
    except requests.RequestException as exc:
        return {"ok": False, "message": f"网络请求失败：{exc}", "detail": ""}

    if not re.search(LOGIN_STATUS_PTN, r.text):
        return {"ok": False, "message": "登录失败，请检查邮箱/密码是否正确", "detail": ""}

    page_token = re.search(TOKEN_PTN, r.text)
    if not page_token:
        return {"ok": False, "message": "未能在页面中找到 token，续期失败", "detail": ""}
    token = page_token.group(1)

    domains = re.findall(DOMAIN_INFO_PTN, r.text)
    # domains 的结构较为依赖页面格式，这里保持与原脚本一致
    for domain, days, renewal_id in domains:
        try:
            day_int = int(days)
        except Exception:
            continue
        domains_list.append(f"域名: {domain} 还有 {day_int} 天到期")
        if day_int < 14:
            time.sleep(6)
            sess.headers.update(
                {
                    "referer": f"https://my.freenom.com/domains.php?a=renewdomain&domain={renewal_id}",
                    "content-type": "application/x-www-form-urlencoded",
                }
            )
            try:
                r2 = sess.post(
                    RENEW_DOMAIN_URL,
                    data={
                        "token": token,
                        "renewalid": renewal_id,
                        f"renewalperiod[{renewal_id}]": "12M",
                        "paymentmethod": "credit",
                    },
                    timeout=20,
                )
            except requests.RequestException:
                renew_failed.append(domain)
                continue
            if "Order Confirmation" in r2.text:
                renew_success.append(domain)
            else:
                renew_failed.append(domain)

    summary_lines: list[str] = []
    if domains_list:
        summary_lines.append("域名状态：")
        summary_lines.extend(domains_list)
    if renew_success:
        summary_lines.append("")
        summary_lines.append("续期成功：")
        summary_lines.extend(renew_success)
    if renew_failed:
        summary_lines.append("")
        summary_lines.append("续期失败：")
        summary_lines.extend(renew_failed)

    ok = bool(renew_success) and not renew_failed
    return {
        "ok": ok,
        "message": "续期完成" if summary_lines else "无即将到期域名或续期结果为空",
        "detail": "\n".join(summary_lines),
    }


async def run_freenom_checkin_once() -> None:
    """执行一次 Freenom 续期任务（多账号）。"""
    app_cfg = get_config(reload=True)
    cfg = FreenomTaskConfig.from_app_config(app_cfg)
    if not cfg.validate():
        return

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        push: UnifiedPushManager | None = await build_push_manager(
            app_cfg.push_channel_list,
            session,
            logger,
            init_fail_prefix="Freenom 续期：",
            channel_names=cfg.push_channels or None,
        )

        all_lines: list[str] = []
        for idx, acc in enumerate(cfg.accounts, start=1):
            masked = acc.email
            logger.info("Freenom 续期：开始处理第 %d 个账号（%s）", idx, masked)
            try:
                result = await asyncio.to_thread(
                    _renew_for_account, acc.email, acc.password
                )
            except Exception as exc:  # pragma: no cover - 防御性
                logger.exception("Freenom 续期：账号 %s 处理异常：%s", masked, exc)
                all_lines.append(f"账号 {masked}：执行异常：{exc}")
                continue

            ok = bool(result.get("ok"))
            msg = str(result.get("message") or "")
            detail = str(result.get("detail") or "")
            prefix = f"[{'✅' if ok else '❌'}] 账号 {masked}：{msg}"
            all_lines.append(prefix)
            if detail:
                all_lines.append(detail)
            all_lines.append("")

        if push and all_lines and not is_in_quiet_hours(app_cfg):
            try:
                await push.send_news(
                    title="Freenom 域名续期结果",
                    description="\n".join(all_lines).strip(),
                    to_url="https://my.freenom.com/domains.php?a=renewals",
                    picurl="",
                    btntxt="查看 Freenom 域名",
                )
            except Exception as exc:  # pragma: no cover - 推送错误不影响主流程
                logger.error("Freenom 续期：发送推送失败：%s", exc, exc_info=True)
            finally:
                await push.close()

        logger.info("Freenom 续期任务执行完成")


def _get_freenom_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "freenom_time", "07:33") or "07:33")
    return {"minute": minute, "hour": hour}


register_task("freenom_checkin", run_freenom_checkin_once, _get_freenom_trigger_kwargs)

