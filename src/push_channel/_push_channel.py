import logging
from abc import ABC, abstractmethod

from aiohttp import ClientSession, ClientTimeout


class PushChannel(ABC):
    """推送通道基类 - 所有推送通道都应该继承此类"""

    def __init__(self, config, session: ClientSession | None = None):
        """
        初始化推送通道

        Args:
            config: 配置字典
            session: 可选的 HTTP 会话（用于共享连接）
        """
        self.name = config.get("name", "")
        self.enable = config.get("enable", False)
        self.type = config.get("type", "")
        self.session = session
        self._own_session = False
        self.logger = logging.getLogger(self.__class__.__name__)

    async def _get_session(self) -> ClientSession:
        """获取或创建 HTTP 会话"""
        if self.session is None:
            self.session = ClientSession(timeout=ClientTimeout(total=10))
            self._own_session = True
        return self.session

    async def close(self):
        """关闭资源"""
        if self._own_session and self.session:
            await self.session.close()
            self.session = None

    @abstractmethod
    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """
        推送消息（异步方法）

        Args:
            title: 标题
            content: 内容
            jump_url: 跳转url
            pic_url: 图片url
            extend_data: 扩展数据
        """
        raise NotImplementedError("Subclasses must implement the push method")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
