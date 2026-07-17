"""微博 HTTP 请求共享常量。"""

from __future__ import annotations

from typing import Any

WEIBO_DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.0.0 Safari/537.36"
)
WEIBO_SPA_CONFIG_URL = "https://weibo.com/ajax/getSpaConfig"
WEIBO_CHAOHUA_LIST_URL = "https://weibo.com/ajax/profile/topicContent"


def extract_weibo_login_uid(payload: Any) -> str:
    """从微博 SPA 配置响应中提取已登录 UID；匿名响应返回空字符串。"""
    if not isinstance(payload, dict) or payload.get("ok") != 1:
        return ""
    data = payload.get("data")
    if not isinstance(data, dict):
        return ""
    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    uid = str(data.get("uid") or user.get("idstr") or user.get("id") or "").strip()
    if not uid.isdigit() or not 5 <= len(uid) <= 20:
        return ""
    return uid
