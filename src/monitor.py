"""监控任务基类 - 提供可扩展的监控框架"""

import logging
from abc import ABC, abstractmethod

import aiohttp
from aiohttp import ClientSession

from src.config import AppConfig
from src.cookie_cache import get_cookie_cache
from src.database import AsyncDatabase
from src.push_channel.manager import UnifiedPushManager, build_push_manager

cookie_cache = get_cookie_cache()


class CookieExpiredError(Exception):
    """Cookie 失效异常，由各平台监控在检测到需重新登录时抛出。"""

    pass


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
        self.push = await build_push_manager(self.config.push_channel_list, session, self.logger)
        if self.push is None:
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

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """
        平台名称 - 用于Cookie缓存标识

        Returns:
            平台名称，如 "huya"、"weibo"
        """
        pass

    async def handle_cookie_expired(self, error: CookieExpiredError) -> None:
        """
        处理Cookie过期 - 统一处理逻辑，子类可重写以自定义行为

        Args:
            error: Cookie过期异常
        """
        platform = self.platform_name
        self.logger.error(f"检测到Cookie失效: {error}")
        await cookie_cache.mark_expired(platform)

        # 只有在未发送过提醒时才发送
        if not cookie_cache.is_notified(platform):
            await self.push_cookie_expired_notification()
            await cookie_cache.mark_notified(platform)

    async def mark_cookie_valid(self) -> None:
        """标记Cookie为有效状态"""
        platform = self.platform_name
        if not cookie_cache.is_valid(platform):
            await cookie_cache.mark_valid(platform)
            self.logger.info(f"{self.monitor_name} Cookie已恢复有效")

    async def push_cookie_expired_notification(self) -> None:
        """
        发送Cookie失效提醒 - 子类应重写此方法以提供平台特定的通知内容

        默认实现为空，子类应提供具体的通知标题、描述和链接
        """
        if not self.push:
            self.logger.warning("推送服务未初始化，无法发送Cookie失效提醒")
            return

        # 默认实现，子类应重写
        self.logger.warning(f"{self.monitor_name} Cookie失效提醒未实现")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
