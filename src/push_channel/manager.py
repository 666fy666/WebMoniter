"""统一推送管理器 - 支持所有推送通道"""

import asyncio
import logging

from aiohttp import ClientSession


class UnifiedPushManager:
    """统一的推送管理器 - 支持多种推送方式同时发送"""

    def __init__(self, push_channels: list, session: ClientSession | None = None):
        """
        初始化推送管理器

        Args:
            push_channels: 推送通道实例列表
            session: 可选的 HTTP 会话（用于共享连接）
        """
        self.push_channels = push_channels
        self.session = session
        self.logger = logging.getLogger(self.__class__.__name__)

    async def send_news(
        self,
        title: str,
        description: str,
        to_url: str,
        picurl: str = "",
        btntxt: str = "阅读全文",
        author: str = "FengYu",
        description_func=None,
        **kwargs,
    ) -> dict:
        """
        发送消息到所有配置的推送渠道

        Args:
            title: 标题
            description: 内容描述（默认值，如果 description_func 不为 None，则会被忽略）
            to_url: 跳转链接
            picurl: 图片URL
            btntxt: 按钮文本
            author: 作者
            description_func: 可选的函数，接收 channel 参数，返回该通道的 description

        Returns:
            包含所有推送结果的字典
        """
        results = {}
        errors = []

        # 过滤出启用的通道
        enabled_channels = [ch for ch in self.push_channels if ch.enable]

        if not enabled_channels:
            self.logger.warning("未配置任何启用的推送渠道")
            return {"results": results, "errors": errors}

        # 并发发送到所有渠道
        tasks = []
        channel_names = []

        for channel in enabled_channels:
            channel_names.append(channel.name)
            # 如果提供了 description_func，则使用它来生成该通道的 description
            channel_description = description_func(channel) if description_func else description
            tasks.append(
                self._send_with_error_handling(
                    channel,
                    title,
                    channel_description,
                    to_url,
                    picurl,
                    btntxt,
                    author,
                )
            )

        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(task_results):
                channel_name = channel_names[i]
                if isinstance(result, Exception):
                    errors.append(f"{channel_name}: {str(result)}")
                    self.logger.error(f"推送通道 {channel_name} 失败: {result}")
                else:
                    results[channel_name] = result

        if errors:
            self.logger.warning(f"部分推送失败: {errors}")

        return {"results": results, "errors": errors}

    async def _send_with_error_handling(
        self,
        channel,
        title: str,
        description: str,
        to_url: str,
        picurl: str,
        btntxt: str,
        author: str,
    ):
        """带错误处理的发送包装器"""
        try:
            # 将 send_news 的参数转换为 push 方法的参数
            # description 作为 content，to_url 作为 jump_url，picurl 作为 pic_url
            await channel.push(
                title=title,
                content=description,
                jump_url=to_url,
                pic_url=picurl if picurl else None,
                extend_data={"btntxt": btntxt, "author": author},
            )
            return {"status": "success"}
        except Exception as e:
            raise Exception(f"{channel.name}推送失败: {e}")

    async def close(self):
        """关闭所有推送服务"""
        for channel in self.push_channels:
            try:
                await channel.close()
            except Exception as e:
                self.logger.error(f"关闭推送通道 {channel.name} 失败: {e}")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
