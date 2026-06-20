"""Web 数据 API 的平台元数据与行转换。"""

import json
import re
from datetime import datetime, timedelta, timezone

# 平台配置：table_name, primary_key, filter_query_param
PLATFORM_CONFIG = {
    "weibo": ("weibo", "UID", "uid"),
    "huya": ("huya", "room", "room"),
    "bilibili_live": ("bilibili_live", "uid", "uid"),
    "bilibili_dynamic": ("bilibili_dynamic", "uid", "uid"),
    "douyin": ("douyin", "douyin_id", "id"),
    "douyu": ("douyu", "room", "room"),
    "xhs": ("xhs", "profile_id", "id"),
}
PLATFORM_PRIMARY_KEY = {k: v[1] for k, v in PLATFORM_CONFIG.items()}
VALID_PLATFORMS = frozenset(PLATFORM_CONFIG)


def _parse_weibo_images(raw: str | None) -> list[str]:
    """解析 weibo.图片 JSON 字段，异常或旧数据返回空数组。"""
    if not raw or not isinstance(raw, str):
        return []
    try:
        images = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(images, list):
        return []
    return [item.strip() for item in images if isinstance(item, str) and item.strip()]


def _weibo_thumb_url(image_url: str) -> str:
    """按保存规则从原图 URL 推导缩略图 URL。"""
    if "/" not in image_url:
        return image_url
    parent, filename = image_url.rsplit("/", 1)
    if "." not in filename:
        return image_url
    stem, _ = filename.rsplit(".", 1)
    return f"{parent}/{stem}.thumb.jpg"


def _parse_weibo_created_at(text: str | None) -> datetime | None:
    """
    从微博文本中解析发布时间。文本格式为 "...\n\n{created_at}"。
    支持格式：Thu Feb 12 17:35:47 +0800 2026 等。
    """
    if not text or not isinstance(text, str):
        return None
    raw = None
    for sep in ("\n\n", "\r\n\r\n"):
        if sep in text:
            parts = text.rsplit(sep, 1)
            if len(parts) >= 2:
                raw = parts[-1].strip()
                break
    if not raw or len(raw) > 80:
        return None

    formats = [
        "%a %b %d %H:%M:%S %z %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%b %d %H:%M:%S %z %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except (ValueError, TypeError):
            continue

    m = re.match(
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        r"(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})\s+([+-]\d{4})\s+(\d{4})",
        raw,
    )
    if m:
        try:
            months = {
                "Jan": 1,
                "Feb": 2,
                "Mar": 3,
                "Apr": 4,
                "May": 5,
                "Jun": 6,
                "Jul": 7,
                "Aug": 8,
                "Sep": 9,
                "Oct": 10,
                "Nov": 11,
                "Dec": 12,
            }
            month = months.get(m.group(1), 1)
            tz_str = m.group(6)
            sign = 1 if tz_str[0] == "+" else -1
            tz_h = sign * int(tz_str[1:3])
            tz_m = sign * int(tz_str[3:5]) if len(tz_str) >= 5 else 0
            tz = timezone(timedelta(hours=tz_h, minutes=tz_m))
            return datetime(
                int(m.group(7)),
                month,
                int(m.group(2)),
                int(m.group(3)),
                int(m.group(4)),
                int(m.group(5)),
                tzinfo=tz,
            )
        except (ValueError, KeyError, IndexError):
            pass
    return None


def _weibo_row_to_item(row: tuple) -> dict:
    mid = row[7] if len(row) > 7 else ""
    images = _parse_weibo_images(row[8] if len(row) > 8 else None)
    return {
        "UID": row[0],
        "用户名": row[1],
        "认证信息": row[2],
        "简介": row[3],
        "粉丝数": row[4],
        "微博数": row[5],
        "文本": row[6],
        "mid": mid,
        "images": images,
        "image_thumbs": [_weibo_thumb_url(image) for image in images],
        "url": f"https://m.weibo.cn/detail/{mid}" if mid else f"https://www.weibo.com/u/{row[0]}",
    }


def _huya_row_to_item(row: tuple) -> dict:
    return {
        "room": row[0],
        "name": row[1],
        "is_live": row[2],
        "room_pic": row[3] if len(row) > 3 else "",
        "avatar_url": row[4] if len(row) > 4 else "",
        "url": f"https://www.huya.com/{row[0]}",
    }


def _weibo_row_to_status_item(row: tuple) -> dict:
    images = _parse_weibo_images(row[8] if len(row) > 8 else None)
    return {
        "UID": row[0],
        "用户名": row[1],
        "认证信息": row[2],
        "简介": row[3],
        "粉丝数": row[4],
        "微博数": row[5],
        "文本": row[6],
        "mid": row[7],
        "images": images,
        "image_thumbs": [_weibo_thumb_url(image) for image in images],
    }


def _huya_row_to_status_item(row: tuple) -> dict:
    return {"room": row[0], "name": row[1], "is_live": row[2]}


def _bilibili_live_row_to_item(row: tuple) -> dict:
    return {
        "uid": row[0],
        "uname": row[1],
        "room_id": row[2],
        "is_live": row[3],
        "url": f"https://live.bilibili.com/{row[2]}" if row[2] else "",
    }


def _bilibili_dynamic_row_to_item(row: tuple) -> dict:
    return {
        "uid": row[0],
        "uname": row[1],
        "dynamic_id": row[2],
        "dynamic_text": row[3] or "",
        "url": (
            f"https://www.bilibili.com/opus/{row[2]}"
            if row[2]
            else f"https://space.bilibili.com/{row[0]}"
        ),
    }


def _douyin_row_to_item(row: tuple) -> dict:
    return {
        "douyin_id": row[0],
        "name": row[1],
        "is_live": row[2],
        "url": f"https://live.douyin.com/{row[0]}",
    }


def _douyu_row_to_item(row: tuple) -> dict:
    return {
        "room": row[0],
        "name": row[1],
        "is_live": row[2],
        "url": f"https://www.douyu.com/{row[0]}",
    }


def _xhs_row_to_item(row: tuple) -> dict:
    return {
        "profile_id": row[0],
        "user_name": row[1],
        "latest_note_title": row[2] or "",
        "url": f"https://www.xiaohongshu.com/user/profile/{row[0]}",
    }


def _row_to_item(platform: str, row: tuple) -> dict:
    """根据平台将行转为 API 返回项。"""
    converters = {
        "weibo": _weibo_row_to_item,
        "huya": _huya_row_to_item,
        "bilibili_live": _bilibili_live_row_to_item,
        "bilibili_dynamic": _bilibili_dynamic_row_to_item,
        "douyin": _douyin_row_to_item,
        "douyu": _douyu_row_to_item,
        "xhs": _xhs_row_to_item,
    }
    return converters.get(platform, lambda r: dict(zip(range(len(r)), r)))(row)


# 各平台 SELECT 列与表名。
_PLATFORM_SELECT = {
    "weibo": (
        "weibo",
        "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid, 图片 FROM weibo WHERE UID = :pk",
    ),
    "huya": ("huya", "SELECT room, name, is_live FROM huya WHERE room = :pk"),
    "bilibili_live": (
        "bilibili_live",
        "SELECT uid, uname, room_id, is_live FROM bilibili_live WHERE uid = :pk",
    ),
    "bilibili_dynamic": (
        "bilibili_dynamic",
        "SELECT uid, uname, dynamic_id, dynamic_text FROM bilibili_dynamic WHERE uid = :pk",
    ),
    "douyin": ("douyin", "SELECT douyin_id, name, is_live FROM douyin WHERE douyin_id = :pk"),
    "douyu": ("douyu", "SELECT room, name, is_live FROM douyu WHERE room = :pk"),
    "xhs": (
        "xhs",
        "SELECT profile_id, user_name, latest_note_title FROM xhs WHERE profile_id = :pk",
    ),
}

_PLATFORM_LIST_SQL = {
    "weibo": "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid, 图片 FROM weibo",
    "huya": "SELECT room, name, is_live, room_pic, avatar_url FROM huya",
    "bilibili_live": "SELECT uid, uname, room_id, is_live FROM bilibili_live",
    "bilibili_dynamic": "SELECT uid, uname, dynamic_id, dynamic_text FROM bilibili_dynamic",
    "douyin": "SELECT douyin_id, name, is_live FROM douyin",
    "douyu": "SELECT room, name, is_live FROM douyu",
    "xhs": "SELECT profile_id, user_name, latest_note_title FROM xhs",
}

_PLATFORM_LIST_SQL_HUYA_BASIC = "SELECT room, name, is_live FROM huya"
