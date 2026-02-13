"""多轮对话存储与加载 - SQLite 或 JSON"""

import json
import logging
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
CONVERSATIONS_FILE = DATA_DIR / "ai_assistant_conversations.json"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_conversations() -> dict[str, Any]:
    """加载会话与消息数据"""
    _ensure_data_dir()
    if not CONVERSATIONS_FILE.exists():
        return {"conversations": {}, "messages": {}}
    try:
        with open(CONVERSATIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("加载 AI 对话数据失败: %s", e)
        return {"conversations": {}, "messages": {}}


def _save_conversations(data: dict[str, Any]) -> None:
    """保存会话与消息数据"""
    _ensure_data_dir()
    try:
        with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("保存 AI 对话数据失败: %s", e)


def list_conversations(user_id: str = "default") -> list[dict[str, Any]]:
    """获取用户的会话列表"""
    data = _load_conversations()
    convos = data.get("conversations", {})
    user_convos = [c for c in convos.values() if c.get("user_id") == user_id]
    return sorted(user_convos, key=lambda x: x.get("updated_at", ""), reverse=True)


def create_conversation(user_id: str = "default", title: str = "新对话") -> str:
    """新建会话，返回 conversation_id"""
    conv_id = str(uuid.uuid4())
    data = _load_conversations()
    convos = data.get("conversations", {})
    convos[conv_id] = {
        "id": conv_id,
        "user_id": user_id,
        "title": title,
        "created_at": _now_str(),
        "updated_at": _now_str(),
    }
    data["conversations"] = convos
    if "messages" not in data:
        data["messages"] = {}
    data["messages"][conv_id] = []
    _save_conversations(data)
    return conv_id


def get_messages(conversation_id: str, max_rounds: int = 10) -> list[dict[str, str]]:
    """获取会话最近 max_rounds 轮消息（user/assistant 交替算一轮）"""
    data = _load_conversations()
    msgs = data.get("messages", {}).get(conversation_id, [])
    if max_rounds <= 0:
        return msgs
    # 每 2 条为一轮
    keep_count = min(len(msgs), max_rounds * 2)
    return msgs[-keep_count:] if keep_count else []


def append_messages(
    conversation_id: str,
    user_content: str,
    assistant_content: str,
    user_id: str = "default",
) -> None:
    """追加一轮 user + assistant 消息，并更新会话时间"""
    data = _load_conversations()
    convos = data.get("conversations", {})
    msgs_map = data.get("messages", {})

    if conversation_id not in convos:
        convos[conversation_id] = {
            "id": conversation_id,
            "user_id": user_id,
            "title": _truncate_title(user_content),
            "created_at": _now_str(),
            "updated_at": _now_str(),
        }
    else:
        convos[conversation_id]["updated_at"] = _now_str()
        if not convos[conversation_id].get("title") or convos[conversation_id]["title"] == "新对话":
            convos[conversation_id]["title"] = _truncate_title(user_content)

    if conversation_id not in msgs_map:
        msgs_map[conversation_id] = []
    msgs_map[conversation_id].append({"role": "user", "content": user_content})
    msgs_map[conversation_id].append({"role": "assistant", "content": assistant_content})

    data["conversations"] = convos
    data["messages"] = msgs_map
    _save_conversations(data)


def delete_conversation(conversation_id: str) -> bool:
    """删除会话及其消息"""
    data = _load_conversations()
    convos = data.get("conversations", {})
    msgs_map = data.get("messages", {})
    if conversation_id in convos:
        del convos[conversation_id]
    if conversation_id in msgs_map:
        del msgs_map[conversation_id]
    data["conversations"] = convos
    data["messages"] = msgs_map
    _save_conversations(data)
    return True


def _now_str() -> str:
    from datetime import datetime
    return datetime.now().isoformat()


def _truncate_title(text: str, max_len: int = 30) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text or "新对话"
    return text[: max_len - 2] + ".."
