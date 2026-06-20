"""哔哩哔哩监控模块（动态 + 开播/下播）"""

import asyncio
import logging
import time
from collections import deque

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from src.jobs.registry import register_monitor
from src.monitors.base import BaseMonitor
from src.settings.config import AppConfig, get_config, is_in_quiet_hours

BILIBILI_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEQUE_LEN = 5


class BilibiliMonitor(BaseMonitor):
    """哔哩哔哩监控类（动态检测 + 开播/下播检测）"""

    def __init__(self, config: AppConfig, session: ClientSession | None = None):
        super().__init__(config, session)
        self.bilibili_config = config.get_bilibili_config()
        self.old_dynamic_dict: dict[str, deque] = {}
        self.old_live_dict: dict[str, tuple] = {}
        self._is_first_time_dynamic: bool = False
        self._is_first_time_live: bool = False
        self._buvid3: str | None = None

    async def initialize(self):
        await super().initialize()
        await self.load_old_info()

    async def _get_session(self) -> ClientSession:
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={
                    "User-Agent": BILIBILI_USER_AGENT,
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://space.bilibili.com/",
                },
                timeout=ClientTimeout(total=15),
            )
            self._own_session = True
        else:
            self.session.headers["User-Agent"] = BILIBILI_USER_AGENT
        return self.session

    async def load_old_info(self):
        try:
            # 动态
            sql = "SELECT uid, uname, dynamic_id, dynamic_text FROM bilibili_dynamic"
            results = await self.db.execute_query(sql)
            self.old_dynamic_dict = {}
            for row in results:
                uid, _, dynamic_id, _ = row[0], row[1], row[2], row[3]
                self.old_dynamic_dict[uid] = deque(maxlen=DEQUE_LEN)
                if dynamic_id:
                    self.old_dynamic_dict[uid].append(dynamic_id)
            self._is_first_time_dynamic = len(self.old_dynamic_dict) == 0

            # 直播
            sql = "SELECT uid, uname, room_id, is_live FROM bilibili_live"
            results = await self.db.execute_query(sql)
            self.old_live_dict = {row[0]: row for row in results}
            self._is_first_time_live = len(self.old_live_dict) == 0
        except Exception as e:
            self.logger.error(f"加载旧数据失败: {e}")
            self.old_dynamic_dict = {}
            self.old_live_dict = {}
            self._is_first_time_dynamic = True
            self._is_first_time_live = True

    async def _get_buvid3(self) -> str | None:
        """获取 buvid3（可选）"""
        if self._buvid3:
            return self._buvid3
        try:
            session = await self._get_session()
            url = "https://api.bilibili.com/x/frontend/finger/spi"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._buvid3 = (data.get("data") or {}).get("b_3", "")
                    return self._buvid3
        except Exception as e:
            self.logger.debug(f"获取 buvid3 失败: {e}")
        return None

    async def query_dynamic(self, uid: str):
        """查询动态"""
        session = await self._get_session()
        ts = int(time.time())
        url = (
            f"https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
            f"?host_mid={uid}&offset=&my_ts={ts}&features=itemOpusStyle"
        )
        headers = {"Referer": f"https://space.bilibili.com/{uid}/dynamic"}
        if self.bilibili_config.cookie:
            headers["Cookie"] = self.bilibili_config.cookie
        buvid3 = await self._get_buvid3()
        if buvid3:
            cookie = headers.get("Cookie", "")
            headers["Cookie"] = f"buvid3={buvid3};{cookie}" if cookie else f"buvid3={buvid3}"

        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                raise ValueError(f"B站动态请求失败: {resp.status}")
            data = await resp.json()

        if data.get("code") != 0:
            if data.get("code") == -352:
                self.logger.warning(f"B站 UID {uid} 触发 -352，可配置 cookie 或 payload")
            raise ValueError(f"B站动态返回错误: {data.get('message', '')}")

        items = (data.get("data") or {}).get("items") or []
        items = [
            it
            for it in items
            if (it.get("modules") or {}).get("module_tag") is None
            or (it.get("modules") or {}).get("module_tag", {}).get("text") != "置顶"
        ]
        if not items:
            return

        item = items[0]
        dynamic_id = item.get("id_str", "")
        modules = item.get("modules") or {}
        author = modules.get("module_author") or {}
        uname = author.get("name", "未知")

        if uid not in self.old_dynamic_dict:
            self.old_dynamic_dict[uid] = deque(maxlen=DEQUE_LEN)
            for i in range(min(DEQUE_LEN, len(items))):
                self.old_dynamic_dict[uid].appendleft(items[i].get("id_str", ""))
            self.logger.info(f"【B站-{uname}】动态初始化")
            sql = (
                "INSERT OR REPLACE INTO bilibili_dynamic "
                "(uid, uname, dynamic_id, dynamic_text) VALUES (%(uid)s, %(uname)s, %(dynamic_id)s, %(dynamic_text)s)"
            )
            await self.db.execute_update(
                sql,
                {
                    "uid": uid,
                    "uname": uname,
                    "dynamic_id": dynamic_id,
                    "dynamic_text": "",
                },
            )
            return

        if dynamic_id in self.old_dynamic_dict[uid]:
            return

        # 新动态
        allow_types = [
            "DYNAMIC_TYPE_DRAW",
            "DYNAMIC_TYPE_WORD",
            "DYNAMIC_TYPE_AV",
            "DYNAMIC_TYPE_ARTICLE",
            "DYNAMIC_TYPE_COMMON_SQUARE",
        ]
        if not self.bilibili_config.skip_forward:
            allow_types.append("DYNAMIC_TYPE_FORWARD")
        dynamic_type = item.get("type", "")
        if dynamic_type not in allow_types:
            self.logger.debug(f"【B站-{uname}】动态类型 {dynamic_type} 跳过推送")
            self.old_dynamic_dict[uid].append(dynamic_id)
            await self.db.execute_update(
                "UPDATE bilibili_dynamic SET dynamic_id=%(dynamic_id)s WHERE uid=%(uid)s",
                {"uid": uid, "dynamic_id": dynamic_id},
            )
            return

        module_dynamic = modules.get("module_dynamic") or {}
        major = module_dynamic.get("major") or {}
        content = ""
        pic_url = ""
        title_msg = "发动态了"
        if dynamic_type == "DYNAMIC_TYPE_FORWARD":
            content = (module_dynamic.get("desc") or {}).get("text", "")
            title_msg = "转发了动态"
        elif dynamic_type == "DYNAMIC_TYPE_DRAW":
            opus = major.get("opus") or {}
            content = (opus.get("summary") or {}).get("text", "")
            pics = opus.get("pics") or []
            pic_url = pics[0].get("url", "") if pics else ""
        elif dynamic_type == "DYNAMIC_TYPE_AV":
            archive = major.get("archive") or {}
            content = archive.get("title", "")
            pic_url = archive.get("cover", "")
            title_msg = "投稿了"
        elif dynamic_type == "DYNAMIC_TYPE_ARTICLE":
            opus = major.get("opus") or {}
            content = opus.get("title", "")
            pics = opus.get("pics") or []
            pic_url = pics[0].get("url", "") if pics else ""
            title_msg = "投稿了"

        self.old_dynamic_dict[uid].append(dynamic_id)
        sql = (
            "UPDATE bilibili_dynamic SET uname=%(uname)s, dynamic_id=%(dynamic_id)s, dynamic_text=%(dynamic_text)s "
            "WHERE uid=%(uid)s"
        )
        await self.db.execute_update(
            sql,
            {
                "uid": uid,
                "uname": uname,
                "dynamic_id": dynamic_id,
                "dynamic_text": content[:200],
            },
        )

        self.logger.info(f"【B站-{uname}】{title_msg}📺")
        if not self._is_first_time_dynamic:
            await self._push_dynamic(uname, dynamic_id, content, pic_url, title_msg)

    async def _push_dynamic(
        self, uname: str, dynamic_id: str, content: str, pic_url: str, title_msg: str
    ):
        if is_in_quiet_hours(self.config):
            return
        try:
            await self.send_push_news(
                title=f"【B站】【{uname}】{title_msg}",
                description=f"{content[:100]}{'...' if len(content) > 100 else ''}",
                to_url=f"https://www.bilibili.com/opus/{dynamic_id}",
                picurl=pic_url
                or "https://cn.bing.com/th?id=OHR.DolbadarnCastle_ZH-CN5397592090_1920x1080.jpg",
                event_type="bilibili_dynamic",
                event_data={
                    "uname": uname,
                    "dynamic_id": dynamic_id,
                    "content": content[:300],
                    "title_msg": title_msg,
                },
            )
        except Exception as e:
            self.logger.error(f"推送失败: {e}")

    async def query_live(self, uid: str):
        """查询直播状态"""
        session = await self._get_session()
        url = "https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids"
        headers = {"Content-Type": "application/json"}
        if self.bilibili_config.cookie:
            headers["Cookie"] = self.bilibili_config.cookie

        async with session.post(url, headers=headers, json={"uids": [int(uid)]}) as resp:
            if resp.status != 200:
                raise ValueError(f"B站直播请求失败: {resp.status}")
            data = await resp.json()

        if data.get("code") != 0:
            raise ValueError(f"B站直播返回错误: {data.get('message', '')}")

        live_list = data.get("data") or {}
        if uid not in live_list:
            return
        item = live_list[uid]
        uname = item.get("uname", "未知")
        live_status = item.get("live_status", 0)
        room_id = item.get("room_id", "")
        room_title = item.get("title", "")
        room_cover = item.get("cover_from_user", "")
        status_num = "1" if live_status == 1 else "0"

        if uid not in self.old_live_dict:
            self.old_live_dict[uid] = ("", "", "", status_num)
            sql = (
                "INSERT OR REPLACE INTO bilibili_live (uid, uname, room_id, is_live) "
                "VALUES (%(uid)s, %(uname)s, %(room_id)s, %(is_live)s)"
            )
            await self.db.execute_update(
                sql,
                {
                    "uid": uid,
                    "uname": uname,
                    "room_id": str(room_id),
                    "is_live": status_num,
                },
            )
            self.logger.info(f"【B站-{uname}】直播初始化")
            return

        old = self.old_live_dict[uid]
        old_status = old[3] if len(old) > 3 else "0"
        if status_num == old_status:
            return

        self.old_live_dict[uid] = (uid, uname, str(room_id), status_num)
        sql = (
            "UPDATE bilibili_live SET uname=%(uname)s, room_id=%(room_id)s, is_live=%(is_live)s "
            "WHERE uid=%(uid)s"
        )
        await self.db.execute_update(
            sql,
            {
                "uid": uid,
                "uname": uname,
                "room_id": str(room_id),
                "is_live": status_num,
            },
        )

        res = 1 if status_num == "1" else 0
        status_msg = "开播啦📺📺📺" if res == 1 else "下播了💤💤💤"
        self.logger.info(f"【B站-{uname}】{status_msg}")

        if not self._is_first_time_live:
            await self._push_live(uname, room_id, room_title, room_cover, res)

    async def _push_live(
        self, uname: str, room_id: str, room_title: str, room_cover: str, res: int
    ):
        if is_in_quiet_hours(self.config):
            return
        status_text = "开播了📺📺📺" if res == 1 else "下播了💤💤💤"
        pic = (
            room_cover
            or "https://cn.bing.com/th?id=OHR.DolbadarnCastle_ZH-CN5397592090_1920x1080.jpg"
        )
        try:
            await self.send_push_news(
                title=f"【B站】【{uname}】{status_text}",
                description=room_title or "直播间",
                to_url=f"https://live.bilibili.com/{room_id}",
                picurl=pic,
                event_type="bilibili_live",
                event_data={
                    "uname": uname,
                    "room_id": room_id,
                    "room_title": room_title,
                    "is_live": res == 1,
                    "status_text": "开播" if res == 1 else "下播",
                },
            )
        except Exception as e:
            self.logger.error(f"推送失败: {e}")

    @property
    def platform_name(self) -> str:
        return "bilibili"

    @property
    def push_channel_names(self) -> list[str] | None:
        channels = getattr(self.config, "bilibili_push_channels", None)
        return channels if channels else None

    async def run(self):
        new_config = get_config(reload=False)
        self.config = new_config
        self.bilibili_config = new_config.get_bilibili_config()
        if not self.bilibili_config.uids:
            self.logger.warning("%s 没有配置 UID，跳过本次执行", self.monitor_name)
            return

        if self.session:
            self.session.headers["User-Agent"] = BILIBILI_USER_AGENT

        self.logger.debug("开始执行 %s", self.monitor_name)

        semaphore = asyncio.Semaphore(self.bilibili_config.concurrency)

        async def process_uid(uid: str):
            async with semaphore:
                errors = []
                try:
                    await self.query_dynamic(uid)
                except Exception as e:
                    errors.append(f"动态:{e}")
                await asyncio.sleep(1)
                try:
                    await self.query_live(uid)
                except Exception as e:
                    errors.append(f"直播:{e}")
                if errors:
                    self.logger.warning(f"UID {uid}: {' '.join(errors)}")

        tasks = [process_uid(uid) for uid in self.bilibili_config.uids]
        await asyncio.gather(*tasks, return_exceptions=True)
        self.logger.debug("执行完成 %s", self.monitor_name)

    @property
    def monitor_name(self) -> str:
        return "哔哩哔哩监控📺  📺  📺"


async def run_bilibili_monitor() -> None:
    config = get_config(reload=True)
    logging.getLogger(__name__).debug("哔哩哔哩监控：已重新加载配置文件")
    async with BilibiliMonitor(config) as monitor:
        await monitor.run()


def _get_bilibili_trigger_kwargs(config: AppConfig) -> dict:
    return {"seconds": config.bilibili_monitor_interval_seconds}


register_monitor(
    "bilibili_monitor",
    run_bilibili_monitor,
    _get_bilibili_trigger_kwargs,
    description="哔哩哔哩动态+直播监控",
)
