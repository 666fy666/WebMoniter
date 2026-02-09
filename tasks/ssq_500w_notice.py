"""双色球开奖监控 + 守号检测 + 冷号机选

参考 only_for_happly/500w.py：
- 调用官方历史开奖接口获取最新一期双色球开奖结果及近 100 期历史数据
- 对固定守号进行中奖情况检测
- 基于冷号进行若干机选推荐

本任务改造点：
- 仅用于信息通知，不涉及真实购彩
- 配置开关与执行时间来自 config.yml 的 ssq_500w 节
- 推送通过本项目统一推送通道完成
"""

from __future__ import annotations

import logging
import random
from collections import Counter
from datetime import datetime

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)

API_URL = "https://ms.zhcw.com/proxy/lottery-chart-center/history/SSQ"
HISTORY_LIMIT = 100
NUM_GENERATED = 2

# 默认守号示例（可后续扩展为从配置读取）
FIXED_TICKETS = [
    {"red": [2, 15, 20, 21, 24, 26], "blue": 1},
    {"red": [3, 4, 11, 17, 23, 30], "blue": 6},
]


def _fetch_latest_and_history() -> tuple[dict | None, list[list[str]] | None, list[int] | None]:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    payload = {"limit": HISTORY_LIMIT, "page": 1, "params": {}}

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        datas = resp.json()["datas"]
        latest = datas[0]

        red_str = latest["winningFrontNum"]
        blue_str = latest["winningBackNum"]
        period = latest.get("issue", "未知")
        date = latest.get("openDate", "")[:10]

        latest_red = sorted(int(x) for x in red_str.split())
        latest_blue = int(blue_str)

        red_hist = [entry["winningFrontNum"].split() for entry in datas]
        blue_hist = [int(entry["winningBackNum"]) for entry in datas]

        return (
            {"period": period, "date": date, "red": latest_red, "blue": latest_blue},
            red_hist,
            blue_hist,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("获取双色球开奖数据失败：%s", exc)
        return None, None, None


def _check_prize(ticket_red: list[int], ticket_blue: int, win_red: list[int], win_blue: int) -> str:
    rh = len(set(ticket_red) & set(win_red))
    bh = 1 if ticket_blue == win_blue else 0
    if rh == 6 and bh:
        return "★★★★★ 一等奖（理论）★★★★★"
    if rh == 6:
        return "二等奖（理论）"
    if rh == 5 and bh:
        return "三等奖（理论）"
    if rh == 5 or (rh == 4 and bh):
        return "四等奖（理论）"
    if rh == 4 or (rh == 3 and bh):
        return "五等奖（理论）"
    if bh:
        return "六等奖（理论）"
    return "未中（仅供娱乐参考）"


def _generate_cold_numbers(red_hist: list[list[str]], blue_hist: list[int]) -> tuple[list[int], int]:
    red_all = [int(n) for sub in red_hist for n in sub]
    red_c = Counter(red_all)
    blue_c = Counter(blue_hist)

    cold_red = [n for n, _ in sorted(red_c.items(), key=lambda x: x[1])[:18]]
    cold_blue = [n for n, _ in sorted(blue_c.items(), key=lambda x: x[1])[:10]]

    reds = sorted(
        random.sample(cold_red if len(cold_red) >= 6 else list(range(1, 34)), 6)
    )
    blue = random.choice(cold_blue if cold_blue else list(range(1, 17)))
    return reds, blue


async def run_ssq_500w_notice_once() -> None:
    """执行一次双色球开奖通知任务。"""
    app_cfg = get_config(reload=True)
    if not getattr(app_cfg, "ssq_500w_enable", False):
        logger.debug("ssq_500w 任务未启用，跳过执行")
        return

    result, r_hist, b_hist = _fetch_latest_and_history()
    if not result or not r_hist or not b_hist:
        logger.error("ssq_500w：获取最新开奖数据失败")
        return

    lines: list[str] = []
    lines.append(
        f"双色球 {result['period']} 已开奖！（仅供娱乐参考）"
    )
    lines.append(f"开奖日期：{result['date']}")
    lines.append(
        "开奖号码：{reds} + {blue:02d}".format(
            reds=" ".join(f"{x:02d}" for x in result["red"]),
            blue=result["blue"],
        )
    )
    lines.append("")

    # 守号检测
    for i, t in enumerate(FIXED_TICKETS, 1):
        prize = _check_prize(t["red"], t["blue"], result["red"], result["blue"])
        rs = " ".join(f"{x:02d}" for x in sorted(t["red"]))
        lines.append(f"守号第{i}注：{rs} + {t['blue']:02d}")
        lines.append(f" → {prize}")
        lines.append("")

    # 冷号机选
    lines.append("今日冷号机选推荐（仅供娱乐参考）：")
    for i in range(NUM_GENERATED):
        r, b = _generate_cold_numbers(r_hist, b_hist)
        rs = " ".join(f"{x:02d}" for x in r)
        lines.append(f"机选第{i+1}注：{rs} + {b:02d}")

    description = "\n".join(lines)
    logger.info("ssq_500w：生成通知内容完成")

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        push: UnifiedPushManager | None = await build_push_manager(
            app_cfg.push_channel_list,
            session,
            logger,
            init_fail_prefix="双色球开奖通知：",
            channel_names=getattr(app_cfg, "ssq_500w_push_channels", None) or None,
        )
        if push and not is_in_quiet_hours(app_cfg):
            try:
                await push.send_news(
                    title=f"双色球开奖通知（第 {result['period']} 期）",
                    description=description,
                    to_url="https://www.zhcw.com/",
                    picurl="",
                    btntxt="查看详情",
                )
            except Exception as exc:  # pragma: no cover
                logger.error("ssq_500w：推送失败：%s", exc, exc_info=True)
            finally:
                await push.close()


def _get_ssq_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(
        getattr(config, "ssq_500w_time", "21:30") or "21:30"
    )
    return {"minute": minute, "hour": hour}


register_task("ssq_500w_notice", run_ssq_500w_notice_once, _get_ssq_trigger_kwargs)

