"""iKuuu/SSPanel ikuuu签到任务模块

iKuuu 自动签到脚本：
- 使用配置文件中的登录地址、签到地址、账号、密码等参数
- 支持每天固定时间（默认 08:00）自动签到
- 项目启动时也会执行一次签到
"""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from typing import Any

import aiohttp
from bs4 import BeautifulSoup
from yarl import URL

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)


@dataclass
class CheckinConfig:
    """签到相关配置（可表示单账号或用于多账号时的公共字段）"""

    enable: bool
    login_url: str
    checkin_url: str
    user_page_url: str | None
    email: str
    password: str
    time: str
    accounts: list[dict]  # 多账号列表 [{"email": str, "password": str}, ...]，执行时优先遍历此列表
    push_channels: list[str]  # 推送通道名称列表，为空时使用全部通道

    @classmethod
    def from_app_config(cls, config: AppConfig) -> CheckinConfig:
        # 多账号优先：checkin_accounts 非空时使用，否则用单账号组一条
        if getattr(config, "checkin_accounts", None):
            accounts = [
                {
                    "email": str(a.get("email", "")).strip(),
                    "password": str(a.get("password", "")).strip(),
                }
                for a in config.checkin_accounts
                if isinstance(a, dict)
            ]
        else:
            accounts = [
                {
                    "email": (config.checkin_email or "").strip(),
                    "password": (config.checkin_password or "").strip(),
                }
            ]
        first = accounts[0] if accounts else {"email": "", "password": ""}
        push_channels: list[str] = getattr(config, "checkin_push_channels", None) or []
        return cls(
            enable=config.checkin_enable,
            login_url=config.checkin_login_url.strip(),
            checkin_url=config.checkin_checkin_url.strip(),
            user_page_url=(config.checkin_user_page_url or "").strip() or None,
            email=first.get("email", ""),
            password=first.get("password", ""),
            time=config.checkin_time.strip() or "08:00",
            accounts=accounts,
            push_channels=push_channels,
        )

    def with_account(self, email: str, password: str) -> CheckinConfig:
        """返回仅替换邮箱/密码的副本，用于单账号登录与推送。"""
        return CheckinConfig(
            enable=self.enable,
            login_url=self.login_url,
            checkin_url=self.checkin_url,
            user_page_url=self.user_page_url,
            email=email,
            password=password,
            time=self.time,
            accounts=self.accounts,
            push_channels=self.push_channels,
        )

    def validate(self) -> bool:
        """校验配置是否完整"""
        if not self.enable:
            logger.debug("ikuuu签到未启用，跳过执行")
            return False

        missing_fields: list[str] = []
        if not self.login_url:
            missing_fields.append("checkin.login_url")
        if not self.checkin_url:
            missing_fields.append("checkin.checkin_url")
        if not self.accounts:
            missing_fields.append("checkin.accounts 或 checkin.email/password")
        else:
            valid_accounts = [a for a in self.accounts if a.get("email") and a.get("password")]
            if not valid_accounts:
                missing_fields.append("至少一个账号需包含 checkin.email 与 checkin.password")

        if missing_fields:
            logger.error("ikuuu签到配置不完整，已跳过执行，缺少字段: %s", ", ".join(missing_fields))
            return False

        return True


def _mask_email(email: str) -> str:
    """对邮箱做部分脱敏，用于日志输出"""
    if "@" not in email:
        return email
    name, domain = email.split("@", 1)
    if len(name) <= 3:
        masked_name = name[0] + "***" if name else "***"
    else:
        masked_name = name[:3] + "***"
    return f"{masked_name}@{domain}"


async def _login_and_get_cookie(session: aiohttp.ClientSession, cfg: CheckinConfig) -> str | None:
    """登录站点并获取 Cookie"""
    logger.debug("ikuuu签到：使用账号 %s 登录", _mask_email(cfg.email))

    # 从登录地址中推导出站点根地址，用于设置 Referer / Origin
    try:
        login_url = URL(cfg.login_url)
        base_origin = f"{login_url.scheme}://{login_url.host}"
    except Exception:
        # 如果 URL 解析失败，则回退为配置值
        base_origin = cfg.login_url

    headers: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
        )
    }

    try:
        # 访问登录页，获取 CSRF 等必要信息
        async with session.get(cfg.login_url, headers=headers) as resp:
            text = await resp.text()

        soup = BeautifulSoup(text, "html.parser")
        csrf_token: str | None = None
        csrf_input = soup.find("input", {"name": "_token"})
        if csrf_input:
            csrf_token = csrf_input.get("value")

        login_data: dict[str, str] = {
            "email": cfg.email,
            "passwd": cfg.password,
        }
        if csrf_token:
            login_data["_token"] = csrf_token

        headers.update(
            {
                "Origin": base_origin,
                "Referer": cfg.login_url,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )

        async with session.post(cfg.login_url, data=login_data, headers=headers) as resp:
            status = resp.status
            resp_url = str(resp.url)

            # 优先尝试解析 JSON
            json_data: dict[str, Any] | None = None
            try:
                json_data = await resp.json(content_type=None)
            except Exception:
                json_data = None

        if status == 200:
            # 1. 一些站点登录成功会跳转到 /user 等页面
            # 2. 有些返回 JSON: {"ret": 1, "msg": "..."}
            if "user" in resp_url or (json_data and json_data.get("ret") == 1):
                logger.debug("ikuuu签到：登录成功")
                # 从 session 中提取 Cookie
                cookie_jar = session.cookie_jar
                cookies = cookie_jar.filter_cookies(base_origin)
                cookie_string = "; ".join(f"{k}={v.value}" for k, v in cookies.items())
                return cookie_string

            msg = json_data.get("msg") if json_data else "未知错误"
            logger.error("ikuuu签到：登录失败：%s", msg)
            return None

        logger.error("ikuuu签到：登录请求失败，HTTP 状态码：%s", status)
        return None

    except Exception as exc:  # noqa: BLE001
        logger.error("ikuuu签到：登录过程中发生错误：%s", exc, exc_info=True)
        return None


async def _checkin(session: aiohttp.ClientSession, cfg: CheckinConfig, cookie: str) -> bool:
    """执行签到"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
        ),
        "Origin": cfg.checkin_url.rsplit("/user", 1)[0] if "/user" in cfg.checkin_url else "",
        "Referer": (
            cfg.checkin_url.rsplit("/checkin", 1)[0] if "/checkin" in cfg.checkin_url else ""
        ),
        "Cookie": cookie,
    }

    try:
        async with session.post(cfg.checkin_url, headers=headers) as resp:
            try:
                data: dict[str, Any] = await resp.json(content_type=None)
            except Exception as exc:  # noqa: BLE001
                logger.error("ikuuu签到：解析签到响应失败：%s", exc, exc_info=True)
                return False

        msg = data.get("msg", "")
        if data.get("ret") == 1:
            logger.info("ikuuu签到：✅ 签到成功：%s", msg)
            return True

        if "已经签到" in msg or "已签到" in msg:
            logger.info("ikuuu签到：ℹ️ 今日已签到：%s", msg)
            return True

        logger.error("ikuuu签到：❌ 签到失败：%s", msg)
        return False

    except Exception as exc:  # noqa: BLE001
        logger.error("ikuuu签到：签到请求失败：%s", exc, exc_info=True)
        return False


async def _get_user_traffic(
    session: aiohttp.ClientSession, cfg: CheckinConfig, cookie: str
) -> str | None:
    """获取并输出流量信息（可选），返回用于推送的流量摘要文本，失败或无配置则返回 None。"""
    if not cfg.user_page_url:
        # 用户未配置用户信息页地址，直接跳过
        return None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
        ),
        "Referer": cfg.user_page_url,
        "Cookie": cookie,
    }

    try:
        async with session.get(cfg.user_page_url, headers=headers) as resp:
            text = await resp.text()

        # 部分站点将正文放在 script 的 base64(originBody) 中，需先解码再解析
        html_to_parse = text
        origin_body_match = re.search(
            r'originBody\s*=\s*"([A-Za-z0-9+/=]+)"',
            text,
            re.DOTALL,
        )
        if origin_body_match:
            try:
                decoded = base64.b64decode(origin_body_match.group(1)).decode("utf-8")
                if "card-statistic-2" in decoded or "剩余流量" in decoded:
                    html_to_parse = decoded
            except Exception:  # 解码失败则仍用原始 HTML
                pass

        soup = BeautifulSoup(html_to_parse, "html.parser")

        traffic_cards = soup.find_all("div", class_="card-statistic-2")
        if not traffic_cards:
            logger.debug("ikuuu签到：未找到流量统计信息")
            return None

        lines: list[str] = []
        for card in traffic_cards:
            header = card.find("h4")
            if header and "剩余流量" in header.text:
                body = card.find("div", class_="card-body")
                if body:
                    remaining_traffic = re.sub(r"\s+", " ", body.get_text(strip=True))
                    logger.debug("ikuuu签到：剩余流量 %s", remaining_traffic)
                    lines.append(f"📈 剩余流量：{remaining_traffic}")

                stats = card.find("div", class_="card-stats-title")
                if stats:
                    today_used_text = re.sub(r"\s+", " ", stats.get_text(strip=True))
                    match = re.search(r":\s*(.+)", today_used_text)
                    if match:
                        today_used = match.group(1).strip()
                        logger.debug("ikuuu签到：今日已用 %s", today_used)
                        lines.append(f"📊 今日已用：{today_used}")
                    else:
                        logger.debug("ikuuu签到：今日使用 %s", today_used_text)
                        lines.append(f"📊 今日使用情况：{today_used_text}")

        return "\n".join(lines) if lines else None

    except Exception as exc:  # noqa: BLE001
        logger.error("ikuuu签到：获取流量信息失败：%s", exc, exc_info=True)
        return None


async def run_checkin_once() -> None:
    """执行一次完整的 iKuuu/SSPanel 签到流程（支持多账号：登录 → 签到 → 获取流量信息 → 推送）"""
    app_config = get_config(reload=True)
    cfg = CheckinConfig.from_app_config(app_config)

    if not cfg.validate():
        return

    valid_accounts = [a for a in cfg.accounts if a.get("email") and a.get("password")]
    logger.info("ikuuu签到：开始执行（共 %d 个账号）", len(valid_accounts))

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="ikuuu签到：",
            channel_names=cfg.push_channels if cfg.push_channels else None,
        )
        if push_manager is None:
            logger.warning("ikuuu签到：未配置任何推送通道，将仅在日志中记录结果")

        success_count = 0
        for idx, account in enumerate(valid_accounts):
            cfg_one = cfg.with_account(account["email"], account["password"])
            logger.debug("ikuuu签到：正在处理第 %d/%d 个账号", idx + 1, len(valid_accounts))

            cookie = await _login_and_get_cookie(session, cfg_one)
            if not cookie:
                logger.error("ikuuu签到：❌ 账号 %s 登录失败", _mask_email(cfg_one.email))
                await _send_checkin_push(
                    push_manager,
                    title="ikuuu签到失败：登录失败",
                    msg="登录失败，无法获取 Cookie，请检查账号、密码或站点状态。",
                    success=False,
                    cfg=cfg_one,
                )
                continue

            ok = await _checkin(session, cfg_one, cookie)
            if ok:
                success_count += 1
            traffic_info = await _get_user_traffic(session, cfg_one, cookie)
            title = "ikuuu签到成功" if ok else "ikuuu签到失败"
            msg = "签到接口返回成功或已签到" if ok else "签到接口返回失败，请查看日志详情。"
            await _send_checkin_push(
                push_manager,
                title=title,
                msg=msg,
                success=ok,
                cfg=cfg_one,
                traffic_info=traffic_info,
            )

        if push_manager is not None:
            await push_manager.close()

    logger.info("ikuuu签到：结束（成功 %d/%d 个账号）", success_count, len(valid_accounts))


async def _send_checkin_push(
    push_manager: UnifiedPushManager | None,
    title: str,
    msg: str,
    success: bool,
    cfg: CheckinConfig,
    traffic_info: str | None = None,
) -> None:
    """通过统一推送通道发送签到结果，可选附带流量信息。"""
    if push_manager is None:
        return

    # 免打扰时段内只记录日志，不推送
    app_cfg = get_config()
    if is_in_quiet_hours(app_cfg):
        logger.debug("ikuuu签到：免打扰时段，不发送推送")
        return

    masked_email = _mask_email(cfg.email)
    status_emoji = "✅" if success else "❌"
    description = f"{status_emoji} 账号：{masked_email}\n" f"{msg}\n"
    if traffic_info:
        description += f"\n【流量信息】\n{traffic_info}\n"
    description += f"\n登录地址：{cfg.login_url}\n" f"签到接口：{cfg.checkin_url}"

    try:
        await push_manager.send_news(
            title=f"{title}",
            description=description,
            to_url=cfg.user_page_url or cfg.login_url,
            picurl="https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg",
            btntxt="查看账户",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("ikuuu签到：发送签到结果推送失败：%s", exc, exc_info=True)


def _get_checkin_trigger_kwargs(config: AppConfig) -> dict:
    """供注册表与配置热重载使用。"""
    hour, minute = parse_checkin_time(config.checkin_time)
    return {"minute": minute, "hour": hour}


register_task("ikuuu_checkin", run_checkin_once, _get_checkin_trigger_kwargs)
