"""统一推送管理器 - 支持所有推送通道"""

import asyncio
import logging

from aiohttp import ClientSession

from src.push_channel import get_push_channel
from src.push_channel.cute_copy import style_push_description, style_push_title
from src.push_channel.rich_text import RichText


def _truncate_content_to_bytes(content: str, max_bytes: int) -> str:
    """将内容按 UTF-8 字节截断到 max_bytes 以内，末尾加省略号。"""
    encoded = content.encode("utf-8")
    if len(encoded) <= max_bytes:
        return content
    ellipsis_bytes = len("……".encode())
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
        if channel_config.get("enable") is False:
            continue
        name = channel_config.get("name", "")

        # 按名称过滤通道（如果指定了）
        if filter_names is not None and name not in filter_names:
            continue

        channel = None
        try:
            channel = get_push_channel(channel_config, session)
            # 对于需要初始化的通道（如 QQBot），执行初始化
            if hasattr(channel, "initialize"):
                await channel.initialize()
            push_channels.append(channel)
        except Exception as e:  # noqa: BLE001
            # 保持日志信息风格可由调用方通过前缀控制
            logger.warning("%s推送通道 %s 初始化失败: %s", init_fail_prefix, name or "未知", e)
            if channel is not None:
                try:
                    await channel.close()
                except Exception as close_exc:  # noqa: BLE001
                    logger.debug(
                        "关闭初始化失败的推送通道 %s 时出错: %s", name or "未知", close_exc
                    )

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

    def _ensure_content_within_limit(
        self,
        channel,
        content: str,
        extend_data: dict | None = None,
    ) -> str:
        """
        若渠道有字数限制且内容超限，则截断到该渠道 max_content_bytes 以内。

        纯同步实现：仅做字节截断，不访问全局配置，调用方无需 await。
        """
        max_bytes = getattr(channel, "max_content_bytes", None)
        if extend_data and extend_data.get("plain_text"):
            max_bytes = getattr(channel, "plain_text_max_content_bytes", max_bytes)
        if max_bytes is None:
            return content
        content_bytes = len(content.encode("utf-8"))
        if content_bytes <= max_bytes:
            return content
        return _truncate_content_to_bytes(content, max_bytes)

    async def _send_one(
        self,
        channel,
        title: str,
        channel_description,
        to_url: str,
        picurl: str,
        btntxt: str,
        author: str,
        extend_data: dict | None,
    ):
        """单渠道发送：先按渠道限制压缩/截断内容，再推送。"""
        channel_extend_data = dict(extend_data or {})
        if isinstance(channel_description, RichText):
            output_format = getattr(channel, "rich_text_format", "plain")
            if output_format not in {"plain", "markdown", "html"}:
                output_format = "plain"
            max_bytes = getattr(channel, "max_content_bytes", None)
            if channel_extend_data.get("plain_text"):
                output_format = "plain"
                max_bytes = getattr(channel, "plain_text_max_content_bytes", max_bytes)
            final_description = channel_description.render(output_format, max_bytes=max_bytes)
            channel_extend_data["_rich_text_format"] = output_format
        else:
            final_description = self._ensure_content_within_limit(
                channel, str(channel_description), channel_extend_data
            )
        return await self._send_with_error_handling(
            channel,
            title,
            final_description,
            to_url,
            picurl,
            btntxt,
            author,
            channel_extend_data,
        )

    async def send_text(
        self,
        title: str,
        content: str,
        author: str = "FengYu",
        description_func=None,
        extend_data: dict | None = None,
        **kwargs,
    ) -> dict:
        """发送纯文本消息，不附带跳转链接或图片。"""
        text_extend_data = {"plain_text": True}
        if extend_data:
            text_extend_data.update(extend_data)

        return await self.send_news(
            title=title,
            description=content,
            to_url="",
            picurl="",
            btntxt="",
            author=author,
            description_func=description_func,
            extend_data=text_extend_data,
            **kwargs,
        )

    async def send_news(
        self,
        title: str,
        description: str | RichText,
        to_url: str,
        picurl: str = "",
        btntxt: str = "阅读全文",
        author: str = "FengYu",
        description_func=None,
        extend_data: dict | None = None,
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

        Returns:
            包含所有推送结果的字典
        """
        results = {}
        errors = []
        styled_title = style_push_title(title)

        if not self.push_channels:
            self.logger.warning("未配置任何推送渠道")
            return {"results": results, "errors": errors}

        # 并发发送到所有渠道
        tasks = []
        channel_names = []

        base_extend_data = {"btntxt": btntxt, "author": author}
        if extend_data:
            base_extend_data.update(extend_data)

        for channel in self.push_channels:
            channel_name = channel.name
            try:
                channel_description = description_func(channel) if description_func else description
                channel_description = style_push_description(title, channel_description)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{channel_name}: {e}")
                continue
            channel_names.append(channel_name)
            tasks.append(
                self._send_one(
                    channel,
                    styled_title,
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
                    errors.append(f"{channel_name}: {result}")
                else:
                    results[channel_name] = result

        if errors:
            total = len(self.push_channels)
            failed = len(errors)
            summary = "; ".join(errors)
            if failed == total:
                self.logger.error("全部推送失败 (%d/%d): %s", failed, total, summary)
            elif failed == 1:
                self.logger.error("推送失败: %s", summary)
            else:
                self.logger.warning("部分推送失败 (%d/%d): %s", failed, total, summary)

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
        except Exception:
            raise

    async def close(self):
        """关闭所有推送服务"""
        for channel in self.push_channels:
            try:
                await channel.close()
            except Exception as e:
                self.logger.error("关闭推送通道 %s 失败: %s", channel.name, e)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
