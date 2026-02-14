"""Telegram 机器人 - AI 助手接收消息与回复

参考文档：https://core.telegram.org/bots/api
Webhook 设置：POST https://api.telegram.org/bot<token>/setWebhook?url=<your_url>
"""

import logging

from fastapi import Request

logger = logging.getLogger(__name__)


async def handle_telegram_webhook(request: Request, channel_config: dict) -> dict | None:
    """
    处理 Telegram Bot Webhook 推送的 Update。

    Returns:
        若处理了消息并需回复，返回 dict 供调用方发送；否则返回 None
    """
    api_token = str(channel_config.get("api_token", "")).strip()
    if not api_token:
        return None

    try:
        body = await request.json()
    except Exception:
        return None

    message = body.get("message") or body.get("edited_message")
    if not message:
        return None

    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()
    from_user = message.get("from", {})
    user_id_str = str(from_user.get("id", ""))

    if not text:
        return {"chat_id": chat_id, "text": "请发送文字与 AI 助手对话。"}

    try:
        from src.ai_assistant import is_ai_enabled
        from src.ai_assistant.platform_chat import chat_for_platform

        if not is_ai_enabled():
            return {
                "chat_id": chat_id,
                "text": "AI 助手未启用，请在 config.yml 中配置 ai_assistant.enable 并执行 uv sync 安装依赖。",
            }

        reply_text, _ = await chat_for_platform(
            message=text,
            user_id=f"telegram:{user_id_str}",
            conversation_id=None,
            skip_executable_intent=True,
        )
        return {"chat_id": chat_id, "text": reply_text}
    except ImportError:
        return {"chat_id": chat_id, "text": "AI 助手模块不可用，请执行 uv sync 安装依赖。"}
    except Exception as e:
        logger.exception("Telegram AI 对话失败")
        return {"chat_id": chat_id, "text": f"处理失败：{e}"}


async def send_telegram_message(api_token: str, chat_id: int | str, text: str) -> bool:
    """通过 Telegram Bot API 发送消息"""
    import aiohttp

    url = f"https://api.telegram.org/bot{api_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=30)
            ) as r:
                data = await r.json()
                return data.get("ok", False)
    except Exception as e:
        logger.error("Telegram 发送消息失败: %s", e)
        return False
