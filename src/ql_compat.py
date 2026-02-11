"""
青龙面板兼容模块 - 使 WebMoniter 可在青龙面板中运行

在不改变现有项目逻辑的前提下，提供：
1. 环境变量配置加载（青龙用户通过环境变量配置参数）
2. QLAPI 推送通道（兼容青龙内置通知）

使用方式：在青龙面板中添加定时任务，执行 ql/ 目录下对应的脚本即可。
环境变量命名规范见 docs/QINGLONG.md。
"""

from __future__ import annotations

import json
import logging
import os

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
    # 默认值：与 config.yml.sample 保持一致
    cfg: dict = {
        "weibo_enable": False,
        "huya_enable": False,
        "bilibili_enable": False,
        "douyin_enable": False,
        "douyu_enable": False,
        "xhs_enable": False,
        "checkin_enable": False,
        "tieba_enable": False,
        "weibo_chaohua_enable": False,
        "rainyun_enable": False,
        "enshan_enable": False,
        "tyyun_enable": False,
        "aliyun_enable": False,
        "smzdm_enable": False,
        "zdm_draw_enable": False,
        "fg_enable": False,
        "miui_enable": False,
        "iqiyi_enable": False,
        "lenovo_enable": False,
        "lbly_enable": False,
        "pinzan_enable": False,
        "dml_enable": False,
        "xiaomao_enable": False,
        "ydwx_enable": False,
        "xingkong_enable": False,
        "freenom_enable": False,
        "weather_enable": False,
        "qtw_enable": False,
        "kuake_enable": False,
        "kjwj_enable": False,
        "fr_enable": False,
        "nine_nine_nine_enable": False,
        "zgfc_enable": False,
        "ssq_500w_enable": False,
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

    # 按任务映射环境变量
    task_env_map: dict[str, tuple[str, dict | None]] = {
        "ikuuu_checkin": ("CHECKIN", {"EMAIL": "checkin_email", "PASSWORD": "checkin_password", "TIME": "checkin_time"}),
        "tieba_checkin": ("TIEBA", {"COOKIE": "tieba_cookie", "TIME": "tieba_time"}),
        "weibo_chaohua_checkin": ("WEIBO_CHAOHUA", {"COOKIE": "weibo_chaohua_cookie", "TIME": "weibo_chaohua_time"}),
        "rainyun_checkin": ("RAINYUN", {"API_KEY": "rainyun_api_key", "TIME": "rainyun_time"}),
        "enshan_checkin": ("ENSHAN", {"COOKIE": "enshan_cookie", "TIME": "enshan_time"}),
        "tyyun_checkin": ("TYYUN", {"USERNAME": "tyyun_username", "PASSWORD": "tyyun_password", "TIME": "tyyun_time"}),
        "aliyun_checkin": ("ALIYUN", {"REFRESH_TOKEN": "aliyun_refresh_token", "TIME": "aliyun_time"}),
        "smzdm_checkin": ("SMZDM", {"COOKIE": "smzdm_cookie", "TIME": "smzdm_time"}),
        "zdm_draw": ("ZDM_DRAW", {"COOKIE": "zdm_draw_cookie", "TIME": "zdm_draw_time"}),
        "fg_checkin": ("FG", {"COOKIE": "fg_cookie", "TIME": "fg_time"}),
        "miui_checkin": ("MIUI", {"ACCOUNT": "miui_account", "PASSWORD": "miui_password", "TIME": "miui_time"}),
        "iqiyi_checkin": ("IQIYI", {"COOKIE": "iqiyi_cookie", "TIME": "iqiyi_time"}),
        "lenovo_checkin": ("LENOVO", {"ACCESS_TOKEN": "lenovo_access_token", "TIME": "lenovo_time"}),
        "lbly_checkin": ("LBLY", {"REQUEST_BODY": "lbly_request_body", "TIME": "lbly_time"}),
        "pinzan_checkin": ("PINZAN", {"ACCOUNT": "pinzan_account", "PASSWORD": "pinzan_password", "TIME": "pinzan_time"}),
        "dml_checkin": ("DML", {"OPENID": "dml_openid", "TIME": "dml_time"}),
        "xiaomao_checkin": ("XIAOMAO", {"TOKEN": "xiaomao_token", "MT_VERSION": "xiaomao_mt_version", "TIME": "xiaomao_time"}),
        "ydwx_checkin": ("YDWX", {"DEVICE_PARAMS": "ydwx_device_params", "TOKEN": "ydwx_token", "TIME": "ydwx_time"}),
        "xingkong_checkin": ("XINGKONG", {"USERNAME": "xingkong_username", "PASSWORD": "xingkong_password", "TIME": "xingkong_time"}),
        "freenom_checkin": ("FREENOM", {"TIME": "freenom_time"}),
        "weather_push": ("WEATHER", {"CITY_CODE": "weather_city_code", "TIME": "weather_time"}),
        "qtw_checkin": ("QTW", {"COOKIE": "qtw_cookie", "TIME": "qtw_time"}),
        "kuake_checkin": ("KUAKE", {"COOKIE": "kuake_cookie", "TIME": "kuake_time"}),
        "kjwj_checkin": ("KJWJ", {"TIME": "kjwj_time"}),
        "fr_checkin": ("FR", {"COOKIE": "fr_cookie", "TIME": "fr_time"}),
        "nine_nine_nine_task": ("NINE_NINE_NINE", {"TIME": "nine_nine_nine_time"}),
        "zgfc_draw": ("ZGFC", {"TIME": "zgfc_time"}),
        "ssq_500w_notice": ("SSQ_500W", {"TIME": "ssq_500w_time"}),
    }

    if task_id and task_id in task_env_map:
        prefix, extra = task_env_map[task_id]
        enable_key = {
            "ikuuu_checkin": "checkin_enable",
            "tieba_checkin": "tieba_enable",
            "weibo_chaohua_checkin": "weibo_chaohua_enable",
            "rainyun_checkin": "rainyun_enable",
            "enshan_checkin": "enshan_enable",
            "tyyun_checkin": "tyyun_enable",
            "aliyun_checkin": "aliyun_enable",
            "smzdm_checkin": "smzdm_enable",
            "zdm_draw": "zdm_draw_enable",
            "fg_checkin": "fg_enable",
            "miui_checkin": "miui_enable",
            "iqiyi_checkin": "iqiyi_enable",
            "lenovo_checkin": "lenovo_enable",
            "lbly_checkin": "lbly_enable",
            "pinzan_checkin": "pinzan_enable",
            "dml_checkin": "dml_enable",
            "xiaomao_checkin": "xiaomao_enable",
            "ydwx_checkin": "ydwx_enable",
            "xingkong_checkin": "xingkong_enable",
            "freenom_checkin": "freenom_enable",
            "weather_push": "weather_enable",
            "qtw_checkin": "qtw_enable",
            "kuake_checkin": "kuake_enable",
            "kjwj_checkin": "kjwj_enable",
            "fr_checkin": "fr_enable",
            "nine_nine_nine_task": "nine_nine_nine_enable",
            "zgfc_draw": "zgfc_enable",
            "ssq_500w_notice": "ssq_500w_enable",
        }.get(task_id, "")
        if enable_key:
            _apply_task_env(prefix, enable_key, extra)
    else:
        # 加载所有任务的环境变量
        for tid, (prefix, extra) in task_env_map.items():
            enable_key = {
                "ikuuu_checkin": "checkin_enable",
                "tieba_checkin": "tieba_enable",
                "weibo_chaohua_checkin": "weibo_chaohua_enable",
                "rainyun_checkin": "rainyun_enable",
                "enshan_checkin": "enshan_enable",
                "tyyun_checkin": "tyyun_enable",
                "aliyun_checkin": "aliyun_enable",
                "smzdm_checkin": "smzdm_enable",
                "zdm_draw": "zdm_draw_enable",
                "fg_checkin": "fg_enable",
                "miui_checkin": "miui_enable",
                "iqiyi_checkin": "iqiyi_enable",
                "lenovo_checkin": "lenovo_enable",
                "lbly_checkin": "lbly_enable",
                "pinzan_checkin": "pinzan_enable",
                "dml_checkin": "dml_enable",
                "xiaomao_checkin": "xiaomao_enable",
                "ydwx_checkin": "ydwx_enable",
                "xingkong_checkin": "xingkong_enable",
                "freenom_checkin": "freenom_enable",
                "weather_push": "weather_enable",
                "qtw_checkin": "qtw_enable",
                "kuake_checkin": "kuake_enable",
                "kjwj_checkin": "kjwj_enable",
                "fr_checkin": "fr_enable",
                "nine_nine_nine_task": "nine_nine_nine_enable",
                "zgfc_draw": "zgfc_enable",
                "ssq_500w_notice": "ssq_500w_enable",
            }.get(tid, "")
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
                    {"email": str(a.get("email", "")).strip(), "password": str(a.get("password", "")).strip()}
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
                    cfg[config_key] = json.loads(val) if val.startswith("[") else [v.strip() for v in val.split("|") if v.strip()]
                except json.JSONDecodeError:
                    cfg[config_key] = [v.strip() for v in val.replace("|", ",").split(",") if v.strip()]
            else:
                cfg[config_key] = [val]

    for tokens_key, config_key in [
        ("RAINYUN_API_KEYS", "rainyun_api_keys"),
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
