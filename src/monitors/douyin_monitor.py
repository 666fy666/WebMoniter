"""抖音直播监控模块（开播/下播）"""

import asyncio
import json
import logging
from datetime import datetime

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from src.core.http import fetch_hitokoto_quote
from src.monitors.base import BaseMonitor
from src.settings.config import AppConfig, get_config, is_in_quiet_hours

DOUYIN_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class DouyinMonitor(BaseMonitor):
    """抖音直播监控类（开播/下播检测）"""

    def __init__(self, config: AppConfig, session: ClientSession | None = None):
        super().__init__(config, session)
        self.douyin_config = config.get_douyin_config()
        self.old_data_dict: dict[str, tuple] = {}
        self._is_first_time: bool = False
        self._ttwid: str | None = None

    async def initialize(self):
        await super().initialize()
        await self.load_old_info()
        await self._init_ttwid()

    async def _init_ttwid(self):
        """获取 ttwid（可选，提高成功率）"""
        try:
            session = await self._get_session()
            url = "https://ttwid.bytedance.com/ttwid/union/register/"
            body = {
                "region": "cn",
                "aid": 1768,
                "needFid": False,
                "service": "www.ixigua.com",
                "migrate_info": {"ticket": "", "source": "node"},
                "cbUrlProtocol": "https",
                "union": True,
            }
            async with session.post(url, json=body) as resp:
                if resp.status == 200:
                    for cookie in resp.cookies.values():
                        if cookie.key == "ttwid":
                            self._ttwid = cookie.value
                            self.logger.debug("获取 ttwid 成功")
                            return
        except Exception as e:
            self.logger.debug(f"获取 ttwid 失败（可忽略）: {e}")

    async def _get_session(self) -> ClientSession:
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={
                    "User-Agent": DOUYIN_USER_AGENT,
                    "Accept": "application/json",
                    "Referer": "https://live.douyin.com/",
                },
                timeout=ClientTimeout(total=10),
            )
            self._own_session = True
        else:
            self.session.headers["User-Agent"] = DOUYIN_USER_AGENT
        return self.session

    async def load_old_info(self):
        try:
            sql = "SELECT douyin_id, name, is_live FROM douyin"
            results = await self.db.execute_query(sql)
            self.old_data_dict = {row[0]: row for row in results}
            self._is_first_time = len(self.old_data_dict) == 0
        except Exception as e:
            self.logger.error(f"加载旧数据失败: {e}")
            self.old_data_dict = {}
            self._is_first_time = True

    async def get_info(self, douyin_id: str) -> dict:
        """获取直播状态"""
        session = await self._get_session()
        url = "https://live.douyin.com/webcast/room/web/enter/"

        params = {
            "aid": "6383",
            "device_platform": "web",
            "enter_from": "web_live",
            "cookie_enabled": "true",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Chrome",
            "browser_version": "120.0.0.0",
            "web_rid": douyin_id,
        }

        headers = {"Referer": "https://live.douyin.com/"}
        if self._ttwid:
            headers["Cookie"] = f"ttwid={self._ttwid}"

        async with session.get(url, params=params, headers=headers) as response:
            response.raise_for_status()
            text = await response.text()

        if not text:
            raise ValueError(f"抖音 {douyin_id} 返回为空")

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            raise ValueError(f"无法解析抖音 {douyin_id} 数据")

        if result.get("status_code") != 0:
            raise ValueError(f"抖音 {douyin_id} 返回错误: {result.get('message', '')}")

        data = result.get("data")
        if not data:
            raise ValueError(f"抖音 {douyin_id} 未开通直播")

        room_datas = data.get("data") or []
        if not room_datas:
            raise ValueError(f"抖音 {douyin_id} 疑似未开通直播间")

        room_data = room_datas[0]
        room_status = data.get("room_status", 2)
        user_info = data.get("user") or {}
        nickname = user_info.get("nickname", "未知")

        # room_status: 0=直播中, 2=未开播
        status_num = "1" if room_status == 0 else "0"

        room_title = room_data.get("title", "")
        room_cover = room_data.get("cover") or {}
        cover_list = room_cover.get("url_list") or []
        room_pic = cover_list[0] if cover_list else ""

        return {
            "douyin_id": douyin_id,
            "name": nickname,
            "is_live": status_num,
            "room_title": room_title,
            "room_pic": room_pic,
        }

    def check_info(self, data: dict, old_info: tuple) -> int:
        """返回值: 1(开播), 0(下播), 2(无变化)"""
        old_status = str(old_info[2]) if len(old_info) > 2 else "0"
        if str(data["is_live"]) != old_status:
            return 1 if data["is_live"] == "1" else 0
        return 2

    async def process_room(self, douyin_id: str):
        try:
            data = await self.get_info(douyin_id)
        except Exception as e:
            self.logger.error(f"获取抖音 {douyin_id} 信息失败: {e}")
            return

        if douyin_id in self.old_data_dict:
            old_info = self.old_data_dict[douyin_id]
            res = self.check_info(data, old_info)

            if res == 2:
                self.logger.debug(f"{data['name']} 最近直播状态没变化🐟")
            else:
                sql = (
                    "UPDATE douyin SET name=%(name)s, is_live=%(is_live)s "
                    "WHERE douyin_id=%(douyin_id)s"
                )
                await self.db.execute_update(sql, data)

                status_msg = "开播啦🎬🎬🎬" if res == 1 else "下播了💤💤💤"
                self.logger.info(f"{data['name']} {status_msg}")

                await self.push_notification(data, res)
        else:
            sql = (
                "INSERT INTO douyin (douyin_id, name, is_live) "
                "VALUES (%(douyin_id)s, %(name)s, %(is_live)s)"
            )
            await self.db.execute_insert(sql, data)

            if self._is_first_time:
                self.logger.info(f"新录入主播: {data['name']}（首次创建数据库，跳过推送）")
            else:
                self.logger.info(f"新录入主播: {data['name']}")
                await self.push_notification(data, 1)

    async def push_notification(self, data: dict, res: int):
        if is_in_quiet_hours(self.config):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_text = "开播了🎬🎬🎬" if res == 1 else "下播了💤💤💤"
            self.logger.info(
                f"[免打扰时段] {data['name']} {status_text}（{timestamp}），已跳过推送"
            )
            return

        quote = await fetch_hitokoto_quote(await self._get_session())

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_text = "开播了🎬🎬🎬" if res == 1 else "下播了💤💤💤"
        room_title = data.get("room_title", "") or "直播间"
        pic_url = (
            data.get("room_pic")
            or "https://cn.bing.com/th?id=OHR.DolbadarnCastle_ZH-CN5397592090_1920x1080.jpg"
        )

        try:
            await self.send_push_news(
                title=f"{data['name']} {status_text}",
                description=(
                    f"抖音号: {data['douyin_id']}\n" f"标题: {room_title}\n\n{quote}\n\n{timestamp}"
                ),
                to_url=f"https://live.douyin.com/{data['douyin_id']}",
                picurl=pic_url,
            )
        except Exception as e:
            self.logger.error(f"推送失败: {e}")

    @property
    def platform_name(self) -> str:
        return "douyin"

    @property
    def push_channel_names(self) -> list[str] | None:
        channels = getattr(self.config, "douyin_push_channels", None)
        return channels if channels else None

    async def run(self):
        new_config = get_config(reload=False)
        self.config = new_config
        self.douyin_config = new_config.get_douyin_config()
        if not self.douyin_config.douyin_ids:
            self.logger.warning("%s 没有配置抖音号，跳过本次执行", self.monitor_name)
            return

        if self.session:
            self.session.headers["User-Agent"] = DOUYIN_USER_AGENT

        self.logger.debug("开始执行 %s", self.monitor_name)

        semaphore = asyncio.Semaphore(self.douyin_config.concurrency)

        async def process_with_semaphore(did: str):
            async with semaphore:
                return await self.process_room(did)

        tasks = [process_with_semaphore(did) for did in self.douyin_config.douyin_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"处理 {self.douyin_config.douyin_ids[i]} 时出错: {result}")
        self.logger.debug("执行完成 %s", self.monitor_name)

    @property
    def monitor_name(self) -> str:
        return "抖音直播监控🎬  🎬  🎬"


async def run_douyin_monitor() -> None:
    config = get_config(reload=True)
    logging.getLogger(__name__).debug("抖音监控：已重新加载配置文件")
    async with DouyinMonitor(config) as monitor:
        await monitor.run()


def _get_douyin_trigger_kwargs(config: AppConfig) -> dict:
    return {"seconds": config.douyin_monitor_interval_seconds}


from src.jobs.registry import register_monitor

register_monitor(
    "douyin_monitor",
    run_douyin_monitor,
    _get_douyin_trigger_kwargs,
    description="抖音直播状态监控",
)
