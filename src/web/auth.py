"""Web 认证状态与凭据读写。"""

import hashlib
import json
import logging
import time
from threading import RLock

from src.core.paths import AUTH_FILE, WEB_SESSION_FILE

logger = logging.getLogger(__name__)
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "123"
WEB_SESSION_MAX_AGE_SECONDS = 365 * 24 * 60 * 60
WEB_SESSION_RENEW_WITHIN_SECONDS = 30 * 24 * 60 * 60

# 当前进程内的登录会话缓存；权威数据持久化在 data/web_sessions.json。
active_sessions: set[str] = set()
_session_lock = RLock()


def _now_ts() -> int:
    return int(time.time())


def hash_password(password: str) -> str:
    """使用 SHA-256 哈希密码。"""
    return hashlib.sha256(password.encode()).hexdigest()


def load_auth() -> dict:
    """加载认证信息，如果文件不存在则返回默认值。"""
    if AUTH_FILE.exists():
        try:
            with open(AUTH_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("加载认证文件失败: %s", e)
    return {
        "username": DEFAULT_USERNAME,
        "password_hash": hash_password(DEFAULT_PASSWORD),
    }


def save_auth(auth_data: dict) -> bool:
    """保存认证信息到文件。"""
    try:
        AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(auth_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error("保存认证文件失败: %s", e)
        return False


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码。"""
    return hash_password(password) == password_hash


def _session_expires_at(now: int | None = None) -> int:
    return (now if now is not None else _now_ts()) + WEB_SESSION_MAX_AGE_SECONDS


def _normalize_session_records(raw_data: object, now: int) -> dict[str, dict[str, int]]:
    if not isinstance(raw_data, dict):
        return {}

    raw_sessions = raw_data.get("sessions", raw_data)
    if not isinstance(raw_sessions, dict):
        return {}

    records: dict[str, dict[str, int]] = {}
    for session_id, record in raw_sessions.items():
        if not isinstance(session_id, str) or not session_id:
            continue

        expires_at: int | None = None
        if isinstance(record, dict):
            raw_expires_at = record.get("expires_at")
        else:
            raw_expires_at = record

        try:
            expires_at = int(raw_expires_at)
        except (TypeError, ValueError):
            expires_at = None

        if expires_at is not None and expires_at > now:
            records[session_id] = {"expires_at": expires_at}
    return records


def _save_session_records_locked(records: dict[str, dict[str, int]]) -> None:
    WEB_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "max_age_seconds": WEB_SESSION_MAX_AGE_SECONDS,
        "sessions": records,
    }
    temp_file = WEB_SESSION_FILE.with_suffix(WEB_SESSION_FILE.suffix + ".tmp")
    temp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_file.replace(WEB_SESSION_FILE)


def _load_session_records_locked(*, persist_purge: bool = True) -> dict[str, dict[str, int]]:
    now = _now_ts()
    if not WEB_SESSION_FILE.is_file():
        active_sessions.clear()
        return {}

    try:
        raw_data = json.loads(WEB_SESSION_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("加载 Web 登录会话失败: %s", e)
        active_sessions.clear()
        return {}

    records = _normalize_session_records(raw_data, now)
    raw_sessions = (
        raw_data.get("sessions", raw_data)
        if isinstance(raw_data, dict)
        else None
    )
    raw_count = len(raw_sessions) if isinstance(raw_sessions, dict) else len(records)
    if persist_purge and raw_count != len(records):
        try:
            _save_session_records_locked(records)
        except Exception as e:
            logger.error("清理过期 Web 登录会话失败: %s", e)

    active_sessions.clear()
    active_sessions.update(records)
    return records


def register_session(session_id: str) -> int:
    """登记并持久化一个登录会话，返回过期时间戳。"""
    with _session_lock:
        records = _load_session_records_locked()
        expires_at = _session_expires_at()
        records[session_id] = {"expires_at": expires_at}
        _save_session_records_locked(records)
        active_sessions.add(session_id)
        return expires_at


def revoke_session(session_id: str | None) -> None:
    """撤销一个登录会话。"""
    if not session_id:
        return
    with _session_lock:
        records = _load_session_records_locked()
        records.pop(session_id, None)
        _save_session_records_locked(records)
        active_sessions.discard(session_id)


def replace_sessions_with(session_id: str) -> int:
    """清空其它会话，仅保留当前会话；用于修改密码后收敛旧登录态。"""
    with _session_lock:
        expires_at = _session_expires_at()
        records = {session_id: {"expires_at": expires_at}}
        _save_session_records_locked(records)
        active_sessions.clear()
        active_sessions.add(session_id)
        return expires_at


def check_login(session_id: str | None) -> bool:
    """检查用户是否已登录。"""
    if not session_id:
        return False

    with _session_lock:
        records = _load_session_records_locked()
        record = records.get(session_id)
        if not record:
            active_sessions.discard(session_id)
            return False

        now = _now_ts()
        remaining = record["expires_at"] - now
        if remaining <= 0:
            records.pop(session_id, None)
            _save_session_records_locked(records)
            active_sessions.discard(session_id)
            return False

        if remaining < WEB_SESSION_RENEW_WITHIN_SECONDS:
            record["expires_at"] = _session_expires_at(now)
            _save_session_records_locked(records)

        active_sessions.add(session_id)
        return True
