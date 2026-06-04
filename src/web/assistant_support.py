"""Web AI assistant helpers.

This module keeps AI-related parsing, action constants, and webhook channel
discovery out of the main FastAPI route file.
"""

import asyncio
import json
import logging
import re

from fastapi import Request, status
from fastapi.responses import JSONResponse

from src.config import get_config
from src.web.auth import check_login

logger = logging.getLogger(__name__)

MONITOR_SECTION_KEYS = frozenset({"weibo", "huya", "bilibili", "douyin", "douyu", "xhs"})

TOGGLE_SECTIONS = frozenset(
    {
        "weibo",
        "huya",
        "bilibili",
        "douyin",
        "douyu",
        "xhs",
        "weibo_chaohua",
        "checkin",
        "tieba",
        "rainyun",
        "aliyun",
        "smzdm",
        "kuake",
        "weather",
        "log_cleanup",
        "quiet_hours",
    }
)

CONFIG_PATCH_PLATFORMS = {
    "weibo": "uids",
    "huya": "rooms",
    "bilibili": "uids",
    "douyin": "douyin_ids",
    "douyu": "rooms",
    "xhs": "profile_ids",
}

CONFIG_FIELD_ALLOWED = frozenset(
    {
        ("weibo", "monitor_interval_seconds"),
        ("huya", "monitor_interval_seconds"),
        ("bilibili", "monitor_interval_seconds"),
        ("douyin", "monitor_interval_seconds"),
        ("douyu", "monitor_interval_seconds"),
        ("xhs", "monitor_interval_seconds"),
        ("weibo", "concurrency"),
        ("huya", "concurrency"),
        ("bilibili", "concurrency"),
        ("douyin", "concurrency"),
        ("douyu", "concurrency"),
        ("xhs", "concurrency"),
        ("weibo_chaohua", "time"),
        ("checkin", "time"),
        ("tieba", "time"),
        ("rainyun", "time"),
        ("log_cleanup", "time"),
        ("log_cleanup", "retention_days"),
        ("quiet_hours", "start"),
        ("quiet_hours", "end"),
        ("quiet_hours", "start_end"),
    }
)

CONFIG_PATCH_DISPLAY_NAMES = {
    "weibo": "微博",
    "huya": "虎牙",
    "bilibili": "哔哩哔哩",
    "douyin": "抖音",
    "douyu": "斗鱼",
    "xhs": "小红书",
}

CONFIG_FIELD_DISPLAY_NAMES = {
    "weibo": "微博",
    "huya": "虎牙",
    "bilibili": "哔哩哔哩",
    "douyin": "抖音",
    "douyu": "斗鱼",
    "xhs": "小红书",
    "weibo_chaohua": "超话签到",
    "checkin": "iKuuu",
    "tieba": "贴吧",
    "rainyun": "雨云",
    "log_cleanup": "日志清理",
    "quiet_hours": "免打扰",
}

TOGGLE_ACTION_DISPLAY_NAMES = {
    "weibo": "微博",
    "huya": "虎牙",
    "bilibili": "哔哩哔哩",
    "douyin": "抖音",
    "douyu": "斗鱼",
    "xhs": "小红书",
    "weibo_chaohua": "微博超话签到",
    "checkin": "iKuuu 签到",
    "tieba": "贴吧签到",
    "rainyun": "雨云签到",
    "aliyun": "阿里云盘签到",
    "smzdm": "值得买签到",
    "kuake": "夸克签到",
    "weather": "天气推送",
    "log_cleanup": "日志清理",
    "quiet_hours": "免打扰",
}


def assistant_require_auth(request: Request) -> JSONResponse | None:
    """Check login and AI availability for assistant API routes."""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)
    try:
        from src.ai_assistant import is_ai_enabled

        if not is_ai_enabled():
            return JSONResponse(
                {
                    "error": "AI 助手未启用",
                    "hint": "请在 config.yml 中配置 ai_assistant.enable 并执行 uv sync 安装依赖",
                },
                status_code=503,
            )
    except ImportError:
        return JSONResponse(
            {"error": "AI 助手模块不可用", "hint": "请执行 uv sync 安装依赖"},
            status_code=503,
        )
    return None


async def parse_executable_intent_and_reply(message: str) -> tuple[str | None, dict | None]:
    """
    Parse executable assistant intents.

    Returns ``(reply, suggested_action)`` when a confirmable action is detected,
    otherwise ``(None, None)``.
    """
    from src.ai_assistant.intent_parser import (
        parse_config_field_intent,
        parse_config_patch_intent,
        parse_run_task_intent,
        parse_toggle_monitor_intent,
    )
    from src.weibo_search import is_numeric_uid, search_weibo_users

    run_intent = parse_run_task_intent(message)
    if run_intent is not None:
        reply = f"好的，将立即执行「{run_intent.display_name}」任务。请确认执行："
        suggested_action = {
            "type": "confirm_execute",
            "action": "run_task",
            "task_id": run_intent.task_id,
            "title": f"执行 {run_intent.display_name}",
            "description": f"确认后将在后台运行任务「{run_intent.display_name}」，与「任务管理」中手动触发的效果相同。",
        }
        return reply, suggested_action

    intent = parse_toggle_monitor_intent(message)
    if intent is not None:
        action_text = "关闭" if not intent.enable else "开启"
        reply = f"好的，{action_text}{intent.display_name}监控。请确认执行："
        suggested_action = {
            "type": "confirm_execute",
            "action": "toggle_monitor",
            "platform_key": intent.platform_key,
            "enable": intent.enable,
            "title": f"{action_text}{intent.display_name}监控",
            "description": f"确认{action_text}{intent.display_name}监控？"
            + (
                "关闭后将停止轮询并不再推送相关通知。"
                if not intent.enable
                else "开启后将恢复轮询并推送通知。"
            ),
        }
        return reply, suggested_action

    patch = parse_config_patch_intent(message)
    if patch is not None:
        op_text = "添加" if patch.operation == "add" else "移除"

        if (
            patch.platform_key == "weibo"
            and patch.operation == "add"
            and not is_numeric_uid(patch.value)
        ):
            config = get_config()
            cookie = config.weibo_cookie or ""
            candidates = await search_weibo_users(patch.value, cookie)

            if not candidates:
                from urllib.parse import quote

                search_link = f"https://s.weibo.com/user?q={quote(patch.value)}"
                reply = (
                    f"未找到与「{patch.value}」相关的微博用户。\n\n"
                    f"请尝试：\n"
                    f"1. 在浏览器打开 {search_link} 搜索\n"
                    f"2. 从结果中点击目标用户，进入主页后 URL 中的数字即为 UID\n"
                    f"3. 对我说「添加微博用户 <UID>」或在配置页直接输入 UID"
                )
                return reply, None

            if len(candidates) == 1:
                c = candidates[0]
                reply = f"找到 1 个匹配账号：**{c['nick']}**（UID: {c['uid']}）"
                suggested_action = {
                    "type": "confirm_execute",
                    "action": "config_patch",
                    "platform_key": "weibo",
                    "list_key": "uids",
                    "operation": "add",
                    "value": c["uid"],
                    "title": "添加微博监控",
                    "description": f"将添加「{c['nick']}」到微博监控列表",
                }
                return reply, suggested_action

            lines = [
                f"{i + 1}. **{c['nick']}**（UID: {c['uid']}，粉丝: {c.get('followers_count_str', '')}）"
                for i, c in enumerate(candidates)
            ]
            reply = f"找到 {len(candidates)} 个相关账号，请选择要添加的：\n\n" + "\n".join(lines)
            suggested_action = {
                "type": "weibo_choose",
                "title": "选择要添加的微博账号",
                "description": "请选择要添加到监控的账号：",
                "candidates": candidates,
            }
            return reply, suggested_action

        reply = f"好的，将从{patch.display_name}监控列表中{op_text}「{patch.value}」。请确认执行："
        suggested_action = {
            "type": "confirm_execute",
            "action": "config_patch",
            "platform_key": patch.platform_key,
            "list_key": patch.list_key,
            "operation": patch.operation,
            "value": patch.value,
            "title": f"{op_text}配置项",
            "description": f"将从 {patch.platform_key} 的 {patch.list_key} 中{op_text}「{patch.value}」",
        }
        return reply, suggested_action

    field_intent = parse_config_field_intent(message)
    if field_intent is not None:
        if field_intent.field_key == "monitor_interval_seconds":
            desc = f"将 {field_intent.display_name} 的 {field_intent.field_key} 修改为 {field_intent.value} 秒"
        elif field_intent.field_key == "concurrency":
            desc = f"将 {field_intent.display_name} 并发数修改为 {field_intent.value}"
        elif field_intent.field_key == "time":
            desc = f"将 {field_intent.display_name} 执行时间修改为 {field_intent.value}"
        elif field_intent.field_key == "retention_days":
            desc = f"将日志保留天数修改为 {field_intent.value} 天"
        elif field_intent.field_key in ("start", "end"):
            desc = f"将免打扰{ '开始' if field_intent.field_key == 'start' else '结束'}时间修改为 {field_intent.value}"
        elif field_intent.field_key == "start_end":
            s, e = str(field_intent.value).split(",", 1)
            desc = f"将免打扰时段设为 {s} 至 {e}"
        else:
            desc = f"将 {field_intent.display_name} 的 {field_intent.field_key} 修改为 {field_intent.value}"
        reply = f"好的，{desc}。请确认执行："
        suggested_action = {
            "type": "confirm_execute",
            "action": "config_field_update",
            "section_key": field_intent.section_key,
            "field_key": field_intent.field_key,
            "value": field_intent.value,
            "title": "修改配置",
            "description": desc,
        }
        return reply, suggested_action

    return None, None


def parse_suggested_action_from_reply(reply: str) -> tuple[str, dict | None]:
    """Parse suggested actions embedded in LLM replies."""
    suggested_action = None
    json_match = re.search(r"```json\s*\n(.*?)```", reply, re.DOTALL)
    if json_match:
        try:
            patch = json.loads(json_match.group(1).strip())
            if patch.get("type") == "config_patch" and all(
                k in patch for k in ("platform_key", "list_key", "operation", "value")
            ):
                suggested_action = {
                    "type": "confirm_execute",
                    "action": "config_patch",
                    "platform_key": patch["platform_key"],
                    "list_key": patch["list_key"],
                    "operation": patch["operation"],
                    "value": str(patch["value"]),
                    "title": f"{'添加' if patch['operation'] == 'add' else '移除'}配置项",
                    "description": f"将从 {patch['platform_key']} 的 {patch['list_key']} 中{'添加' if patch['operation'] == 'add' else '移除'}「{patch['value']}」",
                }
                reply = re.sub(r"\n*```json\s*\n.*?```\s*", "\n", reply, flags=re.DOTALL).strip()
        except (json.JSONDecodeError, KeyError):
            pass
    if suggested_action is None:
        yaml_match = re.search(r"```yaml\s*\n(.*?)```", reply, re.DOTALL)
        if yaml_match:
            suggested_action = {
                "type": "config_diff",
                "diff": yaml_match.group(1).strip(),
                "description": "配置片段（可复制到 config.yml 或配置页）",
            }
    return reply, suggested_action


async def build_assistant_chat_messages(
    message: str,
    context: str,
    history: list[dict],
) -> list[dict]:
    """Build LLM chat messages with RAG context, current state, history, and user input."""
    from src.ai_assistant.prompts import SYSTEM_PROMPT
    from src.ai_assistant.rag import retrieve_all
    from src.ai_assistant.tools_current_state import (
        parse_platforms_from_message,
        query_current_state,
    )

    system_content = SYSTEM_PROMPT
    rag_ctx = await asyncio.to_thread(retrieve_all, message, context)
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
    return messages


def get_wecom_channels_with_callback() -> list[tuple[str, dict]]:
    """Return wecom_apps channels that can receive callbacks."""
    try:
        config = get_config()
        channels = config.push_channel_list or []
        result = []
        for ch in channels:
            if ch.get("type") != "wecom_apps":
                continue
            token = str(ch.get("callback_token", "")).strip()
            key = str(ch.get("encoding_aes_key", "")).strip()
            if token and key and ch.get("corp_id"):
                result.append((ch.get("name", ""), ch))
        return result
    except Exception:
        return []


def get_telegram_channels() -> list[tuple[str, dict]]:
    """Return telegram_bot channels that have api_token configured."""
    try:
        config = get_config()
        channels = config.push_channel_list or []
        result = []
        for ch in channels:
            if ch.get("type") != "telegram_bot":
                continue
            token = str(ch.get("api_token", "")).strip()
            if token:
                result.append((ch.get("name", ""), ch))
        return result
    except Exception:
        return []
