"""企业微信自建应用 - AI 助手接收消息与被动回复

参考文档：
- 接收消息：https://developer.work.weixin.qq.com/document/path/90238
- 消息格式：https://developer.work.weixin.qq.com/document/path/90239
- 被动回复：https://developer.work.weixin.qq.com/document/path/90241
- 加解密：https://developer.work.weixin.qq.com/document/path/90968
"""

import logging
import re
import time
from urllib.parse import unquote

from fastapi import Request, Response
from fastapi.responses import PlainTextResponse

from src.ai_assistant.wecom_crypto import decrypt_msg, encrypt_msg

logger = logging.getLogger(__name__)


def _extract_xml_tag(tag: str, xml: str) -> str | None:
    m = re.search(rf"<{tag}><!\[CDATA\[(.*?)\]\]></{tag}>", xml, re.DOTALL)
    if m:
        return m.group(1)
    m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)
    return m.group(1).strip() if m else None


async def handle_wecom_callback(
    request: Request,
    channel_config: dict,
    *,
    post_body: bytes | None = None,
) -> Response:
    """
    处理企业微信应用回调（接收消息、URL 验证）。

    当企业微信后台配置「接收消息」回调 URL 后，会向该 URL 发送：
    1. GET 请求（URL 验证）：msg_signature, timestamp, nonce, echostr
    2. POST 请求（消息推送）：XML 格式加密消息
    """
    token = str(channel_config.get("callback_token", "")).strip()
    encoding_aes_key = str(channel_config.get("encoding_aes_key", "")).strip()
    corp_id = str(channel_config.get("corp_id", "")).strip()

    if not token or not encoding_aes_key or not corp_id:
        logger.warning("企业微信 AI 回调配置不完整：缺少 callback_token / encoding_aes_key / corp_id")
        return PlainTextResponse("config error", status_code=500)

    params = request.query_params
    msg_signature = params.get("msg_signature", "")
    timestamp = params.get("timestamp", "")
    nonce = params.get("nonce", "")

    if not msg_signature or not timestamp or not nonce:
        return PlainTextResponse("missing params", status_code=400)

    # GET：URL 验证（企业微信后台配置回调 URL 时会发起）
    if request.method == "GET":
        echostr_raw = params.get("echostr", "")
        echostr = unquote(echostr_raw)
        if not echostr:
            return PlainTextResponse("missing echostr", status_code=400)
        try:
            # echostr 为加密内容，解密后原样返回即可通过验证
            fake_post = f'<xml><Encrypt><![CDATA[{echostr}]]></Encrypt></xml>'
            decrypted = decrypt_msg(
                token, encoding_aes_key, corp_id,
                msg_signature, timestamp, nonce, fake_post
            )
            return PlainTextResponse(decrypted)
        except Exception as e:
            logger.error("企业微信 URL 验证失败: %s", e)
            return PlainTextResponse("verify failed", status_code=400)

    # POST：消息回调
    raw = post_body if post_body is not None else (await request.body())
    try:
        post_data = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        post_data = raw.decode("utf-8", errors="replace")
        logger.warning("企业微信 POST 请求体 UTF-8 含非法字节，已 replace 处理，若仍解密失败请检查代理是否篡改请求体")

    try:
        plain_xml = decrypt_msg(
            token, encoding_aes_key, corp_id,
            msg_signature, timestamp, nonce, post_data
        )
    except Exception as e:
        logger.error("企业微信消息解密失败: %s", e)
        return PlainTextResponse("decrypt failed", status_code=400)

    msg_type = _extract_xml_tag("MsgType", plain_xml)
    if msg_type != "text":
        # 非文本消息，回复提示
        from_user = _extract_xml_tag("FromUserName", plain_xml) or ""
        to_user = _extract_xml_tag("ToUserName", plain_xml) or ""
        agent_id = _extract_xml_tag("AgentID", plain_xml) or ""
        reply_xml = f"""<xml>
<ToUserName><![CDATA[{from_user}]]></ToUserName>
<FromUserName><![CDATA[{to_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[暂仅支持文本消息，请发送文字与 AI 助手对话。]]></Content>
</xml>"""
        ts = str(int(time.time()))
        nc = str(int(time.time() * 1000))[-9:]
        encrypted = encrypt_msg(token, encoding_aes_key, reply_xml, ts, nc, corp_id)
        return Response(content=encrypted, media_type="application/xml")

    content = (_extract_xml_tag("Content", plain_xml) or "").strip()
    from_user = _extract_xml_tag("FromUserName", plain_xml) or ""
    to_user = _extract_xml_tag("ToUserName", plain_xml) or ""

    if not content:
        reply_text = "请发送文字内容与 AI 助手对话。"
    else:
        try:
            from src.ai_assistant import is_ai_enabled
            from src.ai_assistant.platform_chat import chat_for_platform

            if not is_ai_enabled():
                reply_text = "AI 助手未启用，请在 config.yml 中配置 ai_assistant.enable 并安装 uv sync --extra ai。"
            else:
                reply_text, _ = await chat_for_platform(
                    message=content,
                    user_id=f"wecom:{from_user}",
                    conversation_id=None,
                    skip_executable_intent=True,
                )
        except ImportError:
            reply_text = "AI 助手模块不可用，请安装 uv sync --extra ai。"
        except Exception as e:
            logger.exception("企业微信 AI 对话失败")
            reply_text = f"处理失败：{e}"

    # 被动回复文本消息（明文 XML，需加密后返回）
    reply_xml = f"""<xml>
<ToUserName><![CDATA[{from_user}]]></ToUserName>
<FromUserName><![CDATA[{to_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{reply_text}]]></Content>
</xml>"""

    ts = str(int(time.time()))
    nc = str(int(time.time() * 1000))[-9:]
    encrypted = encrypt_msg(token, encoding_aes_key, reply_xml, ts, nc, corp_id)
    return Response(content=encrypted, media_type="application/xml")
