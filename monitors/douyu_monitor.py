"""斗鱼直播监控模块（开播/下播）"""

import asyncio
import json
import logging
from datetime import datetime

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from src.config import AppConfig, get_config, is_in_quiet_hours
from src.monitor import BaseMonitor

DOUYU_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class DouyuMonitor(BaseMonitor):
    """斗鱼直播监控类（开播/下播检测）"""

    def __init__(self, config: AppConfig, session: ClientSession | None = None):
        super().__init__(config, session)
        self.douyu_config = config.get_douyu_config()
        self.old_data_dict: dict[str, tuple] = {}
        self._is_first_time: bool = False

    async def initialize(self):
        await super().initialize()
        await self.load_old_info()

    async def _get_session(self) -> ClientSession:
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": DOUYU_USER_AGENT},
                timeout=ClientTimeout(total=10),
            )
            self._own_session = True
        else:
            self.session.headers["User-Agent"] = DOUYU_USER_AGENT
        return self.session

    async def load_old_info(self):
        try:
            sql = "SELECT room, name, is_live FROM douyu"
            results = await self.db.execute_query(sql)
            self.old_data_dict = {row[0]: row for row in results}
            self._is_first_time = len(self.old_data_dict) == 0
        except Exception as e:
            self.logger.error(f"加载旧数据失败: {e}")
            self.old_data_dict = {}
            self._is_first_time = True

    async def get_info(self, room_id: str) -> dict:
        """获取直播状态"""
        session = await self._get_session()
        url = f"https://www.douyu.com/betard/{room_id}"

        async with session.get(url) as response:
            response.raise_for_status()
            text = await response.text()

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            raise ValueError(f"无法解析斗鱼房间 {room_id} 数据")

        room_info = result.get("room")
        if not room_info:
            raise ValueError(f"斗鱼房间 {room_id} 数据为空")

        username = room_info.get("nickname", "未知")
        show_status = room_info.get("show_status", 0)
        status_num = "1" if show_status == 1 else "0"

        return {
            "room": room_id,
            "name": username,
            "is_live": status_num,
            "room_name": room_info.get("room_name", ""),
            "room_pic": room_info.get("room_pic", ""),
        }

    def check_info(self, data: dict, old_info: tuple) -> int:
        """返回值: 1(开播), 0(下播), 2(无变化)"""
        old_status = str(old_info[2]) if len(old_info) > 2 else "0"
        if str(data["is_live"]) != old_status:
            return 1 if data["is_live"] == "1" else 0
        return 2

    async def process_room(self, room_id: str):
        try:
            data = await self.get_info(room_id)
        except Exception as e:
            self.logger.error(f"获取斗鱼房间 {room_id} 信息失败: {e}")
            return

        if room_id in self.old_data_dict:
            old_info = self.old_data_dict[room_id]
            res = self.check_info(data, old_info)

            if res == 2:
                self.logger.debug(f"{data['name']} 最近直播状态没变化🐟")
            else:
                sql = "UPDATE douyu SET name=%(name)s, is_live=%(is_live)s WHERE room=%(room)s"
                await self.db.execute_update(sql, data)

                status_msg = "开播啦🐟🐟🐟" if res == 1 else "下播了💤💤💤"
                self.logger.info(f"{data['name']} {status_msg}")

                await self.push_notification(data, res)
        else:
            sql = "INSERT INTO douyu (room, name, is_live) VALUES (%(room)s, %(name)s, %(is_live)s)"
            await self.db.execute_insert(sql, data)

            if self._is_first_time:
                self.logger.info(f"新录入主播: {data['name']}（首次创建数据库，跳过推送）")
            else:
                self.logger.info(f"新录入主播: {data['name']}")
                await self.push_notification(data, 1)

    async def push_notification(self, data: dict, res: int):
        if is_in_quiet_hours(self.config):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_text = "开播了🐟🐟🐟" if res == 1 else "下播了💤💤💤"
            self.logger.info(
                f"[免打扰时段] {data['name']} {status_text}（{timestamp}），已跳过推送"
            )
            return

        quote = " "
        try:
            session = await self._get_session()
            async with session.get(
                "https://v1.hitokoto.cn/", timeout=ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    hitokoto = await resp.json()
                    quote = f'\n{hitokoto.get("hitokoto", "")} —— {hitokoto.get("from", "")}\n'
        except Exception as e:
            self.logger.debug(f"[{data['name']}] 获取语录失败: {e}")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_text = "开播了🐟🐟🐟" if res == 1 else "下播了💤💤💤"
        room_title = data.get("room_name", "") or "直播间"
        pic_url = (
            data.get("room_pic")
            or "https://cn.bing.com/th?id=OHR.DolbadarnCastle_ZH-CN5397592090_1920x1080.jpg"
        )

        try:
            await self.push.send_news(
                title=f"{data['name']} {status_text}",
                description=f"房间号: {data['room']}\n标题: {room_title}\n\n{quote}\n\n{timestamp}",
                to_url=f"https://www.douyu.com/{data['room']}",
                picurl=pic_url,
            )
        except Exception as e:
            self.logger.error(f"推送失败: {e}")

    @property
    def platform_name(self) -> str:
        return "douyu"

    @property
    def push_channel_names(self) -> list[str] | None:
        channels = getattr(self.config, "douyu_push_channels", None)
        return channels if channels else None

    async def run(self):
        new_config = get_config(reload=False)
        self.config = new_config
        self.douyu_config = new_config.get_douyu_config()
        if not self.douyu_config.rooms:
            self.logger.warning("%s 没有配置房间号，跳过本次执行", self.monitor_name)
            return

        if self.session:
            self.session.headers["User-Agent"] = DOUYU_USER_AGENT

        self.logger.debug("开始执行 %s", self.monitor_name)

        if not self.douyu_config.rooms:
            self.logger.warning("%s 没有配置房间号，跳过本次执行", self.monitor_name)
            return

        semaphore = asyncio.Semaphore(self.douyu_config.concurrency)

        async def process_with_semaphore(room_id: str):
            async with semaphore:
                return await self.process_room(room_id)

        tasks = [process_with_semaphore(rid) for rid in self.douyu_config.rooms]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"处理房间 {self.douyu_config.rooms[i]} 时出错: {result}")
        self.logger.debug("执行完成 %s", self.monitor_name)

    @property
    def monitor_name(self) -> str:
        return "斗鱼直播监控🐟  🐟  🐟"


async def run_douyu_monitor() -> None:
    config = get_config(reload=True)
    logging.getLogger(__name__).debug("斗鱼监控：已重新加载配置文件")
    async with DouyuMonitor(config) as monitor:
        await monitor.run()


def _get_douyu_trigger_kwargs(config: AppConfig) -> dict:
    return {"seconds": config.douyu_monitor_interval_seconds}


from src.job_registry import register_monitor

register_monitor("douyu_monitor", run_douyu_monitor, _get_douyu_trigger_kwargs)
