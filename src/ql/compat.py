"""
青龙面板兼容模块 - 使 WebMoniter 可在青龙面板中运行

在不改变现有项目逻辑的前提下，提供：
1. 环境变量配置加载（青龙用户通过环境变量配置参数）
2. QLAPI 推送通道（兼容青龙内置通知）

使用方式：在青龙面板中添加定时任务，执行 src/ql/ 目录下对应的脚本即可。
环境变量命名规范见 docs/QINGLONG.md。
"""

from __future__ import annotations

import json
import logging
import os

from src.jobs.enable_fields import TASK_JOB_ENABLE_FIELD_MAP
from src.jobs.metadata import MONITOR_JOB_ENABLE_FIELD_MAP, TASK_ENV_MAP

logger = logging.getLogger(__name__)

# 环境变量前缀，青龙用户在「环境变量」中配置时使用此前缀
ENV_PREFIX = "WEBMONITER_"


def is_ql_env() -> bool:
    """
    检测是否在青龙面板环境中运行。

    检测方式：QL_DIR（青龙安装目录）或 WEBMONITER_QL_CRON 环境变量存在。
    """
    return bool(os.environ.get("QL_DIR") or os.environ.get("WEBMONITER_QL_CRON"))


def _env(key: str, default: str = "") -> str:
    """从环境变量读取，支持前缀 WEBMONITER_ 和无前缀两种形式。"""
    v = os.environ.get(f"{ENV_PREFIX}{key}") or os.environ.get(key, default)
    return (v or "").strip()


def load_config_from_env(task_id: str | None = None) -> dict:
    """
    从环境变量构建配置字典（与 load_config_from_yml 返回格式一致）。

    Args:
        task_id: 可选，仅加载指定任务相关配置时传入（如 'ikuuu_checkin'）
                 为 None 时加载所有可从环境变量读取的配置。

    Returns:
        扁平化的配置字典，可直接用于 AppConfig(**config_dict)
    """
    # 青龙单任务模式默认关闭 WebMoniter 内置监控/定时任务，只按目标环境变量显式启用。
    cfg: dict = {
        **{field: False for field in MONITOR_JOB_ENABLE_FIELD_MAP.values()},
        **{field: False for field in TASK_JOB_ENABLE_FIELD_MAP.values()},
        "log_cleanup_enable": True,
        "push_channel_list": [],
        "quiet_hours_enable": False,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "plugins": {},
    }

    # 通用：启用开关与推送均通过环境变量覆盖
    def _apply_task_env(prefix: str, enable_key: str, extra_keys: dict | None = None) -> None:
        enable_val = _env(f"{prefix}_ENABLE", "").lower()
        if enable_val in ("1", "true", "yes", "on"):
            cfg[enable_key] = True
        if extra_keys:
            for env_suffix, config_key in extra_keys.items():
                val = _env(f"{prefix}_{env_suffix}")
                if val:
                    cfg[config_key] = val

    if task_id and task_id in TASK_ENV_MAP:
        prefix, extra = TASK_ENV_MAP[task_id]
        enable_key = TASK_JOB_ENABLE_FIELD_MAP.get(task_id, "")
        if enable_key:
            _apply_task_env(prefix, enable_key, extra)
    else:
        # 加载所有任务的环境变量
        for tid, (prefix, extra) in TASK_ENV_MAP.items():
            enable_key = TASK_JOB_ENABLE_FIELD_MAP.get(tid, "")
            if enable_key:
                _apply_task_env(prefix, enable_key, extra)

    # 多账号/多 Cookie 等：通过 JSON 或竖线分隔
    # CHECKIN_ACCOUNTS: [{"email":"a@b.com","password":"xx"},...] 或 email1|pass1,email2|pass2
    acc = _env("CHECKIN_ACCOUNTS")
    if acc:
        try:
            data = json.loads(acc)
            if isinstance(data, list):
                cfg["checkin_accounts"] = [
                    {
                        "email": str(a.get("email", "")).strip(),
                        "password": str(a.get("password", "")).strip(),
                    }
                    for a in data
                    if isinstance(a, dict)
                ]
        except json.JSONDecodeError:
            # 兼容 email1|pass1,email2|pass2
            accounts = []
            for part in acc.split(","):
                part = part.strip()
                if "|" in part:
                    email, pwd = part.split("|", 1)
                    accounts.append({"email": email.strip(), "password": pwd.strip()})
            if accounts:
                cfg["checkin_accounts"] = accounts

    # Freenom / 天翼云盘 / 科技玩家等多账号 JSON
    for acc_key, config_key in [
        ("FREENOM_ACCOUNTS", "freenom_accounts"),
        ("TYYUN_ACCOUNTS", "tyyun_accounts"),
        ("MIUI_ACCOUNTS", "miui_accounts"),
        ("PINZAN_ACCOUNTS", "pinzan_accounts"),
        ("KJWJ_ACCOUNTS", "kjwj_accounts"),
        ("YDWX_ACCOUNTS", "ydwx_accounts"),
        ("XINGKONG_ACCOUNTS", "xingkong_accounts"),
    ]:
        val = _env(acc_key)
        if val:
            try:
                data = json.loads(val)
                if isinstance(data, list) and data:
                    cfg[config_key] = data
            except json.JSONDecodeError:
                pass

    for cookie_key, config_key in [
        ("TIEBA_COOKIES", "tieba_cookies"),
        ("WEIBO_CHAOHUA_COOKIES", "weibo_chaohua_cookies"),
        ("ENSHAN_COOKIES", "enshan_cookies"),
        ("SMZDM_COOKIES", "smzdm_cookies"),
        ("ZDM_DRAW_COOKIES", "zdm_draw_cookies"),
        ("FG_COOKIES", "fg_cookies"),
        ("IQIYI_COOKIES", "iqiyi_cookies"),
        ("QTW_COOKIES", "qtw_cookies"),
        ("KUAKE_COOKIES", "kuake_cookies"),
        ("FR_COOKIE", "fr_cookie"),
    ]:
        val = _env(cookie_key)
        if val:
            if "|" in val or val.startswith("["):
                try:
                    cfg[config_key] = (
                        json.loads(val)
                        if val.startswith("[")
                        else [v.strip() for v in val.split("|") if v.strip()]
                    )
                except json.JSONDecodeError:
                    cfg[config_key] = [
                        v.strip() for v in val.replace("|", ",").split(",") if v.strip()
                    ]
            else:
                cfg[config_key] = [val]

    # 雨云多账号：RAINYUN_ACCOUNTS 为 JSON 数组，如 [{"username":"u1","password":"p1","api_key":"k1"}]
    try:
        rainyun_acc_json = _env("RAINYUN_ACCOUNTS") or _env("RAINYUN_ACCOUNT")
        if rainyun_acc_json:
            acc_list = (
                json.loads(rainyun_acc_json)
                if isinstance(rainyun_acc_json, str)
                else rainyun_acc_json
            )
            if isinstance(acc_list, dict):
                acc_list = [acc_list]
            if isinstance(acc_list, list) and len(acc_list) > 0:
                accounts = []
                for a in acc_list:
                    if isinstance(a, dict) and a.get("username") and a.get("password"):
                        accounts.append(
                            {
                                "username": str(a.get("username", "")).strip(),
                                "password": str(a.get("password", "")).strip(),
                                "api_key": str(a.get("api_key", "")).strip(),
                            }
                        )
                if accounts:
                    cfg["rainyun_accounts"] = accounts
    except (json.JSONDecodeError, TypeError):
        pass

    # 雨云单账号：RAINYUN_USERNAME + RAINYUN_PASSWORD（青龙环境变量）
    rainyun_user = _env("RAINYUN_USERNAME")
    rainyun_pwd = _env("RAINYUN_PASSWORD")
    if rainyun_user and rainyun_pwd and not cfg.get("rainyun_accounts"):
        cfg["rainyun_accounts"] = [
            {
                "username": rainyun_user,
                "password": rainyun_pwd,
                "api_key": _env("RAINYUN_API_KEY"),
            }
        ]

    for tokens_key, config_key in [
        ("ALIYUN_REFRESH_TOKENS", "aliyun_refresh_tokens"),
        ("LENOVO_ACCESS_TOKENS", "lenovo_access_tokens"),
        ("LBLY_REQUEST_BODIES", "lbly_request_bodies"),
        ("DML_OPENIDS", "dml_openids"),
        ("XIAOMAO_TOKENS", "xiaomao_tokens"),
        ("NINE_NINE_NINE_TOKENS", "nine_nine_nine_tokens"),
        ("ZGFC_TOKENS", "zgfc_tokens"),
    ]:
        val = _env(tokens_key)
        if val:
            cfg[config_key] = [v.strip() for v in val.replace("|", ",").split(",") if v.strip()]

    # 青龙环境下推送优先使用 QLAPI，注入一个虚拟的 qlapi 通道
    if is_ql_env():
        cfg["push_channel_list"] = [{"name": "青龙系统通知", "type": "qlapi"}]

    return cfg


# 当前青龙任务 ID，供 get_config 在 QL 模式下使用
_current_ql_task_id: str | None = None


def inject_ql_config(task_id: str | None = None) -> None:
    """
    设置青龙任务 ID，使 get_config() 从环境变量加载该任务的配置。

    在青龙单任务脚本开头调用，且需在 import 任务模块之前调用。

    Args:
        task_id: 任务 ID，如 'ikuuu_checkin'，仅加载该任务相关配置
    """
    global _current_ql_task_id
    _current_ql_task_id = task_id
    logger.debug("已设置青龙任务 ID (task_id=%s)，get_config 将使用环境变量", task_id)


def get_qlapi():
    """
    获取青龙 QLAPI 对象（如存在）。

    青龙面板在运行脚本时会注入 QLAPI 全局变量，部分版本可能通过 ql 包提供。
    """
    try:
        # 方式1：全局 QLAPI（青龙注入）
        import builtins

        if hasattr(builtins, "QLAPI"):
            return getattr(builtins, "QLAPI")
    except Exception:  # noqa: BLE001
        pass
    try:
        # 方式2：ql 包
        import ql  # type: ignore

        return getattr(ql, "QLAPI", None)
    except ImportError:
        pass
    return None
