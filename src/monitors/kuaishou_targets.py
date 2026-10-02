"""快手目标归一化与引用清理；不在配置加载时发起网络请求。"""

import hashlib
import re
from urllib.parse import parse_qs, urlsplit, urlunsplit

KUAISHOU_HOSTS = frozenset(
    {
        "live.kuaishou.com",
        "www.kuaishou.com",
        "v.kuaishou.com",
        "c.kuaishou.com",
        "www.kuaishou.cn",
        "kuaishou.cn",
        "v.m.chenzhongtech.com",
    }
)
_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


def split_targets(value: str) -> list[str]:
    return list(dict.fromkeys(x.strip() for x in re.split(r"[,，\n]+", value) if x.strip()))


def checked_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in KUAISHOU_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 80, 443}
        or re.search(r"[\s\\\x00-\x1f]", value)
    ):
        raise ValueError("只支持快手官方主页、直播间或分享链接")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def principal_from_target(target: str) -> str | None:
    if _ID.fullmatch(target):
        return target
    parsed = urlsplit(checked_url(target))
    match = re.fullmatch(r"/(?:u|profile)/([A-Za-z0-9_-]{1,128})/?", parsed.path)
    if match and parsed.hostname in {"live.kuaishou.com", "www.kuaishou.com"}:
        return match[1]
    match = re.fullmatch(r"/fw/(?:live|user)/([A-Za-z0-9_-]{1,128})/?", parsed.path)
    if match:
        return match[1]
    # App 的直播分享落地页携带主播 ID；不将一次性的 liveStreamId 当主播 ID。
    query = parse_qs(parsed.query)
    if parsed.path.rstrip("/") == "/fw/live":
        ids = query.get("principalId", [])
        if len(ids) == 1 and _ID.fullmatch(ids[0]):
            return ids[0]
    return None


def target_key(target: str) -> str:
    return hashlib.sha256(target.encode("utf-8")).hexdigest()


async def prune_targets(db, targets: list[str]) -> None:
    """仅在全部新目标可解析时清理快照，避免链接替换或暂时解析失败误删基线。"""
    rows = await db.execute_query("SELECT target_key, target, principal_id FROM kuaishou_targets")
    active = set(targets)
    resolved = {target: principal for _, target, principal in rows if target in active}
    for key, target, _ in rows:
        if target not in active:
            await db.execute_update(
                "DELETE FROM kuaishou_targets WHERE target_key=%(pk)s", {"pk": key}
            )
    for target in targets:
        try:
            principal = principal_from_target(target)
        except ValueError:
            return
        if principal:
            resolved[target] = principal
    if not active <= resolved.keys():
        return
    keep = set(resolved.values())
    for (principal,) in await db.execute_query("SELECT principal_id FROM kuaishou"):
        if principal not in keep:
            await db.execute_update(
                "DELETE FROM kuaishou WHERE principal_id=%(pk)s", {"pk": principal}
            )
