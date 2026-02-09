"""中国福彩抽奖活动任务

参考 only_for_happly/zgfc.py：
- 使用 Authorization 头参与“新年活动”：发送愿望、抽奖、点赞、查询奖品

本任务改造点：
- 多账号 Authorization 从 config.yml 的 zgfc.tokens 读取
- 使用统一推送通道报告中奖情况与执行结果
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)


@dataclass
class ZgfcConfig:
    enable: bool
    tokens: list[str]
    time: str
    push_channels: list[str]

    @classmethod
    def from_app_config(cls, config: AppConfig) -> "ZgfcConfig":
        tokens = getattr(config, "zgfc_tokens", None) or []
        tokens = [t.strip() for t in tokens if t and t.strip()]
        return cls(
            enable=getattr(config, "zgfc_enable", False),
            tokens=tokens,
            time=(getattr(config, "zgfc_time", None) or "08:00").strip() or "08:00",
            push_channels=getattr(config, "zgfc_push_channels", None) or [],
        )

    def validate(self) -> bool:
        if not self.enable:
            logger.debug("中国福彩抽奖任务未启用，跳过")
            return False
        if not self.tokens:
            logger.error("中国福彩抽奖配置不完整，缺少 tokens")
            return False
        return True


WISHES = [
    "财运亨通",
    "事业有成",
    "身体健康",
    "家庭和睦",
    "笑口常开",
    "步步高升",
    "心想事成",
    "万事如意",
    "龙马精神",
    "福禄双全",
]


def _run_for_token(token: str, index: int) -> tuple[list[str], list[str]]:
    """同步执行单个账号的福彩活动，返回 (日志行, 中奖信息行)。"""
    lines: list[str] = [f"账号 {index}：开始执行福彩抽奖任务"]
    win_lines: list[str] = []
    wish_ids: list[str] = []

    headers_base = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Mobile/15E148 MicroMessenger/8.0.45(0x18002d2a) "
            "NetType/WIFI Language/zh_CN"
        ),
        "Authorization": token,
    }

    try:
        # 发送愿望（最多 3 次）
        wish = random.choice(WISHES)
        data_encoded = f"wish={requests.utils.quote(wish)}"
        lines.append(f"发送愿望：{wish}")
        for j in range(3):
            try:
                resp = requests.post(
                    "https://ssqcx-serv.cwlo.com.cn/api/wish/send",
                    headers=headers_base,
                    data=data_encoded,
                    timeout=20,
                )
                result = resp.json()
                lines.append(f"愿望第 {j+1} 次：{result.get('msg')}")
                if j == 0 and result.get("data", {}).get("wish_id"):
                    wish_ids.append(str(result["data"]["wish_id"]))
            except Exception as exc:
                lines.append(f"发送愿望异常：{exc}")
                break

        # 抽奖
        lines.append("开始抽奖（最多 3 次）")
        for _ in range(3):
            try:
                resp2 = requests.post(
                    "https://ssqcx-serv.cwlo.com.cn/api/lottery/start",
                    headers=headers_base,
                    timeout=20,
                )
                result2 = resp2.json()
                msg = result2.get("msg", "")
                if msg == "成功" and result2.get("data", {}).get("lottery_sn"):
                    prize_title = result2["data"].get("prize_title", "")
                    line = f"账号 {index} 中奖：{prize_title or '获得奖励'}"
                    lines.append(line)
                    win_lines.append(line)
                elif msg == "成功":
                    lines.append("未中奖")
                else:
                    lines.append(f"抽奖失败：{msg}")
                time.sleep(2)
            except Exception as exc:
                lines.append(f"抽奖异常：{exc}")
                break

        # 点赞所有记录的愿望
        if wish_ids:
            lines.append("开始为愿望点赞")
            for wid in wish_ids:
                try:
                    resp3 = requests.post(
                        "https://ssqcx-serv.cwlo.com.cn/api/wish/zan",
                        headers=headers_base,
                        data=f"wish_id={wid}",
                        timeout=20,
                    )
                    result3 = resp3.json()
                    lines.append(f"点赞 {wid}：{result3.get('msg')}")
                except Exception as exc:
                    lines.append(f"点赞异常：{exc}")

        # 查询已获得奖品
        try:
            resp4 = requests.post(
                "https://ssqcx-serv.cwlo.com.cn/api/user/prize",
                headers=headers_base,
                timeout=20,
            )
            result4 = resp4.json().get("data", {}).get("prize", [])
            lines.append("已获得奖品列表：")
            lines.append(f"奖品数量：{len(result4)}")
            for item in result4:
                title = item.get("prize_title", "")
                lines.append(title)
        except Exception as exc:
            lines.append(f"查询奖品异常：{exc}")

    except Exception as exc:  # pragma: no cover
        lines.append(f"账号处理异常：{exc}")

    return lines, win_lines


async def run_zgfc_draw_once() -> None:
    """执行一次中国福彩抽奖任务（多 token）。"""
    app_cfg = get_config(reload=True)
    cfg = ZgfcConfig.from_app_config(app_cfg)
    if not cfg.validate():
        return

    all_lines: list[str] = []
    win_lines: list[str] = []
    for idx, token in enumerate(cfg.tokens, start=1):
        logger.info("中国福彩抽奖：开始处理第 %d 个账号", idx)
        lines, wins = await asyncio.to_thread(_run_for_token, token, idx)
        all_lines.extend(lines)
        all_lines.append("")
        win_lines.extend(wins)

    if not all_lines:
        return

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        push: UnifiedPushManager | None = await build_push_manager(
            app_cfg.push_channel_list,
            session,
            logger,
            init_fail_prefix="中国福彩抽奖：",
            channel_names=cfg.push_channels or None,
        )
        if push and not is_in_quiet_hours(app_cfg):
            # 若有中奖信息，优先在标题中提示
            title = "中国福彩抽奖结果"
            if win_lines:
                title = "中国福彩抽奖：有账号中奖！"
            try:
                await push.send_news(
                    title=title,
                    description="\n".join(all_lines),
                    to_url="https://ssqcx-serv.cwlo.com.cn/",
                    picurl="",
                    btntxt="查看活动",
                )
            except Exception as exc:  # pragma: no cover
                logger.error("中国福彩抽奖：推送失败：%s", exc, exc_info=True)
            finally:
                await push.close()


def _get_zgfc_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "zgfc_time", "08:00") or "08:00")
    return {"minute": minute, "hour": hour}


register_task("zgfc_draw", run_zgfc_draw_once, _get_zgfc_trigger_kwargs)

