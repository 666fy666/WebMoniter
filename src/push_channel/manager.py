"""统一推送管理器 - 支持所有推送通道"""

import asyncio
import logging

from aiohttp import ClientSession

from src.ai_assistant.config import is_ai_enabled
from src.ai_assistant.llm_client import compress_text_with_llm, generate_push_content_with_llm
from src.config import get_config
from src.push_channel import get_push_channel


def _truncate_content_to_bytes(content: str, max_bytes: int) -> str:
    """将内容按 UTF-8 字节截断到 max_bytes 以内，末尾加省略号。"""
    encoded = content.encode("utf-8")
    if len(encoded) <= max_bytes:
        return content
    ellipsis_bytes = len("……".encode("utf-8"))
    if max_bytes <= ellipsis_bytes:
        return content.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
    truncated = encoded[: max_bytes - ellipsis_bytes].decode("utf-8", errors="ignore")
    return truncated + "……"


async def build_push_manager(
    push_channel_list: list[dict] | None,
    session: ClientSession,
    logger: logging.Logger,
    *,
    init_fail_prefix: str = "",
    channel_names: list[str] | None = None,
) -> "UnifiedPushManager | None":
    """
    根据配置构建 UnifiedPushManager。

    Args:
        push_channel_list: 推送通道配置列表
        session: HTTP 会话
        logger: 日志记录器
        init_fail_prefix: 初始化失败日志前缀
        channel_names: 要使用的通道名称列表（可选）。
                      如果为空列表或 None，则使用所有已配置的通道。
                      如果指定了名称，则只使用名称匹配的通道。

    说明：
    - 按通道名称过滤：当 channel_names 非空时，只初始化指定名称的通道。
    - 逐个创建通道、可选执行 initialize、失败则跳过该通道。
    """
    if not push_channel_list:
        return None

    # 如果指定了通道名称，转换为集合用于快速查找
    filter_names: set[str] | None = None
    if channel_names:
        filter_names = set(channel_names)

    push_channels = []
    for channel_config in push_channel_list:
        name = channel_config.get("name", "")

        # 按名称过滤通道（如果指定了）
        if filter_names is not None and name not in filter_names:
            continue

        try:
            channel = get_push_channel(channel_config, session)
            push_channels.append(channel)
            # 对于需要初始化的通道（如 QQBot），执行初始化
            if hasattr(channel, "initialize"):
                await channel.initialize()
        except Exception as e:  # noqa: BLE001
            # 保持日志信息风格可由调用方通过前缀控制
            logger.warning(f"{init_fail_prefix}推送通道 {name or '未知'} 初始化失败: {e}")

    if not push_channels:
        return None

    return UnifiedPushManager(push_channels, session)


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

    async def _ensure_content_within_limit(self, channel, content: str) -> str:
        """
        若渠道有字数限制且内容超限，则尝试 LLM 压缩（当配置开启且 AI 可用）或截断。
        返回不超过该渠道 max_content_bytes 的内容。
        """
        max_bytes = getattr(channel, "max_content_bytes", None)
        if max_bytes is None:
            return content
        content_bytes = len(content.encode("utf-8"))
        if content_bytes <= max_bytes:
            return content
        use_llm = getattr(get_config(), "push_compress_with_llm", False) and is_ai_enabled()
        if use_llm:
            compressed = await compress_text_with_llm(content, max_bytes)
            if compressed:
                self.logger.debug("推送内容已通过 LLM 压缩以符合 %s 字数限制", channel.name)
                return compressed
        return _truncate_content_to_bytes(content, max_bytes)

    async def _send_one(
        self,
        channel,
        title: str,
        channel_description: str,
        to_url: str,
        picurl: str,
        btntxt: str,
        author: str,
        extend_data: dict | None,
    ):
        """单渠道发送：先按渠道限制压缩/截断内容，再推送。"""
        final_description = await self._ensure_content_within_limit(channel, channel_description)
        return await self._send_with_error_handling(
            channel, title, final_description, to_url, picurl, btntxt, author, extend_data
        )

    async def send_news(
        self,
        title: str,
        description: str,
        to_url: str,
        picurl: str = "",
        btntxt: str = "阅读全文",
        author: str = "FengYu",
        description_func=None,
        extend_data: dict | None = None,
        event_type: str | None = None,
        event_data: dict | None = None,
        **kwargs,
    ) -> dict:
        """
        发送消息到所有配置的推送渠道

        Args:
            title: 标题
            description: 内容描述（默认值，如果 description_func 不为 None，则会被忽略）
            to_url: 跳转链接
            picurl: 图片URL（部分通道可通过 extend_data 传入本地图片路径自行上传）
            btntxt: 按钮文本
            author: 作者
            description_func: 可选的函数，接收 channel 参数，返回该通道的 description
            extend_data: 额外扩展数据，会原样传递给各通道的 push 方法
            event_type: 可选，事件类型（如 weibo/huya/checkin），配合 push_personalize_with_llm 使用
            event_data: 可选，事件数据字典，用于 LLM 生成个性化推送内容

        Returns:
            包含所有推送结果的字典
        """
        results = {}
        errors = []

        if not self.push_channels:
            self.logger.warning("未配置任何推送渠道")
            return {"results": results, "errors": errors}

        # 若开启 LLM 个性化且提供了事件信息，则生成更贴切的标题和内容
        use_personalize = (
            getattr(get_config(), "push_personalize_with_llm", False)
            and is_ai_enabled()
            and event_type
            and event_data is not None
        )
        if use_personalize:
            base_desc = (
                description_func(self.push_channels[0]) if description_func else description
            )
            personalized = await generate_push_content_with_llm(
                event_type, event_data, title, base_desc
            )
            if personalized:
                title, description = personalized
                description_func = None  # 使用统一 LLM 生成内容
                self.logger.debug("已使用 LLM 生成个性化推送内容")

        # 并发发送到所有渠道
        tasks = []
        channel_names = []

        # 基础扩展数据，每个通道都会收到
        base_extend_data = {"btntxt": btntxt, "author": author}
        # 如果调用方传入了自定义扩展数据，则进行合并（调用方优先）
        if extend_data:
            base_extend_data.update(extend_data)

        for channel in self.push_channels:
            channel_names.append(channel.name)
            # 如果提供了 description_func，则使用它来生成该通道的 description
            channel_description = description_func(channel) if description_func else description
            tasks.append(
                self._send_one(
                    channel,
                    title,
                    channel_description,
                    to_url,
                    picurl,
                    btntxt,
                    author,
                    base_extend_data,
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
        extend_data: dict | None,
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
                extend_data=extend_data,
            )
            return {"status": "success"}
        except Exception as e:
            raise Exception(f"{channel.name}推送失败: {e}") from e

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
