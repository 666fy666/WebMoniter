"""富贵论坛签到任务模块

参考 only_for_happly 富贵论坛签到逻辑：
- 使用 Cookie 访问首页获取 formhash，再提交签到
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

FG_HOME_URL = "https://www.fglt.net/"
FG_SIGN_URL = (
    "https://www.fglt.net/plugin.php?id=dsu_amupper&ppersubmit=true&formhash={formhash}"
    "&infloat=yes&handlekey=dsu_amupper&inajax=1&ajaxtarget=fwin_content_dsu_amupper"
)


def _run_fg_sign_sync(cookie: str) -> tuple[bool, str]:
    """
    同步执行富贵论坛签到。

    Returns:
        (success, message)
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
        r = session.get(FG_HOME_URL, timeout=15)
        r.raise_for_status()
        text = r.text
        # 常见 Discuz formhash 在 input 或 页面变量中
        m = re.search(r'name="formhash"\s+value="([^"]+)"', text) or re.search(
            r"formhash['\"]?\s*[:=]\s*['\"]?([a-fA-F0-9]+)", text
        )
        if not m:
            return False, "未找到 formhash，请检查 Cookie 是否有效"
        formhash = m.group(1).strip()
        sign_url = FG_SIGN_URL.format(formhash=formhash)
        r2 = session.post(sign_url, timeout=15)
        r2.raise_for_status()
        # 解析结果：showDialog( 或 成功/已签到 等
        res_text = r2.text
        if "已签到" in res_text or "签到成功" in res_text or "success" in res_text.lower():
            return True, "签到成功"
        msg_m = re.search(r"showDialog\s*\(\s*['\"]([^'\"]+)", res_text)
        if msg_m:
            return True, msg_m.group(1).strip()
        return True, "请求已提交"
    except Exception as e:
        logger.warning("富贵论坛签到：请求失败 %s", e)
        return False, f"请求失败: {e}"


async def run_fg_checkin_once() -> None:
    """执行一次富贵论坛签到（支持多 Cookie），并接入统一推送。"""
    from dataclasses import dataclass

    @dataclass
    class FgConfig:
        enable: bool
        cookie: str
        cookies: list[str]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> FgConfig:
            cookies: list[str] = getattr(config, "fg_cookies", None) or []
            single = (getattr(config, "fg_cookie", None) or "").strip()
            if not cookies and single:
                cookies = [single]
            push: list[str] = getattr(config, "fg_push_channels", None) or []
            return cls(
                enable=getattr(config, "fg_enable", False),
                cookie=single,
                cookies=cookies,
                time=(getattr(config, "fg_time", None) or "00:01").strip() or "00:01",
                push_channels=push,
            )

        def validate(self) -> bool:
            if not self.enable:
                logger.debug("富贵论坛签到未启用，跳过")
                return False
            effective = self.cookies if self.cookies else ([self.cookie] if self.cookie else [])
            if not effective or not any(c.strip() for c in effective):
                logger.error("富贵论坛签到配置不完整，缺少 cookie 或 cookies")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = FgConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [c.strip() for c in cfg.cookies if c.strip()]
    if not effective and cfg.cookie:
        effective = [cfg.cookie.strip()]
    logger.info("富贵论坛签到：开始执行（共 %d 个 Cookie）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="富贵论坛签到：",
            channel_names=cfg.push_channels if cfg.push_channels else None,
        )

        for idx, cookie_str in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(_run_fg_sign_sync, cookie_str)
            except Exception as e:
                logger.error("富贵论坛签到：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)

            if push_manager and not is_in_quiet_hours(app_config):
                masked = mask_cookie_for_log(cookie_str)
                title = "富贵论坛签到成功" if ok else "富贵论坛签到失败"
                body = f"{'✅' if ok else '❌'} Cookie: {masked}\n{msg}\n\n执行时间配置: {cfg.time}"
                try:
                    await push_manager.send_news(
                        title=title,
                        description=body,
                        to_url=FG_HOME_URL,
                        picurl="",
                        btntxt="打开论坛",
                    )
                except Exception as exc:
                    logger.error("富贵论坛签到：推送失败 %s", exc)

        if push_manager:
            await push_manager.close()

    logger.info("富贵论坛签到：结束（共处理 %d 个账号）", len(effective))


def _get_fg_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "fg_time", "00:01") or "00:01")
    return {"minute": minute, "hour": hour}


register_task("fg_checkin", run_fg_checkin_once, _get_fg_trigger_kwargs)
