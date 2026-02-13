"""AI 助手平台对话核心 - 供企业微信、飞书、Telegram 等平台调用，无 session 依赖"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def chat_for_platform(
    message: str,
    user_id: str,
    conversation_id: str | None = None,
    *,
    skip_executable_intent: bool = True,
) -> tuple[str, dict[str, Any] | None]:
    """
    供外部平台（企业微信、飞书、Telegram）调用的 AI 对话接口。

    Args:
        message: 用户输入
        user_id: 平台用户标识，用于会话隔离
        conversation_id: 可选，指定会话 ID；为空时自动创建新会话
        skip_executable_intent: 是否跳过可执行意图（开关监控、配置增删等），
            推送平台无法执行 apply-action，建议为 True，仅返回文本回复

    Returns:
        (reply_text, suggested_action)
        - reply_text: AI 回复的纯文本
        - suggested_action: 若有可执行操作则返回，否则 None
          推送平台通常忽略 suggested_action，仅展示 reply_text
    """
    from src.ai_assistant.config import get_ai_config
    from src.ai_assistant.conversation import (
        append_messages,
        create_conversation,
        get_messages,
    )
    from src.ai_assistant.llm_client import chat_completion
    from src.ai_assistant.prompts import SYSTEM_PROMPT
    from src.ai_assistant.rag import retrieve_all
    from src.ai_assistant.tools_current_state import (
        parse_platforms_from_message,
        query_current_state,
    )

    cfg = get_ai_config()

    if not conversation_id:
        conversation_id = create_conversation(user_id=user_id, title="新对话")

    # 推送平台通常无法执行 apply-action，skip_executable_intent=True 时直接走 LLM
    suggested_action = None
    if not skip_executable_intent:
        from src.ai_assistant.intent_parser import (
            parse_config_field_intent,
            parse_config_patch_intent,
            parse_run_task_intent,
            parse_toggle_monitor_intent,
        )

        run_intent = parse_run_task_intent(message)
        if run_intent is not None:
            reply = f"好的，将立即执行「{run_intent.display_name}」任务。请在 Web 管理界面「任务管理」中手动触发。"
            append_messages(conversation_id, message, reply, user_id=user_id)
            return reply, None

        toggle = parse_toggle_monitor_intent(message)
        if toggle is not None:
            action_text = "开启" if toggle.enable else "关闭"
            reply = f"好的，{action_text}{toggle.display_name}监控。请在 Web 管理界面「配置管理」中修改。"
            append_messages(conversation_id, message, reply, user_id=user_id)
            return reply, None

        patch = parse_config_patch_intent(message)
        if patch is not None:
            op_text = "添加" if patch.operation == "add" else "移除"
            reply = f"好的，将{patch.display_name}中{op_text}「{patch.value}」。请在 Web 管理界面操作。"
            append_messages(conversation_id, message, reply, user_id=user_id)
            return reply, None

        field_intent = parse_config_field_intent(message)
        if field_intent is not None:
            reply = f"好的，将修改 {field_intent.display_name} 的 {field_intent.field_key}。请在 Web 管理界面操作。"
            append_messages(conversation_id, message, reply, user_id=user_id)
            return reply, None

    history = get_messages(conversation_id, max_rounds=cfg.max_history_rounds)
    system_content = SYSTEM_PROMPT
    rag_ctx = retrieve_all(message, context="all")
    if rag_ctx:
        system_content += "\n\n【本次检索到的参考】\n" + rag_ctx

    need_current = (
        "当前" in message
        or "现在" in message
        or "谁在直播" in message
        or "最新" in message
        or "开播" in message
        or "谁开播" in message
        or "直播" in message
    )
    if need_current:
        try:
            platforms = parse_platforms_from_message(message)
            current_data = await query_current_state(platforms=platforms)
            if current_data:
                system_content += "\n\n【当前监控数据】\n" + current_data
        except Exception as e:
            logger.debug("query_current_state 失败: %s", e)

    messages = [{"role": "system", "content": system_content}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    try:
        reply = await chat_completion(messages=messages)
    except Exception as e:
        logger.error("AI 助手调用失败: %s", e)
        return f"AI 助手调用失败，请稍后重试：{e}", None

    append_messages(
        conversation_id,
        user_content=message,
        assistant_content=reply,
        user_id=user_id,
    )

    # 推送平台不解析 suggested_action（无 apply 能力），直接返回文本
    return reply, None
