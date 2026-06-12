"""小红书动态监控模块（类似微博）"""

import asyncio
import json
import logging
from datetime import datetime

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from src.monitors.base import BaseMonitor
from src.settings.config import AppConfig, get_config, is_in_quiet_hours

XHS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _extract_initial_state(html: str) -> str:
    """从页面中提取 window.__INITIAL_STATE__ 的 JSON 内容"""
    prefix = "window.__INITIAL_STATE__="
    idx = html.find(prefix)
    if idx < 0:
        return ""
    start = idx + len(prefix)
    depth = 0
    in_string = False
    escape = False
    for i, c in enumerate(html[start:], start):
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if c in ('"', "'") and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return html[start : i + 1]
    return ""


class XhsMonitor(BaseMonitor):
    """小红书动态监控类（类似微博）"""

    def __init__(self, config: AppConfig, session: ClientSession | None = None):
        super().__init__(config, session)
        self.xhs_config = config.get_xhs_config()
        self.old_data_dict: dict[str, tuple] = {}
        self._is_first_time: bool = False

    async def initialize(self):
        await super().initialize()
        await self.load_old_info()

    async def _get_session(self) -> ClientSession:
        if self.session is None:
            headers = {
                "User-Agent": XHS_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.xiaohongshu.com/",
            }
            if self.xhs_config.cookie:
                headers["Cookie"] = self.xhs_config.cookie
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=ClientTimeout(total=15),
            )
            self._own_session = True
        else:
            self.session.headers["User-Agent"] = XHS_USER_AGENT
            if self.xhs_config.cookie:
                self.session.headers["Cookie"] = self.xhs_config.cookie
        return self.session

    async def load_old_info(self):
        try:
            sql = "SELECT profile_id, user_name, latest_note_title FROM xhs"
            results = await self.db.execute_query(sql)
            self.old_data_dict = {row[0]: row for row in results}
            self._is_first_time = len(self.old_data_dict) == 0
        except Exception as e:
            self.logger.error(f"加载旧数据失败: {e}")
            self.old_data_dict = {}
            self._is_first_time = True

    async def get_info(self, profile_id: str) -> dict:
        """获取用户最新动态"""
        session = await self._get_session()
        url = f"https://www.xiaohongshu.com/user/profile/{profile_id}"

        async with session.get(url) as response:
            response.raise_for_status()
            html_text = await response.text()

        raw = _extract_initial_state(html_text)
        if not raw:
            raise ValueError(f"无法解析小红书用户 {profile_id} 页面")

        raw = raw.replace("undefined", "null")
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError(f"解析小红书 {profile_id} JSON 失败")

        user_data = result.get("user", {})
        if not user_data:
            raise ValueError(f"小红书 {profile_id} 用户数据为空")

        user_page = user_data.get("userPageData", {}) or {}
        basic_info = user_page.get("basicInfo", {}) or {}
        user_name = basic_info.get("nickname", "未知")

        notes_data = user_data.get("notes", {})
        if isinstance(notes_data, dict):
            # 取第一个 key 对应的列表
            first_key = next(iter(notes_data.keys()), None)
            notes_list = notes_data.get(first_key, []) if first_key else []
        elif isinstance(notes_data, list):
            notes_list = notes_data[0] if notes_data else []
        else:
            notes_list = []

        if not notes_list:
            return {
                "profile_id": profile_id,
                "user_name": user_name,
                "latest_note_title": "",
                "note_id": "",
                "pic_url": "",
            }

        # 过滤置顶
        notes = [
            n
            for n in notes_list
            if n.get("noteCard")
            and not (n.get("noteCard", {}).get("interactInfo") or {}).get("sticky")
        ]
        if not notes:
            return {
                "profile_id": profile_id,
                "user_name": user_name,
                "latest_note_title": "",
                "note_id": "",
                "pic_url": "",
            }

        note = notes[0]
        note_card = note.get("noteCard", {})
        note_title = note_card.get("displayTitle", "")
        note_id = note_card.get("noteId", "")
        cover = note_card.get("cover", {}) or {}
        info_list = cover.get("infoList") or []
        pic_url = info_list[-1].get("url", "") if info_list else ""

        return {
            "profile_id": profile_id,
            "user_name": user_name,
            "latest_note_title": note_title,
            "note_id": note_id,
            "pic_url": pic_url,
        }

    def check_info(self, data: dict, old_info: tuple) -> bool:
        """是否有新动态"""
        old_title = old_info[2] if len(old_info) > 2 else ""
        return data.get("latest_note_title", "") != old_title

    async def process_user(self, profile_id: str):
        try:
            new_data = await self.get_info(profile_id)
        except Exception as e:
            self.logger.error(f"获取小红书用户 {profile_id} 数据失败: {e}")
            return

        if profile_id in self.old_data_dict:
            old_info = self.old_data_dict[profile_id]
            if not self.check_info(new_data, old_info):
                self.logger.debug(f"{new_data['user_name']} 最近在摸鱼🐟")
                return

            sql = (
                "UPDATE xhs SET user_name=%(user_name)s, latest_note_title=%(latest_note_title)s "
                "WHERE profile_id=%(profile_id)s"
            )
            await self.db.execute_update(sql, new_data)

            self.logger.info(f"{new_data['user_name']} 发布了新笔记📕")
            await self.push_notification(new_data)
        else:
            sql = (
                "INSERT INTO xhs (profile_id, user_name, latest_note_title) "
                "VALUES (%(profile_id)s, %(user_name)s, %(latest_note_title)s)"
            )
            await self.db.execute_insert(sql, new_data)

            if self._is_first_time:
                self.logger.info(f"{new_data['user_name']} 新收录（首次创建数据库，跳过推送）")
            else:
                self.logger.info(f"{new_data['user_name']} 发布了新笔记📕 (新收录)")
                await self.push_notification(new_data)

    async def push_notification(self, data: dict):
        if is_in_quiet_hours(self.config):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.logger.info(
                f"[免打扰时段] {data['user_name']} 发布新笔记（{timestamp}），已跳过推送"
            )
            return

        title_text = data.get("latest_note_title", "") or "新笔记"
        pic_url = (
            data.get("pic_url")
            or "https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg"
        )
        note_id = data.get("note_id", "")
        jump_url = (
            f"https://www.xiaohongshu.com/explore/{note_id}"
            if note_id
            else f"https://www.xiaohongshu.com/user/profile/{data['profile_id']}"
        )

        try:
            await self.push.send_news(
                title=f"{data['user_name']} 发动态了📕",
                description=f"【{title_text}】\n\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                to_url=jump_url,
                picurl=pic_url,
                btntxt="阅读全文",
            )
        except Exception as e:
            self.logger.error(f"推送失败: {e}")

    @property
    def platform_name(self) -> str:
        return "xhs"

    @property
    def push_channel_names(self) -> list[str] | None:
        channels = getattr(self.config, "xhs_push_channels", None)
        return channels if channels else None

    async def run(self):
        new_config = get_config(reload=False)
        self.config = new_config
        self.xhs_config = new_config.get_xhs_config()
        if not self.xhs_config.profile_ids:
            self.logger.warning("%s 没有配置 profile_id，跳过本次执行", self.monitor_name)
            return

        if self.session:
            self.session.headers["User-Agent"] = XHS_USER_AGENT
            if self.xhs_config.cookie:
                self.session.headers["Cookie"] = self.xhs_config.cookie

        self.logger.debug("开始执行 %s", self.monitor_name)

        if not self.xhs_config.profile_ids:
            self.logger.warning("%s 没有配置 profile_id，跳过本次执行", self.monitor_name)
            return

        semaphore = asyncio.Semaphore(self.xhs_config.concurrency)

        async def process_with_semaphore(pid: str):
            async with semaphore:
                return await self.process_user(pid)

        tasks = [process_with_semaphore(pid) for pid in self.xhs_config.profile_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"处理用户 {self.xhs_config.profile_ids[i]} 时出错: {result}")
        self.logger.debug("执行完成 %s", self.monitor_name)

    @property
    def monitor_name(self) -> str:
        return "小红书动态监控📕  📕  📕"


async def run_xhs_monitor() -> None:
    config = get_config(reload=True)
    logging.getLogger(__name__).debug("小红书监控：已重新加载配置文件")
    async with XhsMonitor(config) as monitor:
        await monitor.run()


def _get_xhs_trigger_kwargs(config: AppConfig) -> dict:
    return {"seconds": config.xhs_monitor_interval_seconds}


from src.jobs.registry import register_monitor

register_monitor(
    "xhs_monitor",
    run_xhs_monitor,
    _get_xhs_trigger_kwargs,
    description="小红书动态监控",
)
