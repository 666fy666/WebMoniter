"""统一推送的轻可爱文案风格，保留原始业务信息与富文本结构。"""

from __future__ import annotations

import re

from src.push_channel.rich_text import RichText, RichTextBuilder

_CUTE_TITLE_PREFIXES = (
    "✨",
    "🎬",
    "🖼️",
    "💬",
    "🌟",
    "📝",
    "🍃",
    "🍪",
    "🎉",
    "🥺",
    "🌙",
    "🎙️",
    "📮",
    "🌤️",
    "🎱",
    "🌱",
)
_CUTE_BODY_PREFIXES = (
    "✨",
    "🎬",
    "🖼️",
    "💬",
    "🌟",
    "📝",
    "🍃",
    "🍪",
    "🎉",
    "🥺",
    "🌙",
    "🎙️",
    "📮",
    "🌤️",
    "🎱",
    "🌱",
    "🎁",
    "🌷",
    "📣",
    "🛠️",
    "🧾",
    "✅",
    "❌",
    "⚠️",
)
_SUPPORTED_KEYWORDS = (
    "开播",
    "下播",
    "动态",
    "投稿",
    "签到",
    "打卡",
    "抽奖",
    "续期",
    "预约",
    "天气",
    "开奖",
    "任务",
    "结果",
    "通知",
    "提醒",
    "成功",
    "失败",
    "中奖",
    "Cookie",
    "cookie",
)
_DECORATIVE_EMOJI_RE = re.compile(r"[🐯🐟🎬💤📺📕]+")


def _clean_title(value: object) -> str:
    title = _DECORATIVE_EMOJI_RE.sub("", str(value or "")).strip()
    title = re.sub(r"^[⚠️\s]+", "", title)
    return title.rstrip(" !！。~～")


def _title_category(title: str) -> str:
    lowered = title.lower()
    if "cookie" in lowered and any(word in title for word in ("失效", "过期")):
        return "cookie"
    if any(word in title for word in ("失败", "错误", "异常", "失效", "过期")):
        return "failure"
    if "下播" in title:
        return "offline"
    if "开播" in title:
        return "live"
    if any(word in title for word in ("发动态", "转发了动态", "投稿")):
        return "dynamic"
    if "天气" in title:
        return "weather"
    if "开奖" in title:
        return "lottery"
    if any(word in title for word in ("成功", "中奖")):
        return "success"
    if any(word in title for word in ("结果", "完成", "通知", "提醒")):
        return "report"
    return "task"


def _should_style(title: str) -> bool:
    return (
        bool(title)
        and not title.startswith(_CUTE_TITLE_PREFIXES)
        and any(keyword in title for keyword in _SUPPORTED_KEYWORDS)
    )


def style_push_title(value: object) -> str:
    """将任务标题调整为轻可爱语气；已经符合风格的标题保持不变。"""
    raw_title = str(value or "").strip()
    if not _should_style(raw_title):
        return raw_title

    title = _clean_title(raw_title)
    category = _title_category(title)
    if category == "cookie":
        return f"🍪 {title}啦"
    if category == "failure":
        return f"🥺 {title}，这次遇到一点小状况"
    if category == "offline":
        title = re.sub(r"下播(?:了|啦)?", "下播休息", title)
        return f"🌙 {title}啦～"
    if category == "live":
        title = re.sub(r"开播(?:了|啦)?", "开播", title)
        return f"🎙️ {title}啦～"
    if category == "dynamic":
        title = title.replace("转发了动态", "转来一条新动态")
        title = title.replace("发动态了", "发了条新动态")
        title = title.replace("投稿了", "带来一份新投稿")
        return f"✨ {title}～"
    if category == "weather":
        return f"🌤️ {title}来报到啦～"
    if category == "lottery":
        return f"🎱 {title}新鲜出炉啦～"
    if category == "success":
        return f"🎉 {title}啦～"
    if category == "report":
        if title.endswith("完成"):
            return f"📮 {title.removesuffix('完成')}小报告整理好啦～"
        if title.endswith("结果"):
            return f"📮 {title}来啦～"
        return f"📮 {title}来啦～"
    return f"🌱 {title}来报到啦～"


def _description_lead(title: str) -> str:
    category = _title_category(_clean_title(title))
    leads = {
        "cookie": "🛠️ 登录状态需要照顾一下，详情放在这里啦：",
        "failure": "🛠️ 这次遇到一点小状况，详情放在这里啦：",
        "offline": "🌙 直播间安静下来啦，记录放在这里～",
        "live": "📣 直播间有新动静啦～",
        "dynamic": "🌷 新内容送到啦～",
        "weather": "🌤️ 今天的天气小纸条来啦～",
        "lottery": "🎱 本期结果已经整理好啦～",
        "success": "🎁 好耶，今天的任务顺利完成啦～",
        "report": "🧾 今天的小报告整理好啦～",
        "task": "🌱 今天的任务消息来报到啦～",
    }
    return leads[category]


def style_push_description(
    title: object,
    description: str | RichText,
) -> str | RichText:
    """为普通任务正文增加一致的轻可爱引导语，正文内容原样保留。"""
    raw_title = str(title or "").strip()
    if not _should_style(raw_title):
        return description

    visible = description.plain_text() if isinstance(description, RichText) else str(description)
    if visible.lstrip().startswith(_CUTE_BODY_PREFIXES):
        return description

    lead = _description_lead(raw_title)
    if isinstance(description, RichText):
        builder = RichTextBuilder().text(lead)
        if description:
            builder.text("\n\n").rich(description)
        return builder.build()

    body = str(description or "").strip()
    return f"{lead}\n\n{body}" if body else lead
