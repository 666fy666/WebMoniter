"""Web 认证状态与凭据读写。"""

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

AUTH_FILE = Path("data/auth.json")
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "123"

# 当前进程内的登录会话。SessionMiddleware 存 session_id，这里保存已登录 id。
active_sessions: set[str] = set()


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


def check_login(session_id: str | None) -> bool:
    """检查用户是否已登录。"""
    return session_id is not None and session_id in active_sessions

