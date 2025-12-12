"""监控任务基类 - 提供可扩展的监控框架"""

import logging
from abc import ABC, abstractmethod

import aiohttp
from aiohttp import ClientSession

from src.config import AppConfig
from src.database import AsyncDatabase
from src.push_channel import get_push_channel
from src.push_channel.manager import UnifiedPushManager


class BaseMonitor(ABC):
    """监控任务基类 - 所有监控任务都应该继承此类"""

    def __init__(self, config: AppConfig, session: ClientSession | None = None):
        """
        初始化监控器

        Args:
            config: 应用配置
            session: 可选的HTTP会话（用于共享连接）
        """
        self.config = config
        self.session = session
        self._own_session = False
        self.db: AsyncDatabase | None = None
        self.push: UnifiedPushManager | None = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def _get_session(self) -> ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
            self._own_session = True
        return self.session

    async def initialize(self):
        """初始化数据库和推送服务"""
        self.db = AsyncDatabase()
        await self.db.initialize()

        session = await self._get_session()

        # 初始化推送通道（新格式）
        push_channels = []
        if self.config.push_channel_list:
            for channel_config in self.config.push_channel_list:
                # 只处理启用的通道
                if not channel_config.get("enable", False):
                    continue

                try:
                    channel = get_push_channel(channel_config, session)
                    push_channels.append(channel)
                    # 对于需要初始化的通道（如QQBot），执行初始化
                    if hasattr(channel, "initialize"):
                        await channel.initialize()
                except Exception as e:
                    self.logger.warning(
                        f"推送通道 {channel_config.get('name', '未知')} 初始化失败: {e}"
                    )

        # 创建统一的推送管理器
        if push_channels:
            self.push = UnifiedPushManager(push_channels, session)
        else:
            self.logger.warning("未配置任何推送通道，推送功能将不可用")

    async def close(self):
        """关闭资源"""
        if self.db:
            await self.db.close()
        if self.push:
            await self.push.close()
        if self._own_session and self.session:
            await self.session.close()

    @abstractmethod
    async def run(self):
        """
        运行监控任务 - 子类必须实现此方法

        此方法应该包含监控的核心逻辑
        """
        pass

    @property
    @abstractmethod
    def monitor_name(self) -> str:
        """
        监控器名称 - 用于日志和标识

        Returns:
            监控器名称，如 "虎牙直播监控"、"微博监控"
        """
        pass

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
