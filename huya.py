#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Author: Fy
cron: 50 */1 * * * ?
new Env('虎牙直播监控');
"""
import json
import re
import time
import asyncio
from datetime import datetime

import aiohttp
from utils.config import get_config
from utils.conn import OperationMysql
from utils.push import WeChatPub


class HuYaMonitor:
    # 预编译正则，提升匹配效率
    RE_PROFILE = re.compile(r'"tProfileInfo":({.*?})')
    RE_STATUS = re.compile(r'"eLiveStatus":(\d+)')

    def __init__(self, config):
        """配置文件初始化"""
        self.config = config
        self.old_data_dict = self.get_old_info()  # 从数据库获取老信息
        
        # 统一请求头
        self.headers = {
            'Content-Type': self.config['hy'].get('Content-Type', 'application/json'),
            'User-Agent': self.config['hy'].get('User-Agent', 'Mozilla/5.0'),
            'Cookie': self.config['hy'].get('Cookie', '')
        }

    async def main(self):
        """主程序入口, 维护唯一的Session以复用连接"""
        room_ids = self.config['hy']['room']
        
        # 创建一个 session 供整个生命周期使用
        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = [self.process_user(session, room_id) for room_id in room_ids]
            await asyncio.gather(*tasks)

    async def process_user(self, session, room_id):
        """处理单个用户"""
        try:
            data = await self.get_info(session, room_id)
        except Exception as e:
            print(f"获取房间 {room_id} 信息失败: {e}")
            return

        # 数据库操作对象 (假设OperationMysql是同步的，此处为简便未做线程池封装)
        op_mysql = OperationMysql(self.config)

        # 显式判断是否存在旧数据
        if self.old_data_dict and room_id in self.old_data_dict:
            old = self.old_data_dict[room_id]
            # 假设数据库顺序: 0:room, 1:name, 2:is_live
            old_info = {
                "room": old[0],
                "name": old[1],
                "is_live": old[2]
            }
            
            res = self.check_info(data, old_info)
            
            if res == 2:
                print(f"{data['name']} 最近直播状态没变化🐟")
            else:
                # 状态发生变化 (1:开播, 0:下播)
                sql = 'UPDATE huya SET name=%(name)s, is_live=%(is_live)s WHERE room=%(room)s'
                op_mysql.updata_one(sql, data)
                
                status_msg = "开播啦🐯🐯🐯" if res == 1 else "下播了🐟🐟🐟"
                print(f"{data['name']} {status_msg}")
                
                # 传递 session 进行异步推送
                await self.push_pro(session, data, res)
        else:
            # 新录入逻辑
            sql = 'INSERT INTO huya (room, name, is_live) VALUES (%(room)s, %(name)s, %(is_live)s)'
            op_mysql.insert_one(sql, data)
            print(f"新录入主播: {data['name']}")
            # 新录入通常默认为开播推送，或根据实际业务需求调整
            await self.push_pro(session, data, 1)

    async def get_info(self, session, room_id):
        """获取直播状态并处理"""
        url = f'https://m.huya.com/{room_id}'
        async with session.get(url) as response:
            response.raise_for_status()
            page_content = await response.text()

        # 使用预编译正则匹配
        profile_match = self.RE_PROFILE.search(page_content)
        status_match = self.RE_STATUS.search(page_content)

        if not profile_match or not status_match:
            raise ValueError(f"无法解析页面数据: {room_id}")

        profile_info = json.loads(profile_match.group(1))
        live_status = int(status_match.group(1))

        # 直播状态转换: 2代表正在直播 -> 存为 "1"，否则 "0"
        status_num = "1" if live_status == 2 else "0"
        
        data = {
            "room": room_id,
            "name": profile_info["sNick"],
            "is_live": status_num
        }
        return data

    def get_old_info(self):
        """从数据库获取旧的信息"""
        try:
            op_mysql = OperationMysql(self.config)
            sql = "SELECT * FROM huya"
            old_data = op_mysql.search_one(sql)
            if old_data:
                return {user[0]: user for user in old_data}
            return {}
        except Exception as e:
            print(f"数据库读取失败: {e}")
            return {}

    def check_info(self, data, old_info):
        """比对信息, 返回值: 1(开播), 0(下播), 2(无变化)"""
        # 确保数据类型一致进行比较
        if str(data["is_live"]) != str(old_info["is_live"]):
            return 1 if data["is_live"] == "1" else 0
        return 2

    async def push_pro(self, session, data, res):
        """发送微信通知，异步获取语录"""
        quote = ' '
        try:
            # 使用 aiohttp 异步获取语录，不再阻塞主流程
            async with session.get("https://v1.hitokoto.cn/", timeout=3) as resp:
                if resp.status == 200:
                    hitokoto = await resp.json()
                    quote = f'\n{hitokoto.get("hitokoto", "")} —— {hitokoto.get("from", "")}\n'
        except Exception as e:
            print(f"[{data['name']}] 获取语录失败: {e}")

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status_text = "开播了🐯🐯🐯" if res == 1 else "下播了🐟🐟🐟"

        # WeChatPub 依然是同步发送（假设它是requests实现的），放在最后执行
        # 如果追求极致性能，可以将 WeChatPub 改写为 async，或者放入 run_in_executor
        try:
            WeChatPub(self.config['push']).send_news(
                title=f'{data["name"]} {status_text}',
                description=f'房间号: {data["room"]}\n\n{quote}\n\n{timestamp}',
                to_url=f'https://m.huya.com/{data["room"]}',
                picurl="https://cn.bing.com/th?id=OHR.DolbadarnCastle_ZH-CN5397592090_1920x1080.jpg"
            )
        except Exception as e:
            print(f"推送失败: {e}")

if __name__ == '__main__':
    start_time = time.perf_counter()

    config = get_config()
    if config:
        hu_ya = HuYaMonitor(config)
        # 使用标准的 asyncio.run (Python 3.7+)
        asyncio.run(hu_ya.main())
    else:
        print("配置文件加载失败")

    end_time = time.perf_counter()
    print(f"执行时间: {end_time - start_time:.6f} 秒")