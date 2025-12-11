"""监控任务基类 - 提供可扩展的监控框架"""

import logging
from abc import ABC, abstractmethod

import aiohttp
from aiohttp import ClientSession

from src.config import AppConfig
from src.database import AsyncDatabase
from src.push import (
    AsyncEmailPush,
    AsyncPushPlusPush,
    AsyncWeChatPush,
    UnifiedPushManager,
)


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

        # 初始化各种推送方式
        wechat_push = None
        pushplus_push = None
        email_push = None

        # 企业微信推送
        if self.config.wechat_enabled:
            try:
                wechat_config = self.config.get_wechat_config()
                wechat_push = AsyncWeChatPush(wechat_config, session)
            except Exception as e:
                self.logger.warning(f"企业微信推送初始化失败: {e}")
        else:
            self.logger.debug("企业微信推送已禁用")

        # PushPlus推送
        if self.config.wechat_pushplus_enabled and self.config.wechat_pushplus:
            try:
                pushplus_push = AsyncPushPlusPush(self.config.wechat_pushplus, session)
            except Exception as e:
                self.logger.warning(f"PushPlus推送初始化失败: {e}")
        elif not self.config.wechat_pushplus_enabled:
            self.logger.debug("PushPlus推送已禁用")

        # 邮件推送
        if self.config.email_enabled:
            email_config = self.config.get_email_config()
            if email_config:
                try:
                    email_push = AsyncEmailPush(
                        smtp_host=email_config.smtp_host,
                        smtp_port=email_config.smtp_port,
                        smtp_user=email_config.smtp_user,
                        smtp_password=email_config.smtp_password,
                        from_email=email_config.from_email,
                        to_email=email_config.to_email,
                        use_tls=email_config.use_tls,
                    )
                except Exception as e:
                    self.logger.warning(f"邮件推送初始化失败: {e}")
        else:
            self.logger.debug("邮件推送已禁用")

        # 创建统一的推送管理器
        if wechat_push or pushplus_push or email_push:
            self.push = UnifiedPushManager(
                wechat_push=wechat_push,
                pushplus_push=pushplus_push,
                email_push=email_push,
            )
        else:
            self.logger.warning("未配置任何推送方式，推送功能将不可用")

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
