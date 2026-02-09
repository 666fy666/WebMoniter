"""999 会员中心健康打卡任务

参考 only_for_happly/999.py：
- 使用 Authorization 头（jjjck）完成每日健康打卡、阅读文章、体检等任务

本任务改造点：
- 多账号 Authorization 从 config.yml 的 nine_nine_nine.tokens 读取
- 统一使用项目推送通道，而非环境变量 plustoken
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)


@dataclass
class NineConfig:
    enable: bool
    tokens: list[str]
    time: str
    push_channels: list[str]

    @classmethod
    def from_app_config(cls, config: AppConfig) -> "NineConfig":
        tokens = getattr(config, "nine_nine_nine_tokens", None) or []
        tokens = [t.strip() for t in tokens if t and t.strip()]
        return cls(
            enable=getattr(config, "nine_nine_nine_enable", False),
            tokens=tokens,
            time=(getattr(config, "nine_nine_nine_time", None) or "15:15").strip()
            or "15:15",
            push_channels=getattr(config, "nine_nine_nine_push_channels", None) or [],
        )

    def validate(self) -> bool:
        if not self.enable:
            logger.debug("999 会员中心任务未启用，跳过")
            return False
        if not self.tokens:
            logger.error("999 会员中心配置不完整，缺少 tokens")
            return False
        return True


def _run_for_token(token: str) -> list[str]:
    """同步执行单个 999 账号的任务，返回多行日志文本。"""
    lines: list[str] = []
    today = datetime.now().date().strftime("%Y-%m-%d")

    headers = {
        "Host": "mc.999.com.cn",
        "Connection": "keep-alive",
        "locale": "zh_CN",
        "Authorization": token,
        "content-type": "application/json",
        "Accept-Encoding": "gzip,compress,br,deflate",
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_4_1 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
            "MicroMessenger/8.0.48(0x18003030) NetType/WIFI Language/zh_CN"
        ),
    }

    try:
        # 用户信息
        resp_user = requests.get(
            "https://mc.999.com.cn/zanmall_diy/ma/personal/user/info",
            headers=headers,
            timeout=20,
        )
        data_user = resp_user.json()
        phone = data_user.get("data", {}).get("phone", "未知")
        lines.append(f"开始账号：{phone} 打卡")

        check_in_list = [
            {"code": "mtbbs", "meaning": "每天八杯水"},
            {"code": "zs", "meaning": "早睡"},
            {"code": "ydswfz", "meaning": "运动15分钟"},
            {"code": "zq", "meaning": "早起"},
        ]

        # 健康打卡
        for item in check_in_list:
            payload = {
                "type": "daily_health_check_in",
                "params": {"checkInCode": item["code"], "checkInTime": today},
            }
            try:
                r = requests.post(
                    "https://mc.999.com.cn/zanmall_diy/ma/client/pointTaskClient/finishTask",
                    headers=headers,
                    json=payload,
                    timeout=20,
                )
                result = r.json().get("data") or {}
                point = result.get("point", 0)
                if result.get("success") is True:
                    lines.append(
                        f"打卡内容【{item['meaning']}】完成，获得积分 {point}"
                    )
                else:
                    lines.append(f"打卡内容【{item['meaning']}】：请勿重复打卡")
            except Exception as exc:
                lines.append(f"打卡内容【{item['meaning']}】异常：{exc}")

        # 阅读文章
        for i in range(5):
            payload_read = {
                "type": "explore_health_knowledge",
                "params": {"articleCode": str(random.randint(1, 20))},
            }
            try:
                r_read = requests.post(
                    "https://mc.999.com.cn/zanmall_diy/ma/client/pointTaskClient/finishTask",
                    headers=headers,
                    json=payload_read,
                    timeout=20,
                )
                result_read = r_read.json().get("data") or {}
                point = result_read.get("point", 0)
                lines.append(f"阅读文章成功，获得 {point} 积分")
            except Exception as exc:
                lines.append(f"阅读文章异常：{exc}")

        # 体检
        for _ in range(3):
            try:
                h_test = {
                    "gender": "1",
                    "age": "17",
                    "height": "188",
                    "weight": "50",
                    "waist": "55",
                    "hip": "55",
                    "food": {"breakfast": "1", "dietHabits": ["1"], "foodPreference": "1"},
                    "life": {"livingCondition": ["1"], "livingHabits": ["1"]},
                    "exercise": {"exerciseTimesWeekly": "1"},
                    "mental": {"mentalState": ["2"]},
                    "body": {
                        "bodyStatus": ["2"],
                        "oralStatus": "1",
                        "fruitReact": "1",
                        "skinCondition": ["1"],
                        "afterMealReact": "2",
                        "defecation": "2",
                    },
                    "sick": {
                        "bloating": "2",
                        "burp": "2",
                        "fart": "3",
                        "gurgle": "3",
                        "stomachache": "2",
                        "behindSternum": "4",
                        "ThroatOrMouthAcid": "4",
                        "FoodReflux": "4",
                        "auseaOrVomiting": "4",
                    },
                    "other": {"familyProducts": ["5"]},
                }
                r_htest = requests.post(
                    "https://mc.999.com.cn/zanmall_diy/ma/health/add",
                    headers=headers,
                    json=h_test,
                    timeout=20,
                )
                refer_no = r_htest.json().get("data", {}).get("referNo", "")
                lines.append(f"生成体检记录：{refer_no}")

                payload_ht = {
                    "type": "complete_health_testing",
                    "params": {"testCode": refer_no},
                }
                r_h_test = requests.post(
                    "https://mc.999.com.cn/zanmall_diy/ma/client/pointTaskClient/finishTask",
                    headers=headers,
                    json=payload_ht,
                    timeout=20,
                )
                point = r_h_test.json().get("data", {}).get("point", 0)
                lines.append(f"体检成功，获得 {point} 积分")
                time.sleep(5)
            except Exception as exc:
                lines.append(f"体检异常：{exc}")

        # 查询总积分
        try:
            r_total = requests.get(
                "https://mc.999.com.cn/zanmall_diy/ma/personal/point/pointInfo",
                headers=headers,
                timeout=20,
            )
            total = r_total.json().get("data")
            lines.append(f"当前总积分：{total}")
        except Exception as exc:
            lines.append(f"查询总积分异常：{exc}")

    except Exception as exc:  # pragma: no cover
        lines.append(f"账号处理异常：{exc}")

    return lines


async def run_nine_nine_nine_task_once() -> None:
    """执行一次 999 会员中心打卡任务（多 token）。"""
    app_cfg = get_config(reload=True)
    cfg = NineConfig.from_app_config(app_cfg)
    if not cfg.validate():
        return

    all_lines: list[str] = []
    for idx, token in enumerate(cfg.tokens, start=1):
        logger.info("999 会员中心：开始处理第 %d 个账号", idx)
        lines = await asyncio.to_thread(_run_for_token, token)
        all_lines.extend(lines)
        all_lines.append("")

    if not all_lines:
        return

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        push: UnifiedPushManager | None = await build_push_manager(
            app_cfg.push_channel_list,
            session,
            logger,
            init_fail_prefix="999 会员中心：",
            channel_names=cfg.push_channels or None,
        )
        if push and not is_in_quiet_hours(app_cfg):
            try:
                await push.send_news(
                    title="999 会员中心健康打卡结果",
                    description="\n".join(all_lines),
                    to_url="https://mc.999.com.cn/",
                    picurl="",
                    btntxt="打开 999 会员中心",
                )
            except Exception as exc:  # pragma: no cover
                logger.error("999 会员中心：推送失败：%s", exc, exc_info=True)
            finally:
                await push.close()


def _get_nine_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(
        getattr(config, "nine_nine_nine_time", "15:15") or "15:15"
    )
    return {"minute": minute, "hour": hour}


register_task(
    "nine_nine_nine_task",
    run_nine_nine_nine_task_once,
    _get_nine_trigger_kwargs,
)

