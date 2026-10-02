"""快手开播／下播监控。无法确认状态时保留旧快照，绝不推断为下播。"""

import asyncio
import json
import re
from datetime import datetime
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from src.monitors.base import BaseMonitor, CookieExpiredError
from src.monitors.kuaishou_targets import (
    checked_url,
    principal_from_target,
    prune_targets,
    target_key,
)
from src.settings.config import AppConfig, get_config, is_in_quiet_hours

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
)


class KuaishouStateError(ValueError):
    """仅包含可安全记录的诊断，不包含站点响应或凭据。"""


def parse_live_page(html: str, principal_id: str) -> dict:
    """只接受成功响应中的明确布尔状态，不将空数据或错误页当作下播。"""
    marker = re.search(r"window\.__INITIAL_STATE__\s*=\s*", html)
    if not marker:
        raise KuaishouStateError("快手页面缺少状态数据，可能需要登录或接口已变化")
    # 页面状态可含 JS undefined；只替换字符串以外的字面量，绝不执行网页脚本。
    raw = re.sub(
        r'"(?:\\.|[^"\\])*"|\bundefined\b',
        lambda match: "null" if match[0] == "undefined" else match[0],
        html[marker.end() :].split("</script>", 1)[0],
    )
    state, _ = json.JSONDecoder().raw_decode(raw)
    room = state.get("liveroom") if isinstance(state, dict) else None
    playlist = room.get("playList") if isinstance(room, dict) else None
    if not isinstance(playlist, list) or not playlist or not isinstance(playlist[0], dict):
        raise KuaishouStateError("快手页面缺少直播间信息")
    item = playlist[0]
    author = item.get("author")
    if item.get("errorType") or type(item.get("isLiving")) is not bool:
        raise KuaishouStateError("快手页面返回错误或缺少明确直播状态")
    status = item.get("status")
    code = status.get("forbiddenState") if isinstance(status, dict) else None
    # 官方页面也会保留受限房间的 isLiving:false；仅接受成功和明确未开播。
    if type(code) is not int or code not in {1, 671}:
        raise KuaishouStateError("快手页面直播权限受限或缺少有效状态码，保留旧状态")
    if code == 671 and item["isLiving"]:
        raise KuaishouStateError("快手页面直播状态与状态码冲突，保留旧状态")
    if not isinstance(author, dict):
        raise KuaishouStateError("快手页面缺少主播信息")
    # 无法证明属于目标主播时，不能用推荐直播间覆盖该主播的状态。
    ids = {str(author.get(key) or "") for key in ("id", "principalId")}
    if principal_id not in ids:
        raise KuaishouStateError("快手页面主播与监控目标不匹配，请使用主页中的主播 ID")
    name = author.get("name")
    if not isinstance(name, str) or not name.strip():
        raise KuaishouStateError("快手响应缺少主播信息")
    return {"principal_id": principal_id, "name": name, "is_live": "1" if item["isLiving"] else "0"}


class KuaishouMonitor(BaseMonitor):
    @property
    def platform_name(self) -> str:
        return "kuaishou"

    @property
    def monitor_name(self) -> str:
        return "快手直播监控"

    @property
    def push_channel_names(self) -> list[str] | None:
        return self.config.kuaishou_push_channels or None

    async def resolve_target(self, target: str) -> str:
        principal = principal_from_target(target)
        if principal:
            return principal
        url = checked_url(target)
        # 短链请求使用独立、无 Cookie 的会话，逐跳检查目标，避免凭据泄漏。
        async with aiohttp.ClientSession(
            cookie_jar=aiohttp.DummyCookieJar(),
            timeout=aiohttp.ClientTimeout(total=10),
            headers={"User-Agent": _USER_AGENT},
        ) as session:
            for _ in range(5):
                async with session.get(url, allow_redirects=False) as resp:
                    if resp.status in {301, 302, 303, 307, 308}:
                        location = resp.headers.get("Location")
                        if not location:
                            raise ValueError("快手短链缺少跳转地址")
                        url = checked_url(urljoin(url, location))
                    else:
                        resp.raise_for_status()
                        html = await resp.text()
                        soup = BeautifulSoup(html, "html.parser")
                        canonical = soup.find("link", rel="canonical")
                        if not canonical or not canonical.get("href"):
                            raise ValueError("快手分享链接未解析出主播 ID，请使用网页版主页")
                        url = checked_url(urljoin(url, canonical["href"]))
                    principal = principal_from_target(url)
                    if principal:
                        return principal
        raise ValueError("快手分享链接跳转次数过多或不包含主播 ID")

    async def get_info(self, principal_id: str) -> dict:
        session = await self._get_session()
        cookie = self.config.get_kuaishou_config().cookie
        headers = {"User-Agent": _USER_AGENT, "Referer": "https://live.kuaishou.com/"}
        if cookie:
            headers["Cookie"] = cookie
        async with session.get(
            f"https://live.kuaishou.com/u/{principal_id}",
            headers=headers,
            allow_redirects=False,
        ) as resp:
            if resp.status == 401:
                raise CookieExpiredError("快手需要重新登录，请更新 Cookie")
            if resp.status != 200:
                raise KuaishouStateError(f"快手状态获取失败（HTTP {resp.status}），保留旧状态")
            html = await resp.text()
        return parse_live_page(html, principal_id)

    async def process_room(self, principal_id: str) -> None:
        data = await self.get_info(principal_id)
        rows = await self.db.execute_query(
            "SELECT is_live FROM kuaishou WHERE principal_id=%(pk)s", {"pk": principal_id}
        )
        if not rows:
            await self.db.execute_insert(
                "INSERT INTO kuaishou (principal_id, name, is_live) VALUES (%(principal_id)s, %(name)s, %(is_live)s)",
                data,
            )
            return
        changed = rows[0][0] != data["is_live"]
        saved = await self.db.execute_update(
            "UPDATE kuaishou SET name=%(name)s, is_live=%(is_live)s WHERE principal_id=%(principal_id)s",
            data,
        )
        if not saved or not changed or is_in_quiet_hours(self.config):
            return
        status = "开播了" if data["is_live"] == "1" else "下播了"
        await self.send_push_news(
            title=f"{data['name']} {status}",
            description=f"快手主播：{data['name']}\n主播 ID：{principal_id}\n{datetime.now():%Y-%m-%d %H:%M:%S}",
            to_url=f"https://live.kuaishou.com/u/{principal_id}",
            picurl="",
        )

    async def run(self) -> None:
        self.config = get_config(reload=False)
        if not self.config.kuaishou_enable:
            return
        cfg = self.config.get_kuaishou_config()
        await prune_targets(self.db, cfg.targets)
        if self.skip_if_no_targets(cfg.targets, "快手主播"):
            return
        rows = await self.db.execute_query(
            "SELECT target_key, target, principal_id FROM kuaishou_targets"
        )
        cached = {target: principal for _, target, principal in rows}
        principals = set()
        for target in cfg.targets:
            try:
                principal = cached.get(target) or await self.resolve_target(target)
                if target not in cached:
                    await self.db.execute_insert(
                        "INSERT INTO kuaishou_targets (target_key, target, principal_id) VALUES (%(target_key)s, %(target)s, %(principal_id)s)",
                        {
                            "target_key": target_key(target),
                            "target": target,
                            "principal_id": principal,
                        },
                    )
                principals.add(principal)
            except (ValueError, aiohttp.ClientError, TimeoutError):
                self.logger.warning(
                    "快手目标 %s 解析失败，请检查链接或改用网页版主页", target_key(target)[:8]
                )
        semaphore = asyncio.Semaphore(cfg.concurrency)

        async def process(principal):
            async with semaphore:
                try:
                    await self.process_room(principal)
                except CookieExpiredError as exc:
                    await self.handle_cookie_expired(exc)
                except Exception as exc:
                    # 不记录响应正文或请求头，避免将平台凭据写入日志。
                    self.logger.warning(
                        "快手主播 %s 本轮获取失败（%s），保留旧状态",
                        principal,
                        str(exc) if isinstance(exc, KuaishouStateError) else type(exc).__name__,
                    )

        await asyncio.gather(*(process(principal) for principal in sorted(principals)))
        # 请求期间配置可能已删除目标，不能用轮询开始时的旧列表重新保留记录。
        await prune_targets(self.db, get_config(reload=False).get_kuaishou_config().targets)


async def run_kuaishou_monitor() -> None:
    async with KuaishouMonitor(get_config(reload=True)) as monitor:
        await monitor.run()


def _get_kuaishou_trigger_kwargs(config: AppConfig) -> dict:
    return {"seconds": config.kuaishou_monitor_interval_seconds}


from src.jobs.registry import register_monitor

register_monitor(
    "kuaishou_monitor",
    run_kuaishou_monitor,
    _get_kuaishou_trigger_kwargs,
    description="快手直播监控",
)
