"""帆软社区签到 + 摇摇乐任务

参考 only_for_happly/fr.py：
- 使用社区 Cookie 获取 formhash
- 执行签到并查询签到信息
- 执行摇摇乐并查询结果

本任务改造点：
- Cookie 从 config.yml 的 fr.cookie 读取
- 接入统一推送与免打扰逻辑
"""

from __future__ import annotations

import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)


def _run_fr_sync(cookie: str) -> str:
    """同步执行帆软签到与摇摇乐逻辑，返回多行文本。"""
    if not cookie:
        return "❌ 未配置 Cookie"

    date = time.strftime("%Y%m%d", time.localtime())

    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "zh-CN,zh;q=0.9",
        "referer": "https://bbs.fanruan.com/qiandao/",
        "cookie": cookie,
        "user-agent": (
            "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
        ),
    }
    try:
        # 获取 formhash
        url = "https://bbs.fanruan.com/plugin.php?id=k_misign:sign"
        checksign_url = "https://bbs.fanruan.com/qiandao/"
        resp = requests.get(url=url, headers=headers, timeout=20).text
        formhash_match = re.search(r"formhash=(.*?)\">退出 ", resp, re.S)
        if not formhash_match:
            return "❌ 未找到 formhash，请检查 Cookie 是否有效"
        formhash = formhash_match.group(1)

        # 签到
        sign_url = (
            f"https://bbs.fanruan.com/qiandao/?mod=sign&operation=qiandao"
            f"&formhash={formhash}&from=insign&inajax=1&ajaxtarget=JD_sign"
        )
        _ = requests.get(url=sign_url, headers=headers, timeout=20).text

        # 查询签到信息
        check_re = requests.get(url=checksign_url, headers=headers, timeout=20).text
        user = "".join(
            re.findall(r'" c="1" class="author">(.*?) ', check_re, re.S)
        ).strip()
        sign_rank = "".join(
            re.findall(r" ", check_re, re.S)
        ).strip()  # 原脚本中示例，不再精细解析

        # 使用 BeautifulSoup 更稳健地提取部分信息
        soup = BeautifulSoup(check_re, "html.parser")
        info_text = soup.get_text(" ", strip=True)

        # 摇摇乐
        yyl_url = "https://bbs.fanruan.com/plugin.php?id=yinxingfei_zzza:yinxingfei_zzza_post"
        yyl_info_url = "https://bbs.fanruan.com/plugin.php?id=yinxingfei_zzza:yinxingfei_zzza_hall"
        yyl_data = {"id": "yinxingfei_zzza:yinxingfei_zzza_post", "formhash": formhash}
        _ = requests.post(url=yyl_url, headers=headers, data=yyl_data, timeout=20).text
        yyl_info = requests.post(url=yyl_info_url, headers=headers, timeout=20).text
        yyl_soup = BeautifulSoup(yyl_info, "html.parser")
        yyl_text = yyl_soup.get_text(" ", strip=True)

        lines: list[str] = []
        lines.append(f"日期：{date}")
        lines.append(f"用户：{user or '未知'}")
        if sign_rank:
            lines.append(f"签到排名：{sign_rank}")
        lines.append("")
        lines.append("签到页面信息：")
        lines.append(info_text[:500] + "..." if len(info_text) > 500 else info_text)
        lines.append("")
        lines.append("摇摇乐信息：")
        lines.append(yyl_text[:500] + "..." if len(yyl_text) > 500 else yyl_text)

        return "\n".join(lines)
    except Exception as exc:  # pragma: no cover
        logger.warning("帆软签到：执行异常：%s", exc)
        return f"❌ 帆软签到执行异常：{exc}"


async def run_fr_checkin_once() -> None:
    """执行一次帆软社区签到 + 摇摇乐任务。"""
    app_cfg = get_config(reload=True)
    if not getattr(app_cfg, "fr_enable", False):
        logger.debug("帆软签到未启用，跳过执行")
        return
    cookie = getattr(app_cfg, "fr_cookie", "") or ""

    text = await asyncio.to_thread(_run_fr_sync, cookie)
    if not text:
        return

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        push: UnifiedPushManager | None = await build_push_manager(
            app_cfg.push_channel_list,
            session,
            logger,
            init_fail_prefix="帆软签到：",
            channel_names=getattr(app_cfg, "fr_push_channels", None) or None,
        )
        if push and not is_in_quiet_hours(app_cfg):
            try:
                await push.send_news(
                    title="帆软社区签到 & 摇摇乐",
                    description=text,
                    to_url="https://bbs.fanruan.com/qiandao/",
                    picurl="",
                    btntxt="打开帆软社区",
                )
            except Exception as exc:  # pragma: no cover
                logger.error("帆软签到：推送失败：%s", exc, exc_info=True)
            finally:
                await push.close()


def _get_fr_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "fr_time", "06:30") or "06:30")
    return {"minute": minute, "hour": hour}


register_task("fr_checkin", run_fr_checkin_once, _get_fr_trigger_kwargs)

