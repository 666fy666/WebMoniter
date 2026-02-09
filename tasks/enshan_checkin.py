"""恩山论坛签到/查询任务模块

参考 only_for_happly 恩山签到逻辑：
- 使用 Cookie 访问积分页面，解析恩山币与积分并推送
- 支持多 Cookie（多账号）
"""

from __future__ import annotations

import asyncio
import logging
import re

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager
from src.utils import mask_cookie_for_log

logger = logging.getLogger(__name__)

ENSHAN_CREDIT_URL = "https://www.right.com.cn/FORUM/home.php?mod=spacecp&ac=credit&showcredit=1"


def _run_enshan_sync(cookie: str) -> tuple[bool, str, str]:
    """
    同步执行恩山积分查询。

    Returns:
        (success, message, detail)
        - success: 是否成功获取
        - message: 简短结果说明
        - detail: 详情（恩山币、积分等）
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Cookie": cookie,
        }
    )
    try:
        resp = session.get(ENSHAN_CREDIT_URL, timeout=15)
        resp.raise_for_status()
        text = resp.text
        coin_m = re.findall(r"恩山币:\s*(.*?)\s*&nbsp;", text)
        point_m = re.findall(r"积分:\s*(.*?)(?:\s*</|$)", text)
        coin = coin_m[0].strip() if coin_m else "—"
        point = point_m[0].strip() if point_m else "—"
        return True, "查询成功", f"恩山币: {coin}，积分: {point}"
    except Exception as e:
        logger.warning("恩山签到：请求失败 %s", e)
        return False, f"请求失败: {e}", ""


async def run_enshan_checkin_once() -> None:
    """执行一次恩山签到/查询（支持多 Cookie），并接入统一推送。"""
    from dataclasses import dataclass

    @dataclass
    class EnshanConfig:
        enable: bool
        cookie: str
        cookies: list[str]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> EnshanConfig:
            cookies: list[str] = getattr(config, "enshan_cookies", None) or []
            single = (getattr(config, "enshan_cookie", None) or "").strip()
            if not cookies and single:
                cookies = [single]
            push: list[str] = getattr(config, "enshan_push_channels", None) or []
            return cls(
                enable=getattr(config, "enshan_enable", False),
                cookie=single,
                cookies=cookies,
                time=(getattr(config, "enshan_time", None) or "02:00").strip() or "02:00",
                push_channels=push,
            )

        def validate(self) -> bool:
            if not self.enable:
                logger.debug("恩山签到未启用，跳过")
                return False
            effective = self.cookies if self.cookies else ([self.cookie] if self.cookie else [])
            if not effective or not any(c.strip() for c in effective):
                logger.error("恩山签到配置不完整，缺少 cookie 或 cookies")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = EnshanConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [c.strip() for c in cfg.cookies if c.strip()]
    if not effective and cfg.cookie:
        effective = [cfg.cookie.strip()]
    logger.info("恩山签到：开始执行（共 %d 个 Cookie）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="恩山签到：",
            channel_names=cfg.push_channels if cfg.push_channels else None,
        )

        for idx, cookie_str in enumerate(effective):
            try:
                ok, msg, detail = await asyncio.to_thread(_run_enshan_sync, cookie_str)
            except Exception as e:
                logger.error("恩山签到：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg, detail = False, str(e), ""

            if push_manager and not is_in_quiet_hours(app_config):
                masked = mask_cookie_for_log(cookie_str)
                title = "恩山签到成功" if ok else "恩山签到失败"
                body = f"{'✅' if ok else '❌'} Cookie: {masked}\n{detail or msg}\n\n执行时间配置: {cfg.time}"
                try:
                    await push_manager.send_news(
                        title=title,
                        description=body,
                        to_url="https://www.right.com.cn/FORUM/",
                        picurl="",
                        btntxt="打开恩山",
                    )
                except Exception as exc:
                    logger.error("恩山签到：推送失败 %s", exc)

        if push_manager:
            await push_manager.close()

    logger.info("恩山签到：结束（共处理 %d 个账号）", len(effective))


def _get_enshan_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "enshan_time", "02:00") or "02:00")
    return {"minute": minute, "hour": hour}


register_task("enshan_checkin", run_enshan_checkin_once, _get_enshan_trigger_kwargs)
