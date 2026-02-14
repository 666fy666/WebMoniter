"""微博用户搜索：通过昵称搜索并返回候选 UID 列表。

使用微博搜索建议 API 根据昵称查询用户，返回格式化的候选列表，
供 AI 助手在「关注XX的微博」时让用户选择要添加的具体账号。
"""

import logging
import re
from typing import Any
from urllib.parse import quote

import aiohttp
from aiohttp import ClientTimeout

logger = logging.getLogger(__name__)

# 多个候选 API（不同域名/路径，微博历史版本可能不同）
# 参数名 key 或 q 因接口版本而异
_SUGGESTION_ENDPOINTS = [
    "https://www.weibo.com/ajax/suggestion",
    "https://weibo.com/ajax/suggestion",
    "https://s.weibo.com/ajax/suggestion",
]
_SUGGESTION_PARAMS = ("key", "q")


def _parse_users_from_response(data: dict) -> list[dict[str, Any]]:
    """从 API 响应中解析用户列表。支持 data.users / data.user 结构。"""
    result: list[dict[str, Any]] = []
    if not isinstance(data, dict):
        return result
    inner = data.get("data") or {}
    users = inner.get("users") or inner.get("user") or []
    for u in users:
        if not isinstance(u, dict):
            continue
        uid = u.get("id") or u.get("uid") or u.get("idstr")
        if uid is None:
            continue
        uid_str = str(uid)
        nick = u.get("screen_name") or u.get("nick") or u.get("name") or ""
        followers = u.get("followers_count_str") or ""
        verified = u.get("verified_reason") or ""
        result.append(
            {
                "uid": uid_str,
                "nick": nick or uid_str,
                "followers_count_str": followers,
                "verified_reason": verified,
            }
        )
    return result


async def search_weibo_users(keyword: str, cookie: str) -> list[dict[str, Any]]:
    """
    根据昵称/关键词搜索微博用户，返回候选列表。

    Args:
        keyword: 搜索关键词（昵称、用户名等）
        cookie: 微博登录 Cookie（与监控配置相同）

    Returns:
        候选用户列表，每项为 {
            "uid": str,
            "nick": str,
            "followers_count_str": str,
            "verified_reason": str,
        }
        失败或无结果时返回 []。
    """
    if not keyword or not cookie or not cookie.strip():
        return []

    keyword = keyword.strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://s.weibo.com/",
        "Cookie": cookie,
        "X-Requested-With": "XMLHttpRequest",
    }

    result: list[dict[str, Any]] = []
    timeout = ClientTimeout(total=12)

    # 使用与监控相同的 Referer（www.weibo.com 确保 Cookie 生效）
    headers["Referer"] = "https://www.weibo.com/"

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for base_url in _SUGGESTION_ENDPOINTS:
                for param_name in _SUGGESTION_PARAMS:
                    params = {param_name: keyword}
                    url = base_url.rstrip("/")
                    try:
                        async with session.get(url, params=params, headers=headers) as resp:
                            if resp.status != 200:
                                logger.debug("微博搜索 %s %s 返回 %d", url, param_name, resp.status)
                                continue
                            data = await resp.json()
                            if not isinstance(data, dict):
                                continue
                            # ok 可能为 1 或 True，空 data 也尝试解析
                            if data.get("ok") not in (1, True) and "data" not in data:
                                logger.debug(
                                    "微博搜索返回 ok=%s, keys=%s",
                                    data.get("ok"),
                                    list(data.keys())[:5],
                                )
                                continue
                            result = _parse_users_from_response(data)
                            if result:
                                logger.info(
                                    "微博用户搜索成功: %s -> %d 个结果", keyword, len(result)
                                )
                                return result
                    except aiohttp.ClientError as e:
                        logger.debug("微博搜索 %s 请求异常: %s", url, e)
                    except Exception as e:
                        logger.debug("微博搜索 %s 解析异常: %s", url, e)

            # 若 suggestion 都无效，尝试综合/用户搜索接口
            for search_url, ref in [
                ("https://s.weibo.com/ajax/feed/search", "https://s.weibo.com/"),
                ("https://s.weibo.com/ajax/search/all", "https://s.weibo.com/"),
            ]:
                try:
                    async with session.get(
                        search_url,
                        params={"q": keyword, "page": 1},
                        headers={**headers, "Referer": ref},
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            # search/all 可能把用户放在 data.users 或 data.data 下
                            if isinstance(data, dict):
                                result = _parse_users_from_response(data)
                                if not result and "data" in data:
                                    inner = data.get("data") or {}
                                    if isinstance(inner, dict):
                                        result = _parse_users_from_response({"data": inner})
                                    elif isinstance(inner, list):
                                        for item in inner:
                                            if isinstance(item, dict) and (
                                                "users" in item or "user" in item
                                            ):
                                                result = _parse_users_from_response({"data": item})
                                                break
                                if result:
                                    return result
                except Exception as e:
                    logger.debug("微博搜索 %s 异常: %s", search_url, e)

            # 兜底：抓取用户搜索页，从页面中提取 /u/UID 链接（用户卡）
            try:
                page_url = f"https://s.weibo.com/user?q={quote(keyword)}"
                async with session.get(
                    page_url,
                    headers={**headers, "Referer": "https://s.weibo.com/"},
                ) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        # 提取用户主页链接中的 UID（/u/1234567890）
                        seen: set[str] = set()
                        for m in re.finditer(r"/u/(\d{8,})", text):
                            uid = m.group(1)
                            if uid not in seen:
                                seen.add(uid)
                                result.append(
                                    {
                                        "uid": uid,
                                        "nick": f"{keyword} ({uid})",
                                        "followers_count_str": "",
                                        "verified_reason": "",
                                    }
                                )
                                if len(result) >= 10:
                                    break
                        if result:
                            return result
            except Exception as e:
                logger.debug("微博用户搜索 HTML 兜底异常: %s", e)

    except aiohttp.ClientError as e:
        logger.warning("微博用户搜索请求失败: %s", e)
    except Exception as e:
        logger.warning("微博用户搜索解析失败: %s", e)

    logger.debug("微博用户搜索「%s」未找到结果", keyword)

    return result


def is_numeric_uid(value: str) -> bool:
    """判断 value 是否已是数字 UID（可直接写入配置）。"""
    s = (value or "").strip()
    return s.isdigit()
