#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: Fy
cron: 50 */1 * * * ?
new Env('虎牙直播监控');
"""
import asyncio
import json
import re
import time
from datetime import datetime
from typing import Optional

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from src.config import get_config, AppConfig
from src.database import AsyncDatabase
from src.push import AsyncWeChatPush

# 预编译正则表达式
RE_PROFILE = re.compile(r'"tProfileInfo":({.*?})')
RE_STATUS = re.compile(r'"eLiveStatus":(\d+)')


class HuyaMonitor:
    """虎牙直播监控类"""

    def __init__(self, config: AppConfig, session: Optional[ClientSession] = None):
        self.config = config
        self.huya_config = config.get_huya_config()
        self.session = session
        self._own_session = False
        self.db: Optional[AsyncDatabase] = None
        self.push: Optional[AsyncWeChatPush] = None
        self.old_data_dict: dict[str, tuple] = {}

    async def _get_session(self) -> ClientSession:
        """获取或创建session"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={
                    "User-Agent": self.huya_config.user_agent,
                    "Cookie": self.huya_config.cookie,
                },
                timeout=ClientTimeout(total=10),
            )
            self._own_session = True
        return self.session

    async def initialize(self):
        """初始化数据库和推送服务"""
        self.db = AsyncDatabase(self.config.get_database_config())
        await self.db.initialize()

        session = await self._get_session()
        self.push = AsyncWeChatPush(self.config.get_wechat_config(), session)

        # 加载旧数据
        await self.load_old_info()

    async def close(self):
        """关闭资源"""
        if self.db:
            await self.db.close()
        if self.push:
            await self.push.close()
        if self._own_session and self.session:
            await self.session.close()

    async def load_old_info(self):
        """从数据库加载旧信息"""
        try:
            sql = "SELECT room, name, is_live FROM huya"
            results = await self.db.execute_query(sql)
            self.old_data_dict = {row[0]: row for row in results}
        except Exception as e:
            print(f"加载旧数据失败: {e}")
            self.old_data_dict = {}

    async def get_info(self, room_id: str) -> dict:
        """获取直播状态"""
        session = await self._get_session()
        url = f"https://m.huya.com/{room_id}"

        async with session.get(url) as response:
            response.raise_for_status()
            page_content = await response.text()

        # 使用预编译正则匹配
        profile_match = RE_PROFILE.search(page_content)
        status_match = RE_STATUS.search(page_content)

        if not profile_match or not status_match:
            raise ValueError(f"无法解析页面数据: {room_id}")

        profile_info = json.loads(profile_match.group(1))
        live_status = int(status_match.group(1))

        # 直播状态转换: 2代表正在直播 -> 存为 "1"，否则 "0"
        status_num = "1" if live_status == 2 else "0"

        return {
            "room": room_id,
            "name": profile_info["sNick"],
            "is_live": status_num,
        }

    def check_info(self, data: dict, old_info: tuple) -> int:
        """
        比对信息
        返回值: 1(开播), 0(下播), 2(无变化)
        """
        old_status = str(old_info[2]) if len(old_info) > 2 else "0"
        if str(data["is_live"]) != old_status:
            return 1 if data["is_live"] == "1" else 0
        return 2

    async def process_room(self, room_id: str):
        """处理单个房间"""
        try:
            data = await self.get_info(room_id)
        except Exception as e:
            print(f"获取房间 {room_id} 信息失败: {e}")
            return

        if room_id in self.old_data_dict:
            old_info = self.old_data_dict[room_id]
            res = self.check_info(data, old_info)

            if res == 2:
                print(f"{data['name']} 最近直播状态没变化🐟")
            else:
                # 状态发生变化
                sql = "UPDATE huya SET name=%(name)s, is_live=%(is_live)s WHERE room=%(room)s"
                await self.db.execute_update(sql, data)

                status_msg = "开播啦🐯🐯🐯" if res == 1 else "下播了🐟🐟🐟"
                print(f"{data['name']} {status_msg}")

                await self.push_notification(data, res)
        else:
            # 新录入
            sql = "INSERT INTO huya (room, name, is_live) VALUES (%(room)s, %(name)s, %(is_live)s)"
            await self.db.execute_insert(sql, data)
            print(f"新录入主播: {data['name']}")
            await self.push_notification(data, 1)

    async def push_notification(self, data: dict, res: int):
        """发送推送通知"""
        # 异步获取语录
        quote = " "
        try:
            session = await self._get_session()
            async with session.get("https://v1.hitokoto.cn/", timeout=ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    hitokoto = await resp.json()
                    quote = f'\n{hitokoto.get("hitokoto", "")} —— {hitokoto.get("from", "")}\n'
        except Exception as e:
            print(f"[{data['name']}] 获取语录失败: {e}")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_text = "开播了🐯🐯🐯" if res == 1 else "下播了🐟🐟🐟"

        try:
            await self.push.send_news(
                title=f"{data['name']} {status_text}",
                description=f"房间号: {data['room']}\n\n{quote}\n\n{timestamp}",
                to_url=f"https://m.huya.com/{data['room']}",
                picurl="https://cn.bing.com/th?id=OHR.DolbadarnCastle_ZH-CN5397592090_1920x1080.jpg",
            )
        except Exception as e:
            print(f"推送失败: {e}")

    async def run(self):
        """运行监控"""
        await self.initialize()
        try:
            # 创建信号量控制并发数
            semaphore = asyncio.Semaphore(self.huya_config.concurrency)
            
            async def process_with_semaphore(room_id: str):
                """使用信号量包装的处理函数"""
                async with semaphore:
                    return await self.process_room(room_id)
            
            tasks = [
                process_with_semaphore(room_id) for room_id in self.huya_config.rooms
            ]
            await asyncio.gather(*tasks)
        finally:
            await self.close()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


async def main():
    """主函数"""
    start_time = time.perf_counter()

    try:
        config = get_config()
    except Exception as e:
        print(f"配置加载失败: {e}")
        print("请确保已创建.env文件并配置了必要的环境变量")
        print("参考.env.example文件")
        return

    print("=" * 50)
    print("开始虎牙直播监控")
    print("=" * 50)

    async with HuyaMonitor(config) as monitor:
        await monitor.run()

    end_time = time.perf_counter()
    print(f"\n执行时间: {end_time - start_time:.6f} 秒")


if __name__ == "__main__":
    asyncio.run(main())
