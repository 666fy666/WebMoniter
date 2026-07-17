import json
import logging
from abc import ABC, abstractmethod

from aiohttp import ClientResponseError, ClientSession, ClientTimeout


class PushChannel(ABC):
    """推送通道基类 - 所有推送通道都应该继承此类"""

    # 推送内容（content/description）的最大字节数，None 表示不限制。超限时由 UnifiedPushManager 截断。
    # 各子类按官方文档设置，如企业微信应用 500、Telegram 约 4096 字符等。
    max_content_bytes: int | None = None
    # RichText 的原生渲染格式；普通通道默认接收不带实际 URL 的纯文本。
    rich_text_format: str = "plain"
    # 是否支持在正文中显示远程微博表情图片；默认关闭，避免不兼容通道显示破损语法。
    supports_inline_emoji: bool = False

    def __init__(self, config, session: ClientSession | None = None):
        """
        初始化推送通道

        Args:
            config: 配置字典
            session: 可选的 HTTP 会话（用于共享连接）
        """
        self.name = config.get("name", "")
        self.type = config.get("type", "")
        self.session = session
        self._own_session = False
        self.logger = logging.getLogger(self.__class__.__name__)

    def _log_push_error(self, message: str) -> None:
        """记录推送失败详情；由 UnifiedPushManager 统一输出 error 汇总，此处仅 debug。"""
        self.logger.debug("【推送_%s】%s", self.name, message)

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

    async def _post_json(
        self,
        url: str,
        body: dict,
        *,
        headers: dict | None = None,
        params: dict | None = None,
        code_key: str | None = None,
        success_code=0,
        message_key: str = "errmsg",
    ) -> dict:
        """发送 JSON POST，并按渠道业务码做统一错误处理。"""
        try:
            session = await self._get_session()
            async with session.post(
                url,
                headers=headers or {"Content-Type": "application/json"},
                params=params,
                data=json.dumps(body).encode("utf-8"),
            ) as response:
                response.raise_for_status()
                result = await response.json()
                if code_key is not None and result.get(code_key) != success_code:
                    error_msg = result.get(message_key, "未知错误")
                    raise Exception(f"推送失败: {error_msg}")
                self.logger.debug("【推送_%s】成功", self.name)
                return result
        except ClientResponseError as e:
            self._log_push_error(f"请求失败: {e}")
            raise
        except Exception as e:
            self._log_push_error(f"推送失败: {e}")
            raise

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
