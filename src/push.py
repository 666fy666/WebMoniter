"""企业微信推送模块 - 带频率限制和队列"""
import asyncio
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from src.config import WeChatConfig


@dataclass
class PushTask:
    """推送任务"""
    title: str
    description: str
    to_url: str
    picurl: str
    btntxt: str = "阅读全文"
    author: str = "FengYu"
    created_at: float = field(default_factory=time.time)
    retry_count: int = 0
    max_retries: int = 3


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
    """异步企业微信推送类 - 支持队列"""

    def __init__(self, config: WeChatConfig, session: Optional[ClientSession] = None):
        self.config = config
        self.session = session
        self._token: Optional[str] = None
        self._token_expires_at: float = 0
        self._rate_limiter = RateLimiter()
        self._own_session = False
        
        # 推送队列
        self._push_queue: asyncio.Queue[PushTask] = asyncio.Queue()
        self._queue_processor_task: Optional[asyncio.Task] = None
        self._processing = False

    async def _get_session(self) -> ClientSession:
        """获取或创建session"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=ClientTimeout(total=10)
            )
            self._own_session = True
        return self.session

    async def close(self):
        """关闭session和队列处理器"""
        self._processing = False
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass
        
        if self._own_session and self.session:
            await self.session.close()
            self.session = None

    def _start_queue_processor(self):
        """启动队列处理器"""
        if self._queue_processor_task is None or self._queue_processor_task.done():
            self._processing = True
            self._queue_processor_task = asyncio.create_task(self._process_queue())

    async def _process_queue(self):
        """处理推送队列"""
        while self._processing:
            try:
                # 等待队列中有任务，或者超时
                try:
                    task = await asyncio.wait_for(self._push_queue.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    continue

                # 尝试发送
                try:
                    await self._send_news_internal(
                        title=task.title,
                        description=task.description,
                        to_url=task.to_url,
                        picurl=task.picurl,
                        btntxt=task.btntxt,
                        author=task.author,
                        from_queue=True,
                    )
                    print(f"[队列] 成功发送: {task.title[:30]}...")
                except Exception as e:
                    # 发送失败，增加重试次数
                    task.retry_count += 1
                    if task.retry_count < task.max_retries:
                        # 重新放入队列，稍后重试
                        await asyncio.sleep(5)  # 等待5秒后重试
                        await self._push_queue.put(task)
                        print(f"[队列] 发送失败，将重试 ({task.retry_count}/{task.max_retries}): {e}")
                    else:
                        print(f"[队列] 发送失败，已达最大重试次数: {task.title[:30]}...")

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[队列处理器] 错误: {e}")
                await asyncio.sleep(1)

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

    async def _send_news_internal(
        self,
        title: str,
        description: str,
        to_url: str,
        picurl: str,
        btntxt: str = "阅读全文",
        author: str = "FengYu",
        from_queue: bool = False,
    ) -> dict:
        """内部发送方法"""
        users = [u.strip() for u in self.config.touser.split("|") if u.strip()]

        # 检查每个用户的频率限制
        allowed_users = []
        blocked_users = []
        for user in users:
            can_send, error_msg = self._rate_limiter.can_send(user)
            if not can_send:
                if not from_queue:  # 只有非队列调用才打印
                    print(f"用户 {user} 推送被限制: {error_msg}")
                blocked_users.append(user)
                continue
            # 记录发送
            self._rate_limiter.record_send(user)
            allowed_users.append(user)

        if blocked_users and not from_queue:
            print(f"以下用户推送被频率限制阻止: {blocked_users}")

        # 如果所有用户都被阻止，抛出异常（让队列处理器重试）
        if not allowed_users:
            raise Exception(f"所有用户都被频率限制阻止: {blocked_users}")

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

        async with session.post(
            url, data=json.dumps(form_data).encode("utf-8"), headers={"Content-Type": "application/json"}
        ) as response:
            response.raise_for_status()
            result = await response.json()

            if result.get("errcode") != 0:
                error_msg = result.get("errmsg", "未知错误")
                raise Exception(f"推送失败: {error_msg}")

            return result

    async def send_news(
        self,
        title: str,
        description: str,
        to_url: str,
        picurl: str,
        btntxt: str = "阅读全文",
        author: str = "FengYu",
        queue_if_blocked: bool = True,
    ) -> dict:
        """
        发送图文消息
        
        Args:
            queue_if_blocked: 如果被频率限制阻止，是否放入队列
        """
        # 启动队列处理器
        self._start_queue_processor()

        try:
            # 尝试直接发送
            return await self._send_news_internal(
                title=title,
                description=description,
                to_url=to_url,
                picurl=picurl,
                btntxt=btntxt,
                author=author,
                from_queue=False,
            )
        except Exception as e:
            # 如果被频率限制阻止且允许入队
            if queue_if_blocked and ("频率限制" in str(e) or "都被频率限制阻止" in str(e)):
                # 创建推送任务并放入队列
                task = PushTask(
                    title=title,
                    description=description,
                    to_url=to_url,
                    picurl=picurl,
                    btntxt=btntxt,
                    author=author,
                )
                await self._push_queue.put(task)
                print(f"[队列] 推送任务已加入队列: {title[:30]}...")
                return {"errcode": 0, "errmsg": "已加入队列，稍后发送"}
            else:
                # 其他错误，直接抛出
                print(f"推送失败: {e}")
                raise

    async def wait_queue_empty(self, timeout: Optional[float] = None):
        """等待队列为空（用于程序结束时）"""
        start_time = time.time()
        while not self._push_queue.empty():
            if timeout and (time.time() - start_time) > timeout:
                print(f"[队列] 等待超时，仍有 {self._push_queue.qsize()} 个任务未处理")
                break
            await asyncio.sleep(0.5)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        # 等待队列处理完成（最多等待30秒）
        await self.wait_queue_empty(timeout=30)
        await self.close()

