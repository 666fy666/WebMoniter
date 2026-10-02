"""Web 数据 API 的平台元数据与行转换。"""

import json
import re
from functools import lru_cache
from urllib.parse import urlsplit

from src.core.weibo_dates import (
    _parse_weibo_created_at as _parse_weibo_created_at,
)
from src.core.weibo_dates import (
    _parse_weibo_timestamp,
    _weibo_timestamp_text,
)

# 平台配置：table_name, primary_key, filter_query_param
PLATFORM_CONFIG = {
    "weibo": ("weibo", "UID", "uid"),
    "huya": ("huya", "room", "room"),
    "bilibili_live": ("bilibili_live", "uid", "uid"),
    "bilibili_dynamic": ("bilibili_dynamic", "uid", "uid"),
    "douyin": ("douyin", "douyin_id", "id"),
    "kuaishou": ("kuaishou", "principal_id", "id"),
    "douyu": ("douyu", "room", "room"),
    "xhs": ("xhs", "profile_id", "id"),
}
PLATFORM_PRIMARY_KEY = {k: v[1] for k, v in PLATFORM_CONFIG.items()}
VALID_PLATFORMS = frozenset(PLATFORM_CONFIG)
WEIBO_CONTENT_TYPES = {"repost", "video", "image", "text"}


def _safe_http_url(raw: object) -> str:
    value = str(raw or "").strip()
    if value.startswith("//"):
        value = f"https:{value}"
    if re.search(r"[\x00-\x20\x7f]", value):
        return ""
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return ""
    return value


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


def _parse_weibo_content_segments(raw: object) -> list[dict[str, str]]:
    """解析安全的微博正文片段，链接仅允许 HTTP(S)。"""
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            values = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    else:
        return []

    result: list[dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "")
        if not text:
            continue
        text = re.sub(
            r"(?:https?:)?//[^\s<>'\"\]\[）)]+",
            "网页链接",
            text,
            flags=re.IGNORECASE,
        )
        segment_type = item.get("type")
        if segment_type == "emoji":
            src = _safe_http_url(item.get("src"))
            if src:
                result.append({"type": "emoji", "text": text, "src": src})
                continue
        if segment_type == "link":
            url = _safe_http_url(item.get("url"))
            if url:
                result.append({"type": "link", "text": text, "url": url})
                continue
        result.append({"type": "text", "text": text})
    return result


def _parse_weibo_tags(raw: object) -> list[str]:
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            values = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    else:
        return []
    result: list[str] = []
    for item in values:
        tag = str(item or "").strip()
        if tag and tag not in result:
            result.append(tag)
    return result


def _parse_weibo_content_type(
    raw: object,
    *,
    has_repost: bool = False,
    has_video: bool = False,
    has_images: bool = False,
) -> str:
    value = str(raw or "").strip().lower()
    if has_repost:
        return "repost"
    if has_video and value in {"", "text"}:
        return "video"
    if has_images and value in {"", "text"}:
        return "image"
    if value in WEIBO_CONTENT_TYPES:
        return value
    if has_video:
        return "video"
    if has_images:
        return "image"
    return "text"


def _parse_weibo_retweeted_status(raw: str | None) -> dict | None:
    """解析 weibo.转发微博 JSON 字段，返回前端可直接渲染的结构。"""
    if not raw or not isinstance(raw, str):
        return None
    try:
        repost = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(repost, dict) or not repost:
        return None

    images = repost.get("images")
    if not isinstance(images, list):
        images = []
    clean_images = [item.strip() for item in images if isinstance(item, str) and item.strip()]
    content_segments = _parse_weibo_content_segments(repost.get("content_segments"))
    tags = _parse_weibo_tags(repost.get("tags"))
    video_cover = str(repost.get("video_cover") or "").strip()

    mid = str(repost.get("mid") or "").strip()
    user_name = str(repost.get("user_name") or "").strip()
    text = str(repost.get("text") or "").strip()
    if not any([mid, user_name, text, clean_images, video_cover, repost.get("source_unavailable")]):
        return None

    return {
        "user_id": str(repost.get("user_id") or "").strip(),
        "user_name": user_name or "未知用户",
        "verified": str(repost.get("verified") or "").strip(),
        "text": text,
        "content_segments": content_segments,
        "tags": tags,
        "content_type": _parse_weibo_content_type(
            repost.get("content_type"),
            has_video=bool(video_cover),
            has_images=bool(clean_images),
        ),
        "created_at": str(repost.get("created_at") or "").strip(),
        "mid": mid,
        "images": clean_images,
        "image_thumbs": [_weibo_thumb_url(image) for image in clean_images],
        "video_cover": video_cover,
        "video_cover_thumb": _weibo_thumb_url(video_cover) if video_cover else "",
        "url": f"https://m.weibo.cn/detail/{mid}" if mid else "",
        "source_unavailable": bool(repost.get("source_unavailable")),
    }


def _weibo_thumb_url(image_url: str) -> str:
    """按保存规则从原图 URL 推导缩略图 URL。"""
    if "/" not in image_url:
        return image_url
    parent, filename = image_url.rsplit("/", 1)
    if "." not in filename:
        return image_url
    stem, _ = filename.rsplit(".", 1)
    return f"{parent}/{stem}.thumb.jpg"


def _sort_weibo_index(index: tuple[tuple[object, str | None], ...]) -> tuple[object, ...]:
    def sort_key(row: tuple) -> float:
        created_at = _parse_weibo_timestamp(row[1]) if row[1] is not None else None
        return created_at.timestamp() if created_at is not None else 0.0

    return tuple(row[0] for row in sorted(index, key=sort_key, reverse=True))


@lru_cache(maxsize=2)
def _cached_weibo_order(index: tuple[tuple[object, str | None], ...]) -> tuple[object, ...]:
    return _sort_weibo_index(index)


def _weibo_page_ids(rows: list[tuple], offset: int, page_size: int) -> list[object]:
    index = tuple((row[0], _weibo_timestamp_text(row[1])) for row in rows)
    # 键来自每次权威查询的 UID、时间和原始顺序；不保留正文，限制两份 4096 行索引。
    can_cache = len(index) <= 4096 and all(
        isinstance(uid, str) and len(uid) <= 255 for uid, _ in index
    )
    order = _cached_weibo_order(index) if can_cache else _sort_weibo_index(index)
    return list(order[offset : offset + page_size])


def _weibo_row_to_item(row: tuple) -> dict:
    mid = row[7] if len(row) > 7 else ""
    images = _parse_weibo_images(row[8] if len(row) > 8 else None)
    retweeted_status = _parse_weibo_retweeted_status(row[9] if len(row) > 9 else None)
    content_segments = _parse_weibo_content_segments(row[10] if len(row) > 10 else None)
    tags = _parse_weibo_tags(row[11] if len(row) > 11 else None)
    video_cover = str(row[13] or "") if len(row) > 13 else ""
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
        "retweeted_status": retweeted_status,
        "content_segments": content_segments,
        "tags": tags,
        "content_type": _parse_weibo_content_type(
            row[12] if len(row) > 12 else None,
            has_repost=bool(retweeted_status),
            has_video=bool(video_cover),
            has_images=bool(images),
        ),
        "video_cover": video_cover,
        "video_cover_thumb": _weibo_thumb_url(video_cover) if video_cover else "",
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


def _kuaishou_row_to_item(row: tuple) -> dict:
    return {
        "principal_id": row[0],
        "name": row[1],
        "is_live": row[2],
        "url": f"https://live.kuaishou.com/u/{row[0]}",
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
        "kuaishou": _kuaishou_row_to_item,
        "douyu": _douyu_row_to_item,
        "xhs": _xhs_row_to_item,
    }
    return converters.get(platform, lambda r: dict(zip(range(len(r)), r)))(row)


# 各平台 SELECT 列与表名。
_PLATFORM_SELECT = {
    "weibo": (
        "weibo",
        "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid, 图片, "
        "转发微博, 正文结构, 标签, 内容类型, 视频封面 FROM weibo WHERE UID = :pk",
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
    "kuaishou": (
        "kuaishou",
        "SELECT principal_id, name, is_live FROM kuaishou WHERE principal_id = :pk",
    ),
    "douyu": ("douyu", "SELECT room, name, is_live FROM douyu WHERE room = :pk"),
    "xhs": (
        "xhs",
        "SELECT profile_id, user_name, latest_note_title FROM xhs WHERE profile_id = :pk",
    ),
}

_PLATFORM_LIST_SQL = {
    "weibo": (
        "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid, 图片, "
        "转发微博, 正文结构, 标签, 内容类型, 视频封面 FROM weibo"
    ),
    "huya": "SELECT room, name, is_live, room_pic, avatar_url FROM huya",
    "bilibili_live": "SELECT uid, uname, room_id, is_live FROM bilibili_live",
    "bilibili_dynamic": "SELECT uid, uname, dynamic_id, dynamic_text FROM bilibili_dynamic",
    "douyin": "SELECT douyin_id, name, is_live FROM douyin",
    "kuaishou": "SELECT principal_id, name, is_live FROM kuaishou",
    "douyu": "SELECT room, name, is_live FROM douyu",
    "xhs": "SELECT profile_id, user_name, latest_note_title FROM xhs",
}

_PLATFORM_LIST_SQL_HUYA_BASIC = "SELECT room, name, is_live FROM huya"
