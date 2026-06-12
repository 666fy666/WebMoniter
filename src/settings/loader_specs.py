"""YAML 配置加载规格。

本模块只保存“配置文件字段如何映射到 AppConfig”的静态规格，
让 src.settings.config 专注于配置模型、加载流程和校验。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MultiAccountSpec:
    section_key: str
    fields: tuple[str, ...]
    config_key: str


@dataclass(frozen=True)
class MultiStringSpec:
    section_key: str
    yaml_key: str
    config_key: str


CONFIG_MAPPINGS: dict[str, dict[str, str]] = {
    "app": {
        "base_url": "base_url",
    },
    "weibo": {
        "enable": "weibo_enable",
        "cookie": "weibo_cookie",
        "uids": "weibo_uids",
        "concurrency": "weibo_concurrency",
        "monitor_interval_seconds": "weibo_monitor_interval_seconds",
        "push_channels": "weibo_push_channels",
    },
    "huya": {
        "enable": "huya_enable",
        "rooms": "huya_rooms",
        "concurrency": "huya_concurrency",
        "monitor_interval_seconds": "huya_monitor_interval_seconds",
        "push_channels": "huya_push_channels",
    },
    "bilibili": {
        "enable": "bilibili_enable",
        "cookie": "bilibili_cookie",
        "payload": "bilibili_payload",
        "uids": "bilibili_uids",
        "skip_forward": "bilibili_skip_forward",
        "concurrency": "bilibili_concurrency",
        "monitor_interval_seconds": "bilibili_monitor_interval_seconds",
        "push_channels": "bilibili_push_channels",
    },
    "douyin": {
        "enable": "douyin_enable",
        "douyin_ids": "douyin_douyin_ids",
        "concurrency": "douyin_concurrency",
        "monitor_interval_seconds": "douyin_monitor_interval_seconds",
        "push_channels": "douyin_push_channels",
    },
    "douyu": {
        "enable": "douyu_enable",
        "rooms": "douyu_rooms",
        "concurrency": "douyu_concurrency",
        "monitor_interval_seconds": "douyu_monitor_interval_seconds",
        "push_channels": "douyu_push_channels",
    },
    "xhs": {
        "enable": "xhs_enable",
        "cookie": "xhs_cookie",
        "profile_ids": "xhs_profile_ids",
        "concurrency": "xhs_concurrency",
        "monitor_interval_seconds": "xhs_monitor_interval_seconds",
        "push_channels": "xhs_push_channels",
    },
    "checkin": {
        "enable": "checkin_enable",
        "email": "checkin_email",
        "password": "checkin_password",
        "time": "checkin_time",
        "push_channels": "checkin_push_channels",
    },
    "tieba": {
        "enable": "tieba_enable",
        "cookie": "tieba_cookie",
        "time": "tieba_time",
        "push_channels": "tieba_push_channels",
    },
    "weibo_chaohua": {
        "enable": "weibo_chaohua_enable",
        "cookie": "weibo_chaohua_cookie",
        "time": "weibo_chaohua_time",
        "push_channels": "weibo_chaohua_push_channels",
    },
    "rainyun": {
        "enable": "rainyun_enable",
        "time": "rainyun_time",
        "push_channels": "rainyun_push_channels",
    },
    "enshan": {
        "enable": "enshan_enable",
        "cookie": "enshan_cookie",
        "time": "enshan_time",
        "push_channels": "enshan_push_channels",
    },
    "tyyun": {
        "enable": "tyyun_enable",
        "username": "tyyun_username",
        "password": "tyyun_password",
        "time": "tyyun_time",
        "push_channels": "tyyun_push_channels",
    },
    "aliyun": {
        "enable": "aliyun_enable",
        "refresh_token": "aliyun_refresh_token",
        "time": "aliyun_time",
        "push_channels": "aliyun_push_channels",
    },
    "smzdm": {
        "enable": "smzdm_enable",
        "cookie": "smzdm_cookie",
        "time": "smzdm_time",
        "push_channels": "smzdm_push_channels",
    },
    "zdm_draw": {
        "enable": "zdm_draw_enable",
        "cookie": "zdm_draw_cookie",
        "time": "zdm_draw_time",
        "push_channels": "zdm_draw_push_channels",
    },
    "fg": {
        "enable": "fg_enable",
        "cookie": "fg_cookie",
        "time": "fg_time",
        "push_channels": "fg_push_channels",
    },
    "miui": {
        "enable": "miui_enable",
        "account": "miui_account",
        "password": "miui_password",
        "time": "miui_time",
        "push_channels": "miui_push_channels",
    },
    "iqiyi": {
        "enable": "iqiyi_enable",
        "cookie": "iqiyi_cookie",
        "time": "iqiyi_time",
        "push_channels": "iqiyi_push_channels",
    },
    "lenovo": {
        "enable": "lenovo_enable",
        "access_token": "lenovo_access_token",
        "time": "lenovo_time",
        "push_channels": "lenovo_push_channels",
    },
    "lbly": {
        "enable": "lbly_enable",
        "request_body": "lbly_request_body",
        "time": "lbly_time",
        "push_channels": "lbly_push_channels",
    },
    "pinzan": {
        "enable": "pinzan_enable",
        "account": "pinzan_account",
        "password": "pinzan_password",
        "time": "pinzan_time",
        "push_channels": "pinzan_push_channels",
    },
    "dml": {
        "enable": "dml_enable",
        "openid": "dml_openid",
        "time": "dml_time",
        "push_channels": "dml_push_channels",
    },
    "xiaomao": {
        "enable": "xiaomao_enable",
        "token": "xiaomao_token",
        "mt_version": "xiaomao_mt_version",
        "time": "xiaomao_time",
        "push_channels": "xiaomao_push_channels",
    },
    "ydwx": {
        "enable": "ydwx_enable",
        "device_params": "ydwx_device_params",
        "token": "ydwx_token",
        "time": "ydwx_time",
        "push_channels": "ydwx_push_channels",
    },
    "xingkong": {
        "enable": "xingkong_enable",
        "username": "xingkong_username",
        "password": "xingkong_password",
        "time": "xingkong_time",
        "push_channels": "xingkong_push_channels",
    },
    "freenom": {
        "enable": "freenom_enable",
        "time": "freenom_time",
        "push_channels": "freenom_push_channels",
    },
    "weather": {
        "enable": "weather_enable",
        "city_code": "weather_city_code",
        "time": "weather_time",
        "push_channels": "weather_push_channels",
    },
    "qtw": {
        "enable": "qtw_enable",
        "cookie": "qtw_cookie",
        "time": "qtw_time",
        "push_channels": "qtw_push_channels",
    },
    "kuake": {
        "enable": "kuake_enable",
        "cookie": "kuake_cookie",
        "time": "kuake_time",
        "push_channels": "kuake_push_channels",
    },
    "kjwj": {
        "enable": "kjwj_enable",
        "time": "kjwj_time",
        "push_channels": "kjwj_push_channels",
    },
    "fr": {
        "enable": "fr_enable",
        "cookie": "fr_cookie",
        "time": "fr_time",
        "push_channels": "fr_push_channels",
    },
    "nine_nine_nine": {
        "enable": "nine_nine_nine_enable",
        "time": "nine_nine_nine_time",
        "push_channels": "nine_nine_nine_push_channels",
    },
    "zgfc": {
        "enable": "zgfc_enable",
        "time": "zgfc_time",
        "push_channels": "zgfc_push_channels",
    },
    "ssq_500w": {
        "enable": "ssq_500w_enable",
        "time": "ssq_500w_time",
        "push_channels": "ssq_500w_push_channels",
    },
    "log_cleanup": {
        "enable": "log_cleanup_enable",
        "time": "log_cleanup_time",
        "retention_days": "retention_days",
    },
    "quiet_hours": {
        "enable": "quiet_hours_enable",
        "start": "quiet_hours_start",
        "end": "quiet_hours_end",
    },
}

# YAML 中这类字段如果写成 `field:` 会解析为 None，加载时按空字符串处理。
STRING_FIELDS = frozenset(
    {
        "cookie",
        "api_key",
        "uids",
        "rooms",
        "douyin_ids",
        "profile_ids",
        "payload",
        "email",
        "password",
        "time",
        "start",
        "end",
        "username",
        "refresh_token",
        "token",
        "mt_version",
        "device_params",
        "account",
        "access_token",
        "request_body",
        "openid",
    }
)

MULTI_ACCOUNT_SPECS: tuple[MultiAccountSpec, ...] = (
    MultiAccountSpec("checkin", ("email", "password"), "checkin_accounts"),
    MultiAccountSpec("rainyun", ("username", "password", "api_key"), "rainyun_accounts"),
    MultiAccountSpec("tyyun", ("username", "password"), "tyyun_accounts"),
    MultiAccountSpec("miui", ("account", "password"), "miui_accounts"),
    MultiAccountSpec("pinzan", ("account", "password"), "pinzan_accounts"),
    MultiAccountSpec("ydwx", ("device_params", "token"), "ydwx_accounts"),
    MultiAccountSpec("xingkong", ("username", "password"), "xingkong_accounts"),
    MultiAccountSpec("kjwj", ("username", "password"), "kjwj_accounts"),
    MultiAccountSpec("freenom", ("email", "password"), "freenom_accounts"),
)

MULTI_STRING_SPECS: tuple[MultiStringSpec, ...] = (
    MultiStringSpec("tieba", "cookies", "tieba_cookies"),
    MultiStringSpec("weibo_chaohua", "cookies", "weibo_chaohua_cookies"),
    MultiStringSpec("enshan", "cookies", "enshan_cookies"),
    MultiStringSpec("smzdm", "cookies", "smzdm_cookies"),
    MultiStringSpec("zdm_draw", "cookies", "zdm_draw_cookies"),
    MultiStringSpec("fg", "cookies", "fg_cookies"),
    MultiStringSpec("iqiyi", "cookies", "iqiyi_cookies"),
    MultiStringSpec("qtw", "cookies", "qtw_cookies"),
    MultiStringSpec("kuake", "cookies", "kuake_cookies"),
    MultiStringSpec("aliyun", "refresh_tokens", "aliyun_refresh_tokens"),
    MultiStringSpec("lenovo", "access_tokens", "lenovo_access_tokens"),
    MultiStringSpec("lbly", "request_bodies", "lbly_request_bodies"),
    MultiStringSpec("dml", "openids", "dml_openids"),
    MultiStringSpec("xiaomao", "tokens", "xiaomao_tokens"),
    MultiStringSpec("nine_nine_nine", "tokens", "nine_nine_nine_tokens"),
    MultiStringSpec("zgfc", "tokens", "zgfc_tokens"),
)
