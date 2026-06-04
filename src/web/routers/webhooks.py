"""Interactive push-channel webhook routes."""

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.web.assistant_support import (
    get_telegram_channels,
    get_wecom_channels_with_callback,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.api_route("/api/webhooks/wecom", methods=["GET", "POST"])
async def webhook_wecom(request: Request):
    """
    企业微信自建应用 - 接收消息回调。
    需在 push_channel 的 wecom_apps 中配置 callback_token、encoding_aes_key，
    并在企业微信后台设置「接收消息」URL 为本接口（如 https://xxx/api/webhooks/wecom）。
    支持多应用：依次尝试各通道解密，第一个成功的即为目标应用。
    """
    channels = get_wecom_channels_with_callback()
    if not channels:
        return JSONResponse({"error": "未配置企业微信 AI 回调"}, status_code=503)

    from src.ai_assistant.platform_handlers.wecom import handle_wecom_callback

    post_body: bytes | None = None
    if request.method == "POST":
        post_body = await request.body()

    last_error = None
    for _name, ch in channels:
        try:
            resp = await handle_wecom_callback(
                request, ch, post_body=post_body if request.method == "POST" else None
            )
            if hasattr(resp, "status_code") and 400 <= resp.status_code < 500:
                last_error = resp
                continue
            return resp
        except ValueError as e:
            last_error = e
            continue
        except Exception as e:
            logger.debug("企业微信通道 %s 处理异常: %s", _name, e)
            last_error = e
            continue

    if isinstance(last_error, JSONResponse):
        return last_error
    return JSONResponse({"error": "签名或解密失败"}, status_code=400)


@router.post("/api/webhooks/telegram/{channel_name:path}")
async def webhook_telegram(request: Request, channel_name: str):
    """
    Telegram 机器人 - 接收消息 Webhook。
    需在 push_channel 的 telegram_bot 中配置 api_token，
    并调用 setWebhook 设置 URL 为 https://xxx/api/webhooks/telegram/{通道名}。
    """
    channels = get_telegram_channels()
    channel_config = None
    for name, ch in channels:
        if name == channel_name:
            channel_config = ch
            break
    if not channel_config:
        return JSONResponse({"error": "未找到该 Telegram 通道"}, status_code=404)

    from src.ai_assistant.platform_handlers.telegram import (
        handle_telegram_webhook,
        send_telegram_message,
    )

    result = await handle_telegram_webhook(request, channel_config)
    if result is None:
        return JSONResponse({"ok": True})

    chat_id = result.get("chat_id")
    text = result.get("text", "")
    api_token = channel_config.get("api_token", "")

    if chat_id and text and api_token:
        asyncio.create_task(send_telegram_message(api_token, chat_id, text))

    return JSONResponse({"ok": True})
