"""爱奇艺签到与任务模块。参考 only_for_happly：Cookie 含 P00001/P00003/QC005/__dfp，签到、日常任务、抽奖、摇一摇、白金抽奖、用户信息。不刷观影时长以缩短执行时间。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from uuid import uuid4

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager
from src.utils import mask_cookie_for_log

logger = logging.getLogger(__name__)


def _parse_cookie(cookie: str) -> dict:
    out = {}
    for item in ["P00001", "P00003", "QC005", "__dfp"]:
        m = re.search(rf"{re.escape(item)}=(.*?)(;|$)", cookie)
        if m:
            out[item] = m.group(1).strip()
    if out.get("__dfp"):
        out["__dfp"] = out["__dfp"].split("@")[0]
    return out


def _run_iqiyi_sync(cookie: str) -> tuple[bool, str]:
    try:
        parsed = _parse_cookie(cookie)
        P00001 = parsed.get("P00001")
        P00003 = parsed.get("P00003")
        qyid = parsed.get("QC005", "")
        dfp = parsed.get("__dfp", "")
        if not P00001 or not P00003:
            return False, "Cookie 缺少 P00001 或 P00003"

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Cookie": f"P00001={P00001}",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "zh-CN,zh-Hans;q=0.9",
        })
        platform = str(uuid4())[:16]
        ts = int(time.time() * 1000)

        def req(url, method="GET", body=None):
            if method == "GET":
                r = session.get(url, params=body, timeout=15)
            else:
                r = session.post(url, data=json.dumps(body) if isinstance(body, dict) else body, headers={"Content-Type": "application/json"}, timeout=15)
            try:
                return r.json()
            except Exception:
                return {}

        msg_parts = []

        # 签到
        sign_data = f'agenttype=20|agentversion=15.5.5|appKey=lequ_rn|appver=15.5.5|authCookie={P00001}|qyid={qyid}|srcplatform=20|task_code=natural_month_sign|timestamp={ts}|userId={P00003}|cRcFakm9KSPSjFEufg3W'
        sign_url = f"https://community.iqiyi.com/openApi/task/execute?task_code=natural_month_sign&timestamp={ts}&appKey=lequ_rn&userId={P00003}&authCookie={P00001}&agenttype=20&agentversion=15.5.5&srcplatform=20&appver=15.5.5&qyid={qyid}&sign={hashlib.md5(sign_data.encode()).hexdigest()}"
        body = {"natural_month_sign": {"verticalCode": "iQIYI", "agentVersion": "15.4.6", "authCookie": P00001, "taskCode": "iQIYI_mofhr", "dfp": dfp, "qyid": qyid, "agentType": 20, "signFrom": 1}}
        data = req(sign_url, "POST", body)
        if data.get("code") == "A0003":
            return False, "Cookie 已失效，请重新获取"
        if data.get("code") == "A00000":
            d = data.get("data", {})
            if d.get("data", {}).get("signDays") is not None:
                msg_parts.append(f"签到成功，本月累计签到{d['data']['signDays']}天")
            elif "已经到达上限" in str(d.get("msg", "")):
                msg_parts.append("今日已签到")
            else:
                msg_parts.append(d.get("msg", "签到请求已提交"))

        # 日常任务（简化：只查询并领奖，不逐个 join/notify）
        task_url = f"https://tc.vip.iqiyi.com/taskCenter/task/queryUserTask?P00001={P00001}"
        task_data = req(task_url)
        if task_data.get("code") == "A00000":
            daily = (task_data.get("data") or {}).get("tasks", {}).get("daily", [])
            for item in daily:
                if item.get("status") == 0:
                    code = item.get("taskCode", "")
                    rwd_url = f"https://tc.vip.iqiyi.com/taskCenter/task/getTaskRewards?P00001={P00001}&taskCode={code}&lang=zh_CN&platform={platform}"
                    rwd = req(rwd_url)
                    if rwd.get("code") == "A00000":
                        msg_parts.append(f"{item.get('taskTitle', '')}领奖成功")

        # 抽奖
        lot_url = "https://iface2.iqiyi.com/aggregate/3.0/lottery_activity"
        lot_params = {"app_k": 0, "app_v": 0, "platform_id": 10, "qyid": qyid, "psp_uid": P00003, "psp_cki": P00001, "psp_status": 3, "req_sn": ts}
        lot_data = req(lot_url, "GET", lot_params)
        if lot_data.get("code") == 0 and lot_data.get("daysurpluschance", 0) > 0:
            msg_parts.append("抽奖: " + (lot_data.get("awardName") or "已抽"))

        # 摇一摇
        shake_url = f"https://act.vip.iqiyi.com/shake-api/lottery?P00001={P00001}&dfp={dfp}&qyid={qyid}&deviceID={qyid}&version=15.4.6&agentType=12&platform=bb35a104d95490f6&_={ts}&vipType=1&lotteryType=0&actCode=0k9GkUcjqqj4tne8&freeLotteryNum=3"
        shake_data = req(shake_url)
        if shake_data.get("code") == "A00000":
            msg_parts.append("摇一摇: " + (shake_data.get("data", {}).get("title") or "已摇"))

        # 用户信息
        info_url = f"https://tc.vip.iqiyi.com/growthAgency/v2/growth-aggregation?messageId=b7d48dbba64c4fd0f9f257dc89de8e25&platform=97ae2982356f69d8&P00001={P00001}&responseNodes=duration,growth,upgrade,viewTime,growthAnnualCard&_={ts}"
        info_data = req(info_url)
        if info_data.get("code") == "A00000":
            growth = (info_data.get("data") or {}).get("growth", {})
            msg_parts.append(f"等级:{growth.get('level','')} 今日成长:{growth.get('todayGrowthValue','')} 当前成长:{growth.get('growthvalue','')}")

        return True, "\n".join(msg_parts) if msg_parts else "任务已执行"
    except Exception as e:
        logger.warning("爱奇艺签到：异常 %s", e)
        return False, str(e)


async def run_iqiyi_checkin_once() -> None:
    from dataclasses import dataclass

    @dataclass
    class IqiyiConfig:
        enable: bool
        cookie: str
        cookies: list[str]
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> "IqiyiConfig":
            cookies: list[str] = getattr(config, "iqiyi_cookies", None) or []
            single = (getattr(config, "iqiyi_cookie", None) or "").strip()
            if not cookies and single:
                cookies = [single]
            push: list[str] = getattr(config, "iqiyi_push_channels", None) or []
            return cls(
                enable=getattr(config, "iqiyi_enable", False),
                cookie=single,
                cookies=cookies,
                time=(getattr(config, "iqiyi_time", None) or "06:00").strip() or "06:00",
                push_channels=push,
            )

        def validate(self) -> bool:
            if not self.enable:
                return False
            effective = self.cookies or ([self.cookie] if self.cookie else [])
            if not effective or not any(c.strip() for c in effective):
                logger.error("爱奇艺签到配置不完整")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = IqiyiConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [c.strip() for c in cfg.cookies if c.strip()]
    if not effective and cfg.cookie:
        effective = [cfg.cookie.strip()]
    logger.info("爱奇艺签到：开始执行（共 %d 个 Cookie）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list, session, logger,
            init_fail_prefix="爱奇艺签到：", channel_names=cfg.push_channels or None,
        )
        for idx, cookie_str in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(_run_iqiyi_sync, cookie_str)
            except Exception as e:
                logger.error("爱奇艺签到：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)
            if push_manager and not is_in_quiet_hours(app_config):
                masked = mask_cookie_for_log(cookie_str)
                title = "爱奇艺签到成功" if ok else "爱奇艺签到失败"
                try:
                    await push_manager.send_news(title=title, description=f"Cookie: {masked}\n{msg}", to_url="https://www.iqiyi.com", picurl="", btntxt="打开")
                except Exception as exc:
                    logger.error("爱奇艺签到：推送失败 %s", exc)
        if push_manager:
            await push_manager.close()
    logger.info("爱奇艺签到：结束（共 %d 个账号）", len(effective))


def _get_iqiyi_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "iqiyi_time", "06:00") or "06:00")
    return {"minute": minute, "hour": hour}


register_task("iqiyi_checkin", run_iqiyi_checkin_once, _get_iqiyi_trigger_kwargs)
