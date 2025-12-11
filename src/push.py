"""推送模块 - 支持企业微信、PushPlus、邮件等多种推送方式"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import aiohttp
import aiosmtplib
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

        # 异步锁保护并发访问
        self._lock = asyncio.Lock()

    def _cleanup_old_records(self, records: list[float], max_age: float):
        """清理过期记录"""
        current_time = time.time()
        return [ts for ts in records if current_time - ts < max_age]

    async def can_send(self, user: str) -> tuple[bool, Optional[str]]:
        """
        检查是否可以发送消息（异步方法，带锁保护）
        返回: (是否可以发送, 错误信息)
        """
        async with self._lock:
            current_time = time.time()

            # 清理过期记录
            self._minute_records[user] = self._cleanup_old_records(self._minute_records[user], 60)
            self._hour_records[user] = self._cleanup_old_records(self._hour_records[user], 3600)
            self._day_records[user] = self._cleanup_old_records(self._day_records[user], 86400)

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

    async def record_send(self, user: str):
        """记录发送操作（异步方法，带锁保护）"""
        async with self._lock:
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
        self.logger = logging.getLogger(self.__class__.__name__)

        # 推送队列
        self._push_queue: asyncio.Queue[PushTask] = asyncio.Queue()
        self._queue_processor_task: Optional[asyncio.Task] = None
        self._processing = False
        self._queue_lock = asyncio.Lock()  # 保护队列处理器启动

    async def _get_session(self) -> ClientSession:
        """获取或创建session"""
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=ClientTimeout(total=10))
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

    async def _start_queue_processor(self):
        """启动队列处理器（带锁保护，避免重复启动）"""
        async with self._queue_lock:
            if self._queue_processor_task is None or self._queue_processor_task.done():
                self._processing = True
                self._queue_processor_task = asyncio.create_task(self._process_queue())
                self.logger.debug("队列处理器已启动")

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
                    self.logger.info(f"[队列] 成功发送: {task.title[:30]}...")
                except Exception as e:
                    # 发送失败，增加重试次数
                    task.retry_count += 1
                    if task.retry_count < task.max_retries:
                        # 重新放入队列，稍后重试
                        await asyncio.sleep(5)  # 等待5秒后重试
                        await self._push_queue.put(task)
                        self.logger.warning(
                            f"[队列] 发送失败，将重试 ({task.retry_count}/{task.max_retries}): {e}"
                        )
                    else:
                        self.logger.error(f"[队列] 发送失败，已达最大重试次数: {task.title[:30]}...")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"[队列处理器] 错误: {e}")
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
            self.logger.error(f"获取企业微信token失败: {e}")
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
            can_send, error_msg = await self._rate_limiter.can_send(user)
            if not can_send:
                if not from_queue:  # 只有非队列调用才记录日志
                    self.logger.debug(f"用户 {user} 推送被限制: {error_msg}")
                blocked_users.append(user)
                continue
            # 记录发送
            await self._rate_limiter.record_send(user)
            allowed_users.append(user)

        if blocked_users and not from_queue:
            self.logger.debug(f"以下用户推送被频率限制阻止: {blocked_users}")

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
            url,
            data=json.dumps(form_data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
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
        await self._start_queue_processor()

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
                self.logger.info(f"[队列] 推送任务已加入队列: {title[:30]}...")
                return {"errcode": 0, "errmsg": "已加入队列，稍后发送"}
            else:
                # 其他错误，直接抛出
                self.logger.error(f"推送失败: {e}")
                raise

    async def wait_queue_empty(self, timeout: Optional[float] = None):
        """等待队列为空（用于程序结束时）"""
        start_time = time.time()
        while not self._push_queue.empty():
            if timeout and (time.time() - start_time) > timeout:
                self.logger.warning(f"[队列] 等待超时，仍有 {self._push_queue.qsize()} 个任务未处理")
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


class AsyncPushPlusPush:
    """异步 PushPlus 推送类"""

    def __init__(self, token: str, session: Optional[ClientSession] = None):
        """
        初始化 PushPlus 推送

        Args:
            token: PushPlus token
            session: 可选的 HTTP 会话
        """
        self.token = token
        self.session = session
        self._own_session = False
        self.api_url = "http://www.pushplus.plus/send"
        self.logger = logging.getLogger(self.__class__.__name__)

    async def _get_session(self) -> ClientSession:
        """获取或创建session"""
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=ClientTimeout(total=10))
            self._own_session = True
        return self.session

    async def close(self):
        """关闭session"""
        if self._own_session and self.session:
            await self.session.close()
            self.session = None

    async def send_news(
        self,
        title: str,
        description: str,
        to_url: str,
        picurl: str = "",
        btntxt: str = "阅读全文",
        author: str = "FengYu",
        **kwargs,
    ) -> dict:
        """
        发送消息到 PushPlus

        Args:
            title: 标题
            description: 内容描述
            to_url: 跳转链接
            picurl: 图片URL（可选）
            btntxt: 按钮文本
            author: 作者
        """
        session = await self._get_session()

        # 构建消息内容（HTML格式）
        content = f"""
        <div style="font-family: Arial, sans-serif;">
            <h2>{title}</h2>
            <p style="white-space: pre-wrap;">{description}</p>
            {f'<img src="{picurl}" alt="图片" style="max-width: 100%;" />' if picurl else ''}
            <p><a href="{to_url}" style="display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">{btntxt}</a></p>
            <p style="color: #666; font-size: 12px;">作者: {author}</p>
        </div>
        """

        payload = {
            "token": self.token,
            "title": title,
            "content": content,
            "template": "html",
        }

        try:
            async with session.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:
                response.raise_for_status()
                result = await response.json()

                if result.get("code") != 200:
                    error_msg = result.get("msg", "未知错误")
                    raise Exception(f"PushPlus推送失败: {error_msg}")

                return result
        except Exception as e:
            self.logger.error(f"PushPlus推送失败: {e}")
            raise

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


class AsyncEmailPush:
    """异步邮件推送类"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_email: str,
        to_email: str,
        use_tls: bool = True,
    ):
        """
        初始化邮件推送

        Args:
            smtp_host: SMTP服务器地址
            smtp_port: SMTP端口
            smtp_user: SMTP用户名
            smtp_password: SMTP密码
            from_email: 发件人邮箱
            to_email: 收件人邮箱
            use_tls: 是否使用TLS加密
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.to_email = to_email
        self.use_tls = use_tls
        self.logger = logging.getLogger(self.__class__.__name__)

    async def send_news(
        self,
        title: str,
        description: str,
        to_url: str,
        picurl: str = "",
        btntxt: str = "阅读全文",
        author: str = "FengYu",
        **kwargs,
    ) -> dict:
        """
        发送邮件

        Args:
            title: 标题
            description: 内容描述
            to_url: 跳转链接
            picurl: 图片URL（可选）
            btntxt: 按钮文本
            author: 作者
        """
        # 构建HTML邮件内容
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                h2 {{
                    color: #007bff;
                    border-bottom: 2px solid #007bff;
                    padding-bottom: 10px;
                }}
                .content {{
                    white-space: pre-wrap;
                    margin: 20px 0;
                }}
                .image {{
                    max-width: 100%;
                    height: auto;
                    margin: 20px 0;
                }}
                .button {{
                    display: inline-block;
                    padding: 12px 24px;
                    background-color: #007bff;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                .footer {{
                    color: #666;
                    font-size: 12px;
                    margin-top: 30px;
                    border-top: 1px solid #eee;
                    padding-top: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>{title}</h2>
                <div class="content">{description}</div>
                {f'<img src="{picurl}" alt="图片" class="image" />' if picurl else ''}
                <a href="{to_url}" class="button">{btntxt}</a>
                <div class="footer">
                    <p>作者: {author}</p>
                    <p>发送时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                </div>
            </div>
        </body>
        </html>
        """

        # 构建纯文本内容（作为备选）
        text_content = f"""
{title}

{description}

{to_url}

作者: {author}
发送时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        """

        # 创建邮件消息
        message = MIMEMultipart("alternative")
        message["Subject"] = title
        message["From"] = self.from_email
        message["To"] = self.to_email

        # 添加文本和HTML部分
        text_part = MIMEText(text_content, "plain", "utf-8")
        html_part = MIMEText(html_content, "html", "utf-8")
        message.attach(text_part)
        message.attach(html_part)

        try:
            # 对于 465 端口（SSL），使用 SMTP_SSL；对于 587 端口（TLS），使用 SMTP + start_tls
            if self.smtp_port == 465:
                # SSL 连接（465端口）
                smtp_client = aiosmtplib.SMTP(
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    use_tls=True,  # SSL 连接
                )
            else:
                # TLS 连接（587端口或其他）
                smtp_client = aiosmtplib.SMTP(
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    use_tls=False,
                )

            await smtp_client.connect()
            
            # 如果需要 TLS（587端口），启动 TLS
            if self.use_tls and self.smtp_port != 465:
                await smtp_client.starttls()
            
            # 登录
            await smtp_client.login(self.smtp_user, self.smtp_password)
            
            # 发送邮件
            await smtp_client.send_message(message)
            
            # 关闭连接
            await smtp_client.quit()
            
            return {"status": "success", "message": "邮件发送成功"}
        except Exception as e:
            self.logger.error(f"邮件推送失败: {e}")
            raise

    async def close(self):
        """关闭连接（邮件推送无需保持连接）"""
        pass

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


class UnifiedPushManager:
    """统一的推送管理器 - 支持多种推送方式同时发送"""

    def __init__(
        self,
        wechat_push: Optional[AsyncWeChatPush] = None,
        pushplus_push: Optional[AsyncPushPlusPush] = None,
        email_push: Optional[AsyncEmailPush] = None,
    ):
        """
        初始化推送管理器

        Args:
            wechat_push: 企业微信推送实例（可选）
            pushplus_push: PushPlus推送实例（可选）
            email_push: 邮件推送实例（可选）
        """
        self.wechat_push = wechat_push
        self.pushplus_push = pushplus_push
        self.email_push = email_push

    async def send_news(
        self,
        title: str,
        description: str,
        to_url: str,
        picurl: str = "",
        btntxt: str = "阅读全文",
        author: str = "FengYu",
        **kwargs,
    ) -> dict:
        """
        发送消息到所有配置的推送渠道

        Args:
            title: 标题
            description: 内容描述
            to_url: 跳转链接
            picurl: 图片URL
            btntxt: 按钮文本
            author: 作者

        Returns:
            包含所有推送结果的字典
        """
        results = {}
        errors = []

        # 并发发送到所有渠道
        tasks = []
        channel_names = []

        if self.wechat_push:
            channel_names.append("wechat")
            tasks.append(
                self._send_with_error_handling(
                    "wechat", self.wechat_push.send_news, title, description, to_url, picurl, btntxt, author
                )
            )

        if self.pushplus_push:
            channel_names.append("pushplus")
            tasks.append(
                self._send_with_error_handling(
                    "pushplus", self.pushplus_push.send_news, title, description, to_url, picurl, btntxt, author
                )
            )

        if self.email_push:
            channel_names.append("email")
            tasks.append(
                self._send_with_error_handling(
                    "email", self.email_push.send_news, title, description, to_url, picurl, btntxt, author
                )
            )

        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(task_results):
                channel_name = channel_names[i]
                if isinstance(result, Exception):
                    errors.append(f"{channel_name}: {str(result)}")
                else:
                    results[channel_name] = result
        else:
            raise Exception("未配置任何推送渠道")

        if errors:
            logger = logging.getLogger(self.__class__.__name__)
            logger.warning(f"部分推送失败: {errors}")

        return {"results": results, "errors": errors}

    def _has_channel(self, channel: str) -> bool:
        """检查是否配置了指定渠道"""
        if channel == "wechat":
            return self.wechat_push is not None
        elif channel == "pushplus":
            return self.pushplus_push is not None
        elif channel == "email":
            return self.email_push is not None
        return False

    async def _send_with_error_handling(
        self, channel_name: str, send_func, title: str, description: str, to_url: str, picurl: str, btntxt: str, author: str
    ):
        """带错误处理的发送包装器"""
        try:
            return await send_func(
                title=title,
                description=description,
                to_url=to_url,
                picurl=picurl,
                btntxt=btntxt,
                author=author,
            )
        except Exception as e:
            raise Exception(f"{channel_name}推送失败: {e}")

    async def close(self):
        """关闭所有推送服务"""
        if self.wechat_push:
            await self.wechat_push.close()
        if self.pushplus_push:
            await self.pushplus_push.close()
        if self.email_push:
            await self.email_push.close()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
