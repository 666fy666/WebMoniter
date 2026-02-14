"""当前状态查询 - 从数据库获取各平台最新监控数据"""

import logging

logger = logging.getLogger(__name__)

VALID_PLATFORMS = {"weibo", "huya", "bilibili_live", "bilibili_dynamic", "douyin", "douyu", "xhs"}

# 具体平台名称 -> 内部 key（用户指定时只查这些）
_PLATFORM_ALIASES: dict[str, list[str]] = {
    "虎牙": ["huya"],
    "微博": ["weibo"],
    "哔哩哔哩": ["bilibili_live", "bilibili_dynamic"],
    "b站": ["bilibili_live", "bilibili_dynamic"],
    "bilibili": ["bilibili_live", "bilibili_dynamic"],
    "抖音": ["douyin"],
    "斗鱼": ["douyu"],
    "小红书": ["xhs"],
}
#  generic 关键词：未指定具体平台时，用这些扩充（直播=各直播平台，动态=微博/B站动态/小红书）
_PLATFORM_GENERIC: dict[str, list[str]] = {
    "直播": ["huya", "bilibili_live", "douyin", "douyu"],
    "动态": ["weibo", "bilibili_dynamic", "xhs"],
}

_PLATFORM_SQL = {
    "weibo": "SELECT UID, 用户名, 认证信息, 粉丝数, 微博数, 文本, mid FROM weibo",
    "huya": "SELECT room, name, is_live FROM huya",
    "bilibili_live": "SELECT uid, uname, room_id, is_live FROM bilibili_live",
    "bilibili_dynamic": "SELECT uid, uname, dynamic_id, dynamic_text FROM bilibili_dynamic",
    "douyin": "SELECT douyin_id, name, is_live FROM douyin",
    "douyu": "SELECT room, name, is_live FROM douyu",
    "xhs": "SELECT profile_id, user_name, latest_note_title FROM xhs",
}

_PLATFORM_DISPLAY = {
    "weibo": "微博",
    "huya": "虎牙",
    "bilibili_live": "B站直播",
    "bilibili_dynamic": "B站动态",
    "douyin": "抖音",
    "douyu": "斗鱼",
    "xhs": "小红书",
}


def parse_platforms_from_message(message: str) -> list[str] | None:
    """
    从用户消息中解析要查询的平台，返回去重后的平台列表。
    - 若识别到具体平台（虎牙/微博/B站等），只查这些平台
    - 若仅识别到 generic 词（直播/动态），查对应类别
    - 若都未识别，返回 None 表示查全部
    """
    msg_lower = message.lower().strip()
    explicit: set[str] = set()
    for alias, platforms in _PLATFORM_ALIASES.items():
        if alias in message or alias in msg_lower:
            explicit.update(platforms)
    if explicit:
        return list(explicit)
    generic: set[str] = set()
    for alias, platforms in _PLATFORM_GENERIC.items():
        if alias in message or alias in msg_lower:
            generic.update(platforms)
    if generic:
        return list(generic)
    return None


async def query_current_state(platforms: list[str] | None = None) -> str:
    """
    查询数据库中各平台当前最新状态，返回结构化文本供 LLM 组织回答。
    platforms 为 None 或空时查询所有平台；否则只查指定平台。
    """
    try:
        from src.database import AsyncDatabase
    except ImportError:
        return "无法连接数据库"

    db = AsyncDatabase()
    await db.initialize()

    to_query = (
        [p for p in (platforms or []) if p in VALID_PLATFORMS]
        if platforms
        else list(VALID_PLATFORMS)
    )
    lines: list[str] = []

    for p in to_query:
        sql = _PLATFORM_SQL.get(p)
        if not sql:
            continue
        label = _PLATFORM_DISPLAY.get(p, p)
        try:
            rows = await db.execute_query(sql)
            if not rows:
                lines.append(f"【{label}】暂无数据")
                continue
            for i, row in enumerate(rows[:10]):
                parts = [str(v) if v is not None else "" for v in row]
                lines.append(f"【{label}】{i + 1}. " + " | ".join(parts))
            if len(rows) > 10:
                lines.append(f"【{label}】... 共 {len(rows)} 条")
        except Exception as e:
            logger.debug("查询 %s 失败: %s", p, e)
            lines.append(f"【{label}】查询失败")

    return "\n".join(lines) if lines else "暂无监控数据"
