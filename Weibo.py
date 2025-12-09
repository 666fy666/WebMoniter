#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Author: Fy
cron: 0 */5 * * * ?
new Env('微博监控');
"""
import time
import requests
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.config import get_config
from utils.conn import OperationMysql
from utils.push import WeChatPub


class WeiBo:
    def __init__(self, config):
        """初始化配置、Session和旧数据"""
        self.config = config
        # 初始化 Session，复用 TCP 连接
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.config.get('User-Agent', 'Mozilla/5.0'),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.weibo.com/",
            "Cookie": os.getenv("weibo", ""),
            "X-Requested-With": "XMLHttpRequest",
        })
        
        # 预先加载旧数据
        self.old_data_dict = self.get_old_info()

    def main(self):
        """主程序入口，使用线程池处理"""
        uids = self.config['weibo']['uid']
        max_workers = 2  # 保持原有的最大并发数

        # 使用线程池替代手动 Thread 和 Queue
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_uid = {executor.submit(self.process_user, uid): uid for uid in uids}
            
            # 等待完成并捕获异常
            for future in as_completed(future_to_uid):
                uid = future_to_uid[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"用户 {uid} 处理出错: {e}")

    def process_user(self, uid):
        """处理单个用户逻辑"""
        # 获取最新数据
        try:
            new_data = self.get_info(uid)
        except Exception as e:
            print(f"获取用户 {uid} 数据失败: {e}")
            return

        # 数据库操作实例 (建议：如果 OperationMysql 不是线程安全的，需在线程内实例化)
        op_mysql = OperationMysql(self.config)

        # 逻辑判断：存在则更新，不存在则插入
        if self.old_data_dict and uid in self.old_data_dict:
            old = self.old_data_dict[uid]
            # 假设数据库顺序: 0:UID, ..., 5:微博数, 6:文本
            old_info = {
                "微博数": old[5],
                "文本": old[6]
            }
            
            diff = self.check_info(new_data, old_info)
            
            if diff == 0:
                print(f"{new_data['用户名']} 最近在摸鱼🐟")
            else:
                # 更新数据
                sql = ('UPDATE weibo SET 用户名=%(用户名)s, 认证信息=%(认证信息)s, 简介=%(简介)s, '
                       '粉丝数=%(粉丝数)s, 微博数=%(微博数)s, 文本=%(文本)s, mid=%(mid)s WHERE UID=%(UID)s')
                op_mysql.updata_one(sql, new_data)
                
                if diff > 0:
                    print(f"{new_data['用户名']} 发布了{diff}条微博😍")
                else:
                    print(f"{new_data['用户名']} 删除了{abs(diff)}条微博😞")
                
                self.push_pro(new_data, diff)
        else:
            # 新用户插入
            sql = ('INSERT INTO weibo (UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid) '
                   'VALUES (%(UID)s, %(用户名)s, %(认证信息)s, %(简介)s, %(粉丝数)s, %(微博数)s, %(文本)s, %(mid)s)')
            op_mysql.insert_one(sql, new_data)
            print(f"{new_data['用户名']} 发布了新微博😍 (新收录)")
            self.push_pro(new_data, 1)

    def check_info(self, data, old_info):
        """比对信息"""
        if data["文本"] != old_info["文本"]:
            # 简单的数值转换容错
            try:
                return int(data["微博数"]) - int(old_info["微博数"])
            except ValueError:
                return 1 # 无法计算时默认有变化
        return 0

    def get_info(self, uid):
        """请求微博网址并解析"""
        info_url = f"https://www.weibo.com/ajax/profile/info?uid={uid}"
        con_url = f"https://www.weibo.com/ajax/statuses/mymblog?uid={uid}&page=1&feature=0"

        # 移除内部多线程，改为复用 Session 的顺序请求
        # 网络延迟通常在 100-300ms，顺序请求只增加极少时间，但极大减少系统开销
        res_info = self.session.get(info_url, timeout=10).json()
        res_list = self.session.get(con_url, timeout=10).json()

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
        # 原逻辑：计算 "isTop" 出现的次数来定位最新非置顶微博的索引
        # 注意：这块逻辑保留原样，但为了稳健性，建议检查 list 是否为空
        wb_list = res_list["data"]["list"]
        if not wb_list:
            data["文本"] = "无内容"
            data["mid"] = "0"
            return data

        # 使用原代码的逻辑计算索引
        # 这里实际上可能比较脆弱，但为了"不改变功能"保留原逻辑思路
        raw_text_content = requests.Response() 
        # 为了兼容原逻辑的 text.count，我们需要 response 的 text，但现在 res_list 是 json dict
        # 我们这里重新模拟原逻辑的计数方式，或者直接遍历 list 找非置顶
        # 优化方案：直接在 JSON 中判断 isTop 字段
        
        target_idx = 0
        for idx, item in enumerate(wb_list):
            # 如果是置顶微博(isTop存在且为1)，则跳过，找下一条
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

    def get_old_info(self):
        """从数据库获取旧的信息"""
        try:
            op_mysql = OperationMysql(self.config)
            sql = "SELECT * FROM weibo"
            old_data = op_mysql.search_one(sql)
            # 转换为字典: {uid: (row_data)}
            if old_data:
                return {user[0]: user for user in old_data}
            return {}
        except Exception as e:
            print(f"读取数据库失败: {e}")
            return {}

    def push_pro(self, data, res):
        """推送到企业微信"""
        action = "发布" if res > 0 else "删除"
        count = abs(res)
        
        wechat = WeChatPub(self.config['push'])
        wechat.send_news(
            title=f"{data['用户名']} {action}了{count}条weibo",
            description=(
                f"Ta说:👇\n{data['文本']}\n"
                f"{'=' * 32}\n"
                f"认证:{data['认证信息']}\n\n"
                f"简介:{data['简介']}"
            ),
            picurl="https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg",
            to_url=f"https://m.weibo.cn/detail/{data['mid']}",
            btntxt='阅读全文'
        )

if __name__ == '__main__':
    start_time = time.perf_counter()

    config = get_config()
    if not config:
        print("配置文件加载失败")
    else:
        weibo = WeiBo(config)
        weibo.main()

    end_time = time.perf_counter()
    print(f"执行时间: {end_time - start_time:.6f} 秒")