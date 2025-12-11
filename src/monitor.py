"""监控任务基类 - 提供可扩展的监控框架"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional

import aiohttp
from aiohttp import ClientSession

from src.config import AppConfig
from src.database import AsyncDatabase
from src.push import AsyncWeChatPush


class BaseMonitor(ABC):
    """监控任务基类 - 所有监控任务都应该继承此类"""

    def __init__(self, config: AppConfig, session: Optional[ClientSession] = None):
        """
        初始化监控器
        
        Args:
            config: 应用配置
            session: 可选的HTTP会话（用于共享连接）
        """
        self.config = config
        self.session = session
        self._own_session = False
        self.db: Optional[AsyncDatabase] = None
        self.push: Optional[AsyncWeChatPush] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def _get_session(self) -> ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
            self._own_session = True
        return self.session

    async def initialize(self):
        """初始化数据库和推送服务"""
        self.db = AsyncDatabase()
        await self.db.initialize()

        session = await self._get_session()
        self.push = AsyncWeChatPush(self.config.get_wechat_config(), session)

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

