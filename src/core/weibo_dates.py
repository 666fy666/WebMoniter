"""Shared Weibo publication time parsing for ingestion and presentation."""

import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache


def _parse_weibo_created_at(text: str | None) -> datetime | None:
    """
    从微博文本中解析发布时间。文本格式为 "...\n\n{created_at}"。
    支持格式：Thu Feb 12 17:35:47 +0800 2026 等。
    """
    raw = _weibo_timestamp_text(text)
    return _parse_weibo_timestamp(raw) if raw is not None else None


def _weibo_timestamp_text(text: str | None) -> str | None:
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

    return raw


@lru_cache(maxsize=2048)
def _parse_weibo_timestamp(raw: str) -> datetime | None:
    # 只缓存短时间字段，避免持有完整正文；新时间自然生成新缓存键。
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
