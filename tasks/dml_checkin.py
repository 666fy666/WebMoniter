"""达美乐任务模块（分享+抽奖）

参考 only_for_happly 达美乐逻辑：使用 openid 调用分享与游戏完成接口。
"""

from __future__ import annotations

import asyncio
import logging

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)

SHARING_DONE_URL = "https://game.dominos.com.cn/bulgogi/game/sharingDone"
GAME_DONE_URL = "https://game.dominos.com.cn/bulgogi/game/gameDone"
GAME_PAYLOAD_TEMPLATE = "openid={openid}&score=d8XtWSEx0zRy%2BxdeJriXZeoTek6ZVZdadlxdTFiN9yrxt%2BSIax0%2BRccbkObBZsisYFTquPg%2FG2cnGPBlGV2f32C6D5q3FFhgvcfJP9cKg%2BXs6l7J%2BEcahicPml%2BZWp3P4o1pOQvNdDUTQgtO6NGY0iijZ%2FLAmITy5EJU8dAc1EnbvhOYG36Qg1Ji4GDRoxAfRgmELvpLM6JSFlCEKG2C2s%2BJCevOJo7kwsLJCvwbVgeewhKSAyCZYnJQ4anmPgvrv6iUIiFQP%2Bj6%2B5p1VETe5xfawQ4FQ4w0mttXP0%2BhX39n1dzDrfcSkYkUaWPkIFlHAX7QPT3IgG6MhIKCvB%2BUcw%3D%3D&tempId=16408240716151126162"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 12; M2012K11AC Build/SKQ1.211006.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/122.0.6261.120 Mobile Safari/537.36 XWEB/1220133 MMWEBSDK/20240404 MicroMessenger/8.0.49.2600 WeChat/arm64 Weixin NetType/WIFI Language/zh_CN",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://servicewechat.com/wx887bf6ad752ca2f2/63/page-frame.html",
}


def _run_dml_sync(openid: str) -> tuple[bool, str]:
    """同步执行达美乐分享+抽奖。Returns (success, message)."""
    messages = []
    try:
        share_data = f"openid={openid}&from=1&target=0"
        r = requests.post(SHARING_DONE_URL, data=share_data, headers=HEADERS, timeout=15)
        r.raise_for_status()
        res = r.json()
        if res.get("errorMessage") == "今日分享已用完，请明日再来":
            messages.append("分享已达上限")
        elif res.get("statusCode") == 0:
            messages.append("分享成功")
        else:
            messages.append("分享失败: " + res.get("errorMessage", ""))

        game_data = GAME_PAYLOAD_TEMPLATE.format(openid=openid)
        for _ in range(3):
            r2 = requests.post(GAME_DONE_URL, data=game_data, headers=HEADERS, timeout=15)
            if r2.status_code != 200:
                continue
            j = r2.json()
            if j.get("statusCode") == 0:
                prize = (j.get("content") or {}).get("name", "")
                if prize:
                    messages.append("抽奖: " + prize)
            else:
                messages.append("抽奖失败: " + j.get("errorMessage", ""))
            break
        return True, "\n".join(messages) if messages else "已执行"
    except Exception as e:
        logger.warning("达美乐任务：请求失败 %s", e)
        return False, str(e)


async def run_dml_checkin_once() -> None:
    """执行一次达美乐任务（支持多 openid），并接入统一推送。"""
    from dataclasses import dataclass

    @dataclass
    class DmlConfig:
        enable: bool
        openid: str
        openids: list[str]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> DmlConfig:
            openids: list[str] = getattr(config, "dml_openids", None) or []
            single = (getattr(config, "dml_openid", None) or "").strip()
            if not openids and single:
                openids = [single]
            push: list[str] = getattr(config, "dml_push_channels", None) or []
            return cls(
                enable=getattr(config, "dml_enable", False),
                openid=single,
                openids=openids,
                time=(getattr(config, "dml_time", None) or "06:00").strip() or "06:00",
                push_channels=push,
            )

        def validate(self) -> bool:
            if not self.enable:
                return False
            effective = self.openids or ([self.openid] if self.openid else [])
            if not effective or not any(o.strip() for o in effective):
                logger.error("达美乐任务配置不完整，缺少 openid 或 openids")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = DmlConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [o.strip() for o in cfg.openids if o.strip()]
    if not effective and cfg.openid:
        effective = [cfg.openid.strip()]
    logger.info("达美乐任务：开始执行（共 %d 个账号）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="达美乐任务：",
            channel_names=cfg.push_channels or None,
        )
        for idx, openid in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(_run_dml_sync, openid)
            except Exception as e:
                logger.error("达美乐任务：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)
            if push_manager and not is_in_quiet_hours(app_config):
                title = "达美乐任务成功" if ok else "达美乐任务失败"
                try:
                    await push_manager.send_news(
                        title=title,
                        description=msg,
                        to_url="https://game.dominos.com.cn",
                        picurl="",
                        btntxt="打开",
                    )
                except Exception as exc:
                    logger.error("达美乐任务：推送失败 %s", exc)
        if push_manager:
            await push_manager.close()
    logger.info("达美乐任务：结束（共处理 %d 个账号）", len(effective))


def _get_dml_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "dml_time", "06:00") or "06:00")
    return {"minute": minute, "hour": hour}


register_task("dml_checkin", run_dml_checkin_once, _get_dml_trigger_kwargs)
