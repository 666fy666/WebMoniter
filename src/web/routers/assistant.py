"""AI assistant API routes."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from src.jobs.metadata import get_job_description as _get_job_description
from src.jobs.registry import (
    MONITOR_JOBS,
    TASK_JOBS,
    discover_and_import,
    run_task_with_logging,
)
from src.web.assistant_support import (
    CONFIG_FIELD_ALLOWED,
    CONFIG_FIELD_DISPLAY_NAMES,
    CONFIG_PATCH_DISPLAY_NAMES,
    CONFIG_PATCH_PLATFORMS,
    MONITOR_SECTION_KEYS,
    TOGGLE_ACTION_DISPLAY_NAMES,
    TOGGLE_SECTIONS,
    assistant_require_auth,
    build_assistant_chat_messages,
    parse_executable_intent_and_reply,
    parse_suggested_action_from_reply,
)
from src.web.auth import check_login
from src.web.config_io import (
    _apply_config_patch,
    _merge_and_dump_config,
    _validate_and_save_config,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/assistant/status")
async def assistant_status(request: Request):
    """获取 AI 助手可用状态（无需 AI 依赖也可调用）"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"enabled": False, "reason": "未登录"})
    try:
        from src.ai_assistant import is_ai_enabled

        return JSONResponse({"enabled": is_ai_enabled()})
    except ImportError:
        return JSONResponse({"enabled": False, "reason": "未安装 ai 依赖"})


@router.get("/api/assistant/conversations")
async def get_assistant_conversations(request: Request):
    """获取当前用户会话列表"""
    err = assistant_require_auth(request)
    if err:
        return err
    from src.ai_assistant.conversation import list_conversations

    user_id = request.session.get("username", "default")
    convos = list_conversations(user_id)
    return JSONResponse({"conversations": convos})


@router.post("/api/assistant/conversations")
async def create_assistant_conversation(request: Request):
    """新建会话"""
    err = assistant_require_auth(request)
    if err:
        return err
    body = (
        await request.json()
        if request.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    title = str(body.get("title", "新对话")).strip() or "新对话"
    from src.ai_assistant.conversation import create_conversation

    user_id = request.session.get("username", "default")
    conv_id = create_conversation(user_id=user_id, title=title)
    return JSONResponse({"conversation_id": conv_id})


@router.get("/api/assistant/conversations/{conv_id}/messages")
async def get_assistant_messages(request: Request, conv_id: str):
    """获取指定会话的消息列表"""
    err = assistant_require_auth(request)
    if err:
        return err
    from src.ai_assistant.config import get_ai_config
    from src.ai_assistant.conversation import get_messages

    cfg = get_ai_config()
    msgs = get_messages(conv_id, max_rounds=cfg.max_history_rounds)
    return JSONResponse({"messages": msgs})


@router.delete("/api/assistant/conversations/{conv_id}")
async def delete_assistant_conversation(request: Request, conv_id: str):
    """删除指定会话"""
    err = assistant_require_auth(request)
    if err:
        return err
    from src.ai_assistant.conversation import delete_conversation

    delete_conversation(conv_id)
    return JSONResponse({"success": True})


@router.post("/api/assistant/chat")
async def assistant_chat(request: Request):
    """对话接口，支持多轮记忆"""
    err = assistant_require_auth(request)
    if err:
        return err
    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "message 不能为空"}, status_code=400)
    conversation_id = body.get("conversation_id") or ""
    context = body.get("context", "all")

    from src.ai_assistant.config import get_ai_config
    from src.ai_assistant.conversation import (
        append_messages,
        create_conversation,
        get_messages,
    )
    from src.ai_assistant.llm_client import chat_completion

    cfg = get_ai_config()
    user_id = request.session.get("username", "default")

    if not conversation_id:
        conversation_id = create_conversation(user_id=user_id, title="新对话")

    reply, suggested_action = await parse_executable_intent_and_reply(message)
    if reply is not None:
        append_messages(
            conversation_id, user_content=message, assistant_content=reply, user_id=user_id
        )
        return JSONResponse(
            {
                "reply": reply,
                "conversation_id": conversation_id,
                "suggested_action": suggested_action,
            }
        )

    history = get_messages(conversation_id, max_rounds=cfg.max_history_rounds)
    messages = await build_assistant_chat_messages(message, context, history)

    try:
        reply = await chat_completion(messages=messages)
    except Exception as e:
        logger.error("AI 助手调用失败: %s", e)
        return JSONResponse(
            {"error": f"LLM 调用失败: {e}", "conversation_id": conversation_id},
            status_code=500,
        )

    append_messages(conversation_id, user_content=message, assistant_content=reply, user_id=user_id)

    reply, suggested_action = parse_suggested_action_from_reply(reply)

    return JSONResponse(
        {
            "reply": reply,
            "conversation_id": conversation_id,
            "suggested_action": suggested_action,
        }
    )


@router.post("/api/assistant/chat/stream")
async def assistant_chat_stream(request: Request):
    """对话接口（流式），使用 Server-Sent Events 逐块返回 AI 回复。"""
    err = assistant_require_auth(request)
    if err:
        return err
    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "message 不能为空"}, status_code=400)
    conversation_id = body.get("conversation_id") or ""
    context = body.get("context", "all")

    from src.ai_assistant.config import get_ai_config
    from src.ai_assistant.conversation import (
        append_messages,
        create_conversation,
        get_messages,
    )
    from src.ai_assistant.llm_client import chat_completion_stream

    cfg = get_ai_config()
    user_id = request.session.get("username", "default")

    if not conversation_id:
        conversation_id = create_conversation(user_id=user_id, title="新对话")

    reply, suggested_action = await parse_executable_intent_and_reply(message)
    if reply is not None:

        async def _intent_stream():
            yield f"data: {json.dumps({'chunk': reply}, ensure_ascii=False)}\n\n".encode()
            yield f"data: {json.dumps({'done': True, 'reply': reply, 'suggested_action': suggested_action, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n".encode()

        append_messages(
            conversation_id, user_content=message, assistant_content=reply, user_id=user_id
        )
        return StreamingResponse(
            _intent_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    history = get_messages(conversation_id, max_rounds=cfg.max_history_rounds)
    messages = await build_assistant_chat_messages(message, context, history)

    async def _stream_body():
        full_reply_parts = []
        try:
            async for chunk in chat_completion_stream(messages=messages):
                full_reply_parts.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n".encode()
        except Exception as e:
            logger.error("AI 助手流式调用失败: %s", e)
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n".encode()
            return
        reply = "".join(full_reply_parts).strip()
        append_messages(
            conversation_id, user_content=message, assistant_content=reply, user_id=user_id
        )
        reply, suggested_action = parse_suggested_action_from_reply(reply)
        yield f"data: {json.dumps({'done': True, 'reply': reply, 'suggested_action': suggested_action, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n".encode()

    return StreamingResponse(
        _stream_body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/assistant/apply-action")
async def assistant_apply_action(request: Request):
    """执行 AI 助手识别的可确认操作（如开关监控、增删列表项）"""
    err = assistant_require_auth(request)
    if err:
        return err

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "请求体格式错误"}, status_code=400)

    action = body.get("action")
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    if action == "config_patch":
        platform_key = body.get("platform_key")
        list_key = body.get("list_key")
        operation = body.get("operation")
        value = body.get("value")
        if platform_key not in CONFIG_PATCH_PLATFORMS:
            return JSONResponse({"error": f"不支持的平台: {platform_key}"}, status_code=400)
        if CONFIG_PATCH_PLATFORMS.get(platform_key) != list_key:
            return JSONResponse({"error": f"无效的 list_key: {list_key}"}, status_code=400)
        if operation not in ("add", "remove"):
            return JSONResponse({"error": "operation 须为 add 或 remove"}, status_code=400)
        if not isinstance(value, str) or not value.strip():
            return JSONResponse({"error": "value 不能为空"}, status_code=400)

        if platform_key == "weibo" and operation == "add":
            from src.monitors.weibo_search import is_numeric_uid

            if not is_numeric_uid(value):
                return JSONResponse(
                    {
                        "error": "微博添加请使用 UID（纯数字）。可通过对话说「关注XX的微博」由系统搜索并选择后写入。"
                    },
                    status_code=400,
                )

        try:
            config_path = Path("config.yml")
            if not config_path.exists():
                return JSONResponse({"error": "配置文件不存在"}, status_code=404)
            yaml_content = _apply_config_patch(
                config_path, platform_key, list_key, operation, value
            )

            err = await _validate_and_save_config(yaml_content, config_path)
            if err:
                return err

            op_text = "添加" if operation == "add" else "移除"
            display = CONFIG_PATCH_DISPLAY_NAMES.get(platform_key, platform_key)
            return JSONResponse(
                {
                    "success": True,
                    "message": f"已从{display}监控列表{op_text}「{value}」，配置已热重载",
                }
            )
        except Exception as e:
            logger.error("apply-action config_patch 执行失败: %s", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    if action == "config_field_update":
        section_key = body.get("section_key") or body.get("platform_key")
        field_key = body.get("field_key")
        value = body.get("value")
        if (section_key, field_key) not in CONFIG_FIELD_ALLOWED:
            return JSONResponse(
                {"error": f"不支持的配置: {section_key}.{field_key}"}, status_code=400
            )
        config_updates = {}
        if field_key == "start_end" and section_key == "quiet_hours":
            parts = str(value).split(",", 1)
            if len(parts) == 2:
                config_updates = {
                    "quiet_hours": {"start": parts[0].strip(), "end": parts[1].strip()}
                }
        else:
            if field_key in ("monitor_interval_seconds", "concurrency", "retention_days"):
                try:
                    value = int(value) if value is not None else 0
                except (TypeError, ValueError):
                    return JSONResponse({"error": "value 须为整数"}, status_code=400)
                if field_key == "monitor_interval_seconds" and (value < 1 or value > 86400):
                    return JSONResponse({"error": "监控间隔须为 1–86400 秒"}, status_code=400)
                if field_key == "concurrency" and (value < 1 or value > 20):
                    return JSONResponse({"error": "并发数须为 1–20"}, status_code=400)
                if field_key == "retention_days" and (value < 1 or value > 90):
                    return JSONResponse({"error": "日志保留天数须为 1–90"}, status_code=400)
            config_updates = {section_key: {field_key: value}}
        try:
            config_path = Path("config.yml")
            if not config_path.exists():
                return JSONResponse({"error": "配置文件不存在"}, status_code=404)
            yaml_content = _merge_and_dump_config(config_path, config_updates)
            err = await _validate_and_save_config(yaml_content, config_path)
            if err:
                return err
            display = CONFIG_FIELD_DISPLAY_NAMES.get(section_key, section_key)
            if field_key == "monitor_interval_seconds":
                msg = f"已将{display}监控间隔修改为 {value} 秒"
            elif field_key == "concurrency":
                msg = f"已将{display}并发数修改为 {value}"
            elif field_key == "time":
                msg = f"已将{display}执行时间修改为 {value}"
            elif field_key == "retention_days":
                msg = f"已将日志保留天数修改为 {value} 天"
            elif field_key in ("start", "end"):
                msg = f"已将免打扰{ '开始' if field_key == 'start' else '结束'}时间修改为 {value}"
            elif field_key == "start_end":
                s, e = str(value).split(",", 1)
                msg = f"已将免打扰时段设为 {s} 至 {e}"
            else:
                msg = f"已修改 {section_key}.{field_key}"
            return JSONResponse({"success": True, "message": f"{msg}，配置已热重载"})
        except Exception as e:
            logger.error("apply-action config_field_update 执行失败: %s", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    if action == "run_task":
        task_id = body.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            return JSONResponse({"error": "task_id 不能为空"}, status_code=400)
        task_id = task_id.strip()
        try:
            discover_and_import()
            all_jobs = MONITOR_JOBS + TASK_JOBS
            target_job = None
            for job in all_jobs:
                if job.job_id == task_id:
                    target_job = job
                    break
            if target_job is None:
                return JSONResponse({"error": f"任务 {task_id} 不存在"}, status_code=404)
            run_func = target_job.original_run_func or target_job.run_func
            await run_task_with_logging(task_id, run_func)
            logger.info("AI 助手触发任务: %s", task_id)
            display = _get_job_description(task_id)
            return JSONResponse({"success": True, "message": f"已执行「{display}」"})
        except Exception as e:
            logger.error("apply-action run_task 执行失败: %s", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    if action != "toggle_monitor":
        return JSONResponse({"error": f"不支持的操作: {action}"}, status_code=400)

    platform_key = body.get("platform_key")
    if platform_key not in TOGGLE_SECTIONS:
        return JSONResponse({"error": f"不支持的配置节: {platform_key}"}, status_code=400)

    enable = body.get("enable")
    if not isinstance(enable, bool):
        return JSONResponse({"error": "enable 须为布尔值"}, status_code=400)

    try:
        config_path = Path("config.yml")
        if not config_path.exists():
            return JSONResponse({"error": "配置文件不存在"}, status_code=404)

        config_data = {platform_key: {"enable": enable}}
        yaml_content = _merge_and_dump_config(config_path, config_data)

        err = await _validate_and_save_config(yaml_content, config_path)
        if err:
            return err

        action_text = "开启" if enable else "关闭"
        display = TOGGLE_ACTION_DISPLAY_NAMES.get(platform_key, platform_key)
        suffix = "监控" if platform_key in MONITOR_SECTION_KEYS else ""
        return JSONResponse(
            {"success": True, "message": f"已{action_text}{display}{suffix}，配置已热重载"}
        )
    except Exception as e:
        logger.error("apply-action 执行失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)
