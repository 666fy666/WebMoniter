"""企业微信推送模块 - 带频率限制"""
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from src.config import WeChatConfig


class RateLimiter:
    """频率限制器 - 实现企业微信推送频率限制"""

    def __init__(self):
        # 每分钟每个用户的发送次数记录 {user: [timestamp1, timestamp2, ...]}
        self._minute_records: dict[str, list[float]] = defaultdict(list)
        # 每小时每个用户的发送次数记录
        self._hour_records: dict[str, list[float]] = defaultdict(list)
        # 每天每个用户的发送次数记录
        self._day_records: dict[str, list[float]] = defaultdict(list)

        # 限制阈值
        self.MINUTE_LIMIT = 30  # 每分钟30次
        self.HOUR_LIMIT = 1000  # 每小时1000次
        self.DAY_LIMIT = 200  # 每天200次（假设账号上限为1，实际应该乘以账号上限数）

    def _cleanup_old_records(self, records: list[float], max_age: float):
        """清理过期记录"""
        current_time = time.time()
        return [ts for ts in records if current_time - ts < max_age]

    def can_send(self, user: str) -> tuple[bool, Optional[str]]:
        """
        检查是否可以发送消息
        返回: (是否可以发送, 错误信息)
        """
        current_time = time.time()

        # 清理过期记录
        self._minute_records[user] = self._cleanup_old_records(
            self._minute_records[user], 60
        )
        self._hour_records[user] = self._cleanup_old_records(
            self._hour_records[user], 3600
        )
        self._day_records[user] = self._cleanup_old_records(
            self._day_records[user], 86400
        )

        # 检查分钟限制
        if len(self._minute_records[user]) >= self.MINUTE_LIMIT:
            return (
                False,
                f"超过分钟限制: {self.MINUTE_LIMIT}次/分钟",
            )

        # 检查小时限制
        if len(self._hour_records[user]) >= self.HOUR_LIMIT:
            return (
                False,
                f"超过小时限制: {self.HOUR_LIMIT}次/小时",
            )

        # 检查天限制
        if len(self._day_records[user]) >= self.DAY_LIMIT:
            return (
                False,
                f"超过天限制: {self.DAY_LIMIT}次/天",
            )

        return True, None

    def record_send(self, user: str):
        """记录发送操作"""
        current_time = time.time()
        self._minute_records[user].append(current_time)
        self._hour_records[user].append(current_time)
        self._day_records[user].append(current_time)


class AsyncWeChatPush:
    """异步企业微信推送类"""

    def __init__(self, config: WeChatConfig, session: Optional[ClientSession] = None):
        self.config = config
        self.session = session
        self._token: Optional[str] = None
        self._token_expires_at: float = 0
        self._rate_limiter = RateLimiter()
        self._own_session = False

    async def _get_session(self) -> ClientSession:
        """获取或创建session"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=ClientTimeout(total=10)
            )
            self._own_session = True
        return self.session

    async def close(self):
        """关闭session（如果是自己创建的）"""
        if self._own_session and self.session:
            await self.session.close()
            self.session = None

    async def get_token(self) -> str:
        """获取或刷新access_token"""
        current_time = time.time()

        # 如果token还有效（提前5分钟刷新），直接返回
        if self._token and current_time < self._token_expires_at - 300:
            return self._token

        session = await self._get_session()
        url = (
            f"https://qyapi.weixin.qq.com/cgi-bin/gettoken"
            f"?corpid={self.config.corpid}&corpsecret={self.config.secret}"
        )

        try:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()

                if data.get("errcode") != 0:
                    raise Exception(f"获取token失败: {data.get('errmsg', '未知错误')}")

                self._token = data["access_token"]
                # token有效期通常是7200秒，这里设置为7000秒以提前刷新
                self._token_expires_at = current_time + 7000
                return self._token

        except Exception as e:
            print(f"获取企业微信token失败: {e}")
            raise

    async def send_news(
        self,
        title: str,
        description: str,
        to_url: str,
        picurl: str,
        btntxt: str = "阅读全文",
        author: str = "FengYu",
    ) -> dict:
        """
        发送图文消息
        注意：touser可能包含多个用户（用|分隔），需要分别检查频率限制
        """
        users = [u.strip() for u in self.config.touser.split("|") if u.strip()]

        # 检查每个用户的频率限制
        allowed_users = []
        blocked_users = []
        for user in users:
            can_send, error_msg = self._rate_limiter.can_send(user)
            if not can_send:
                print(f"用户 {user} 推送被限制: {error_msg}")
                blocked_users.append(user)
                continue
            # 记录发送
            self._rate_limiter.record_send(user)
            allowed_users.append(user)

        if blocked_users:
            print(f"以下用户推送被频率限制阻止: {blocked_users}")

        # 如果所有用户都被阻止，直接返回
        if not allowed_users:
            return {"errcode": -1, "errmsg": "所有用户都被频率限制阻止"}

        token = await self.get_token()
        session = await self._get_session()

        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"

        # 只发送给允许的用户
        touser_str = "|".join(allowed_users)

        form_data = {
            "touser": touser_str,
            "toparty": "",
            "msgtype": "news",
            "agentid": self.config.agentid,
            "news": {
                "articles": [
                    {
                        "title": title,
                        "description": description,
                        "url": to_url,
                        "author": author,
                        "picurl": picurl,
                        "btntxt": btntxt,
                    }
                ]
            },
            "enable_id_trans": 0,
            "enable_duplicate_check": 0,
            "duplicate_check_interval": 1800,
        }

        try:
            async with session.post(
                url, data=json.dumps(form_data).encode("utf-8"), headers={"Content-Type": "application/json"}
            ) as response:
                response.raise_for_status()
                result = await response.json()

                if result.get("errcode") != 0:
                    print(f"推送失败: {result.get('errmsg', '未知错误')}")
                    return result

                return result

        except Exception as e:
            print(f"推送请求失败: {e}")
            raise

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

