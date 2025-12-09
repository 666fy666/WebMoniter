#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: Fy
cron: 0 */5 * * * ?
new Env('微博监控');
"""
import asyncio
import time
from typing import Optional

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from src.config import get_config, AppConfig
from src.database import AsyncDatabase
from src.push import AsyncWeChatPush


class WeiboMonitor:
    """微博监控类"""

    def __init__(self, config: AppConfig, session: Optional[ClientSession] = None):
        self.config = config
        self.weibo_config = config.get_weibo_config()
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
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://www.weibo.com/",
                    "Cookie": self.weibo_config.cookie,
                    "X-Requested-With": "XMLHttpRequest",
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
            sql = "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid FROM weibo"
            results = await self.db.execute_query(sql)
            self.old_data_dict = {row[0]: row for row in results}
        except Exception as e:
            print(f"加载旧数据失败: {e}")
            self.old_data_dict = {}

    async def get_info(self, uid: str) -> dict:
        """获取微博信息"""
        session = await self._get_session()
        info_url = f"https://www.weibo.com/ajax/profile/info?uid={uid}"
        con_url = f"https://www.weibo.com/ajax/statuses/mymblog?uid={uid}&page=1&feature=0"

        # 并发请求两个接口
        async with session.get(info_url) as info_resp, session.get(con_url) as con_resp:
            info_resp.raise_for_status()
            con_resp.raise_for_status()

            res_info = await info_resp.json()
            res_list = await con_resp.json()

        # 解析用户信息
        user_info = res_info["data"]["user"]
        data = {
            "UID": user_info["idstr"],
            "用户名": user_info["screen_name"],
            "认证信息": user_info.get("verified_reason", "人气博主"),
            "简介": user_info["description"] if user_info["description"] else "peace and love",
            "粉丝数": user_info["followers_count_str"],
            "微博数": str(user_info["statuses_count"]),
        }

        # 解析最新微博内容
        wb_list = res_list["data"]["list"]
        if not wb_list:
            data["文本"] = "无内容"
            data["mid"] = "0"
            return data

        # 找到第一个非置顶微博
        target_idx = 0
        for idx, item in enumerate(wb_list):
            if item.get("isTop", 0) == 1:
                continue
            else:
                target_idx = idx
                break

        target_wb = wb_list[target_idx]

        spacing = "\n          "
        text = "          " + target_wb["text_raw"]

        # 图片处理
        pic_ids = target_wb.get("pic_ids", [])
        if pic_ids:
            text += f"{spacing}[图片]  *  {len(pic_ids)}      (详情请点击噢!)"

        # URL 结构处理
        url_struct = target_wb.get("url_struct", [])
        if url_struct:
            text += f"{spacing}#{url_struct[0]['url_title']}#"

        text += f"{spacing}                {target_wb['created_at']}"

        data["文本"] = text
        data["mid"] = str(target_wb["mid"])

        return data

    def check_info(self, data: dict, old_info: tuple) -> int:
        """
        比对信息
        返回差值：正数表示新增，负数表示删除，0表示无变化
        """
        if len(old_info) < 7:
            return 1  # 数据不完整，默认有变化

        old_text = old_info[6] if len(old_info) > 6 else ""
        if data["文本"] != old_text:
            try:
                old_count = int(old_info[5]) if len(old_info) > 5 else 0
                new_count = int(data["微博数"])
                return new_count - old_count
            except (ValueError, TypeError):
                return 1  # 无法计算时默认有变化
        return 0

    async def process_user(self, uid: str):
        """处理单个用户"""
        try:
            new_data = await self.get_info(uid)
        except Exception as e:
            print(f"获取用户 {uid} 数据失败: {e}")
            return

        if uid in self.old_data_dict:
            old_info = self.old_data_dict[uid]
            diff = self.check_info(new_data, old_info)

            if diff == 0:
                print(f"{new_data['用户名']} 最近在摸鱼🐟")
            else:
                # 更新数据
                sql = (
                    "UPDATE weibo SET 用户名=%(用户名)s, 认证信息=%(认证信息)s, 简介=%(简介)s, "
                    "粉丝数=%(粉丝数)s, 微博数=%(微博数)s, 文本=%(文本)s, mid=%(mid)s WHERE UID=%(UID)s"
                )
                await self.db.execute_update(sql, new_data)

                if diff > 0:
                    print(f"{new_data['用户名']} 发布了{diff}条微博😍")
                else:
                    print(f"{new_data['用户名']} 删除了{abs(diff)}条微博😞")

                await self.push_notification(new_data, diff)
        else:
            # 新用户插入
            sql = (
                "INSERT INTO weibo (UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid) "
                "VALUES (%(UID)s, %(用户名)s, %(认证信息)s, %(简介)s, %(粉丝数)s, %(微博数)s, %(文本)s, %(mid)s)"
            )
            await self.db.execute_insert(sql, new_data)
            print(f"{new_data['用户名']} 发布了新微博😍 (新收录)")
            await self.push_notification(new_data, 1)

    async def push_notification(self, data: dict, diff: int):
        """发送推送通知"""
        action = "发布" if diff > 0 else "删除"
        count = abs(diff)

        try:
            await self.push.send_news(
                title=f"{data['用户名']} {action}了{count}条weibo",
                description=(
                    f"Ta说:👇\n{data['文本']}\n"
                    f"{'=' * 32}\n"
                    f"认证:{data['认证信息']}\n\n"
                    f"简介:{data['简介']}"
                ),
                picurl="https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg",
                to_url=f"https://m.weibo.cn/detail/{data['mid']}",
                btntxt="阅读全文",
            )
        except Exception as e:
            print(f"推送失败: {e}")

    async def run(self):
        """运行监控"""
        await self.initialize()
        try:
            tasks = [self.process_user(uid) for uid in self.weibo_config.uids]
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
    print("开始微博监控")
    print("=" * 50)

    async with WeiboMonitor(config) as monitor:
        await monitor.run()

    end_time = time.perf_counter()
    print(f"\n执行时间: {end_time - start_time:.6f} 秒")


if __name__ == "__main__":
    asyncio.run(main())
