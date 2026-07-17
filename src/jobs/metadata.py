"""任务与推送通道元数据。

本模块是注册表、enable 映射、青龙环境变量和 Web 配置页的轻量单一真相源。
它只描述现有接口，不改变任何任务、配置或推送通道的行为。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

JobKind = Literal["monitor", "task"]


@dataclass(frozen=True)
class TaskSpec:
    job_id: str
    module: str
    description: str
    kind: JobKind
    config_section: str
    enable_field: str | None = None
    time_field: str | None = None
    default_time: str | None = None
    interval_field: str | None = None
    push_field: str | None = None
    ql_prefix: str | None = None
    ql_extra_env: dict[str, str] = field(default_factory=dict)
    plugin_only: bool = False

    @property
    def push_container_id(self) -> str | None:
        if self.push_field is None:
            return None
        return self.push_field


@dataclass(frozen=True)
class PushChannelSpec:
    type: str
    name: str
    fields: tuple[str, ...]


MONITOR_SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        "huya_monitor",
        "src.monitors.huya_monitor",
        "虎牙直播监控",
        "monitor",
        "huya",
        enable_field="huya_enable",
        interval_field="huya_monitor_interval_seconds",
        push_field="huya_push_channels",
    ),
    TaskSpec(
        "weibo_monitor",
        "src.monitors.weibo_monitor",
        "微博监控",
        "monitor",
        "weibo",
        enable_field="weibo_enable",
        interval_field="weibo_monitor_interval_seconds",
        push_field="weibo_push_channels",
    ),
    TaskSpec(
        "bilibili_monitor",
        "src.monitors.bilibili_monitor",
        "哔哩哔哩监控",
        "monitor",
        "bilibili",
        enable_field="bilibili_enable",
        interval_field="bilibili_monitor_interval_seconds",
        push_field="bilibili_push_channels",
    ),
    TaskSpec(
        "douyin_monitor",
        "src.monitors.douyin_monitor",
        "抖音直播监控",
        "monitor",
        "douyin",
        enable_field="douyin_enable",
        interval_field="douyin_monitor_interval_seconds",
        push_field="douyin_push_channels",
    ),
    TaskSpec(
        "douyu_monitor",
        "src.monitors.douyu_monitor",
        "斗鱼直播监控",
        "monitor",
        "douyu",
        enable_field="douyu_enable",
        interval_field="douyu_monitor_interval_seconds",
        push_field="douyu_push_channels",
    ),
    TaskSpec(
        "xhs_monitor",
        "src.monitors.xhs_monitor",
        "小红书动态监控",
        "monitor",
        "xhs",
        enable_field="xhs_enable",
        interval_field="xhs_monitor_interval_seconds",
        push_field="xhs_push_channels",
    ),
)


TASK_SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        "weibo_cookie_refresh",
        "src.tasks.weibo_cookie_refresh",
        "微博 Cookie 自动刷新",
        "task",
        "weibo",
        enable_field="weibo_cookie_refresh_enable",
        time_field="weibo_cookie_refresh_time",
        default_time="21:00",
    ),
    TaskSpec(
        "log_cleanup",
        "src.tasks.log_cleanup",
        "日志清理",
        "task",
        "log_cleanup",
        enable_field="log_cleanup_enable",
        time_field="log_cleanup_time",
        default_time="02:10",
        ql_prefix="LOG_CLEANUP",
        ql_extra_env={"TIME": "log_cleanup_time"},
    ),
    TaskSpec(
        "ikuuu_checkin",
        "src.tasks.ikuuu_checkin",
        "iKuuu 签到",
        "task",
        "checkin",
        enable_field="checkin_enable",
        time_field="checkin_time",
        default_time="08:00",
        push_field="checkin_push_channels",
        ql_prefix="CHECKIN",
        ql_extra_env={
            "EMAIL": "checkin_email",
            "PASSWORD": "checkin_password",
            "TIME": "checkin_time",
        },
    ),
    TaskSpec(
        "tieba_checkin",
        "src.tasks.tieba_checkin",
        "百度贴吧签到",
        "task",
        "tieba",
        enable_field="tieba_enable",
        time_field="tieba_time",
        default_time="08:10",
        push_field="tieba_push_channels",
        ql_prefix="TIEBA",
        ql_extra_env={"COOKIE": "tieba_cookie", "TIME": "tieba_time"},
    ),
    TaskSpec(
        "weibo_chaohua_checkin",
        "src.tasks.weibo_chaohua_checkin",
        "微博超话签到",
        "task",
        "weibo_chaohua",
        enable_field="weibo_chaohua_enable",
        time_field="weibo_chaohua_time",
        default_time="23:45",
        push_field="weibo_chaohua_push_channels",
        ql_prefix="WEIBO_CHAOHUA",
        ql_extra_env={"COOKIE": "weibo_chaohua_cookie", "TIME": "weibo_chaohua_time"},
    ),
    TaskSpec(
        "rainyun_checkin",
        "src.tasks.rainyun_checkin",
        "雨云签到",
        "task",
        "rainyun",
        enable_field="rainyun_enable",
        time_field="rainyun_time",
        default_time="08:30",
        push_field="rainyun_push_channels",
        ql_prefix="RAINYUN",
        ql_extra_env={"TIME": "rainyun_time"},
    ),
    TaskSpec(
        "enshan_checkin",
        "src.tasks.enshan_checkin",
        "恩山论坛签到",
        "task",
        "enshan",
        enable_field="enshan_enable",
        time_field="enshan_time",
        default_time="02:00",
        push_field="enshan_push_channels",
        ql_prefix="ENSHAN",
        ql_extra_env={"COOKIE": "enshan_cookie", "TIME": "enshan_time"},
    ),
    TaskSpec(
        "fg_checkin",
        "src.tasks.fg_checkin",
        "富贵论坛签到",
        "task",
        "fg",
        enable_field="fg_enable",
        time_field="fg_time",
        default_time="00:01",
        push_field="fg_push_channels",
        ql_prefix="FG",
        ql_extra_env={"COOKIE": "fg_cookie", "TIME": "fg_time"},
    ),
    TaskSpec(
        "aliyun_checkin",
        "src.tasks.aliyun_checkin",
        "阿里云盘签到",
        "task",
        "aliyun",
        enable_field="aliyun_enable",
        time_field="aliyun_time",
        default_time="05:30",
        push_field="aliyun_push_channels",
        ql_prefix="ALIYUN",
        ql_extra_env={"REFRESH_TOKEN": "aliyun_refresh_token", "TIME": "aliyun_time"},
    ),
    TaskSpec(
        "smzdm_checkin",
        "src.tasks.smzdm_checkin",
        "什么值得买签到",
        "task",
        "smzdm",
        enable_field="smzdm_enable",
        time_field="smzdm_time",
        default_time="00:30",
        push_field="smzdm_push_channels",
        ql_prefix="SMZDM",
        ql_extra_env={"COOKIE": "smzdm_cookie", "TIME": "smzdm_time"},
    ),
    TaskSpec(
        "zdm_draw",
        "src.tasks.zdm_draw",
        "值得买每日抽奖",
        "task",
        "zdm_draw",
        enable_field="zdm_draw_enable",
        time_field="zdm_draw_time",
        default_time="07:30",
        push_field="zdm_draw_push_channels",
        ql_prefix="ZDM_DRAW",
        ql_extra_env={"COOKIE": "zdm_draw_cookie", "TIME": "zdm_draw_time"},
    ),
    TaskSpec(
        "tyyun_checkin",
        "src.tasks.tyyun_checkin",
        "天翼云盘签到",
        "task",
        "tyyun",
        enable_field="tyyun_enable",
        time_field="tyyun_time",
        default_time="04:30",
        push_field="tyyun_push_channels",
        ql_prefix="TYYUN",
        ql_extra_env={
            "USERNAME": "tyyun_username",
            "PASSWORD": "tyyun_password",
            "TIME": "tyyun_time",
        },
    ),
    TaskSpec(
        "miui_checkin",
        "src.tasks.miui_checkin",
        "小米社区签到",
        "task",
        "miui",
        enable_field="miui_enable",
        time_field="miui_time",
        default_time="08:30",
        push_field="miui_push_channels",
        ql_prefix="MIUI",
        ql_extra_env={"ACCOUNT": "miui_account", "PASSWORD": "miui_password", "TIME": "miui_time"},
    ),
    TaskSpec(
        "iqiyi_checkin",
        "src.tasks.iqiyi_checkin",
        "爱奇艺签到",
        "task",
        "iqiyi",
        enable_field="iqiyi_enable",
        time_field="iqiyi_time",
        default_time="06:00",
        push_field="iqiyi_push_channels",
        ql_prefix="IQIYI",
        ql_extra_env={"COOKIE": "iqiyi_cookie", "TIME": "iqiyi_time"},
    ),
    TaskSpec(
        "lenovo_checkin",
        "src.tasks.lenovo_checkin",
        "联想乐豆签到",
        "task",
        "lenovo",
        enable_field="lenovo_enable",
        time_field="lenovo_time",
        default_time="05:30",
        push_field="lenovo_push_channels",
        ql_prefix="LENOVO",
        ql_extra_env={"ACCESS_TOKEN": "lenovo_access_token", "TIME": "lenovo_time"},
    ),
    TaskSpec(
        "lbly_checkin",
        "src.tasks.lbly_checkin",
        "丽宝乐园签到",
        "task",
        "lbly",
        enable_field="lbly_enable",
        time_field="lbly_time",
        default_time="05:30",
        push_field="lbly_push_channels",
        ql_prefix="LBLY",
        ql_extra_env={"REQUEST_BODY": "lbly_request_body", "TIME": "lbly_time"},
    ),
    TaskSpec(
        "pinzan_checkin",
        "src.tasks.pinzan_checkin",
        "品赞代理签到",
        "task",
        "pinzan",
        enable_field="pinzan_enable",
        time_field="pinzan_time",
        default_time="08:00",
        push_field="pinzan_push_channels",
        ql_prefix="PINZAN",
        ql_extra_env={
            "ACCOUNT": "pinzan_account",
            "PASSWORD": "pinzan_password",
            "TIME": "pinzan_time",
        },
    ),
    TaskSpec(
        "dml_checkin",
        "src.tasks.dml_checkin",
        "达美乐任务",
        "task",
        "dml",
        enable_field="dml_enable",
        time_field="dml_time",
        default_time="06:00",
        push_field="dml_push_channels",
        ql_prefix="DML",
        ql_extra_env={"OPENID": "dml_openid", "TIME": "dml_time"},
    ),
    TaskSpec(
        "xiaomao_checkin",
        "src.tasks.xiaomao_checkin",
        "小茅预约",
        "task",
        "xiaomao",
        enable_field="xiaomao_enable",
        time_field="xiaomao_time",
        default_time="09:00",
        push_field="xiaomao_push_channels",
        ql_prefix="XIAOMAO",
        ql_extra_env={
            "TOKEN": "xiaomao_token",
            "MT_VERSION": "xiaomao_mt_version",
            "TIME": "xiaomao_time",
        },
    ),
    TaskSpec(
        "ydwx_checkin",
        "src.tasks.ydwx_checkin",
        "一点万象签到",
        "task",
        "ydwx",
        enable_field="ydwx_enable",
        time_field="ydwx_time",
        default_time="06:00",
        push_field="ydwx_push_channels",
        ql_prefix="YDWX",
        ql_extra_env={
            "DEVICE_PARAMS": "ydwx_device_params",
            "TOKEN": "ydwx_token",
            "TIME": "ydwx_time",
        },
    ),
    TaskSpec(
        "xingkong_checkin",
        "src.tasks.xingkong_checkin",
        "星空代理签到",
        "task",
        "xingkong",
        enable_field="xingkong_enable",
        time_field="xingkong_time",
        default_time="07:30",
        push_field="xingkong_push_channels",
        ql_prefix="XINGKONG",
        ql_extra_env={
            "USERNAME": "xingkong_username",
            "PASSWORD": "xingkong_password",
            "TIME": "xingkong_time",
        },
    ),
    TaskSpec(
        "freenom_checkin",
        "src.tasks.freenom_checkin",
        "Freenom 免费域名续期",
        "task",
        "freenom",
        enable_field="freenom_enable",
        time_field="freenom_time",
        default_time="07:33",
        push_field="freenom_push_channels",
        ql_prefix="FREENOM",
        ql_extra_env={"TIME": "freenom_time"},
    ),
    TaskSpec(
        "weather_push",
        "src.tasks.weather_push",
        "天气每日推送",
        "task",
        "weather",
        enable_field="weather_enable",
        time_field="weather_time",
        default_time="07:30",
        push_field="weather_push_channels",
        ql_prefix="WEATHER",
        ql_extra_env={"CITY_CODE": "weather_city_code", "TIME": "weather_time"},
    ),
    TaskSpec(
        "qtw_checkin",
        "src.tasks.qtw_checkin",
        "千图网签到",
        "task",
        "qtw",
        enable_field="qtw_enable",
        time_field="qtw_time",
        default_time="01:30",
        push_field="qtw_push_channels",
        ql_prefix="QTW",
        ql_extra_env={"COOKIE": "qtw_cookie", "TIME": "qtw_time"},
    ),
    TaskSpec(
        "kuake_checkin",
        "src.tasks.kuake_checkin",
        "夸克网盘签到",
        "task",
        "kuake",
        enable_field="kuake_enable",
        time_field="kuake_time",
        default_time="02:00",
        push_field="kuake_push_channels",
        ql_prefix="KUAKE",
        ql_extra_env={"COOKIE": "kuake_cookie", "TIME": "kuake_time"},
    ),
    TaskSpec(
        "kjwj_checkin",
        "src.tasks.kjwj_checkin",
        "科技玩家签到",
        "task",
        "kjwj",
        enable_field="kjwj_enable",
        time_field="kjwj_time",
        default_time="07:30",
        push_field="kjwj_push_channels",
        ql_prefix="KJWJ",
        ql_extra_env={"TIME": "kjwj_time"},
    ),
    TaskSpec(
        "fr_checkin",
        "src.tasks.fr_checkin",
        "帆软社区签到",
        "task",
        "fr",
        enable_field="fr_enable",
        time_field="fr_time",
        default_time="06:30",
        push_field="fr_push_channels",
        ql_prefix="FR",
        ql_extra_env={"COOKIE": "fr_cookie", "TIME": "fr_time"},
    ),
    TaskSpec(
        "nine_nine_nine_task",
        "src.tasks.nine_nine_nine_task",
        "999 会员中心健康打卡",
        "task",
        "nine_nine_nine",
        enable_field="nine_nine_nine_enable",
        time_field="nine_nine_nine_time",
        default_time="15:15",
        push_field="nine_nine_nine_push_channels",
        ql_prefix="NINE_NINE_NINE",
        ql_extra_env={"TIME": "nine_nine_nine_time"},
    ),
    TaskSpec(
        "zgfc_draw",
        "src.tasks.zgfc_draw",
        "中国福彩抽奖活动",
        "task",
        "zgfc",
        enable_field="zgfc_enable",
        time_field="zgfc_time",
        default_time="08:00",
        push_field="zgfc_push_channels",
        ql_prefix="ZGFC",
        ql_extra_env={"TIME": "zgfc_time"},
    ),
    TaskSpec(
        "ssq_500w_notice",
        "src.tasks.ssq_500w_notice",
        "双色球开奖通知",
        "task",
        "ssq_500w",
        enable_field="ssq_500w_enable",
        time_field="ssq_500w_time",
        default_time="21:30",
        push_field="ssq_500w_push_channels",
        ql_prefix="SSQ_500W",
        ql_extra_env={"TIME": "ssq_500w_time"},
    ),
    TaskSpec(
        "demo_task",
        "src.tasks.demo_task",
        "二次开发示例任务",
        "task",
        "plugins",
        time_field="plugins.demo_task.time",
        default_time="08:00",
        ql_prefix="DEMO_TASK",
        plugin_only=True,
    ),
)


PUSH_CHANNEL_SPECS: tuple[PushChannelSpec, ...] = (
    PushChannelSpec("serverChan_turbo", "Server酱 Turbo", ("send_key",)),
    PushChannelSpec("serverChan_3", "Server酱 3", ("send_key", "uid", "tags")),
    PushChannelSpec("wecom_apps", "企业微信应用", ("corp_id", "agent_id", "corp_secret", "touser")),
    PushChannelSpec("wecom_bot", "企业微信机器人", ("key",)),
    PushChannelSpec("dingtalk_bot", "钉钉机器人", ("access_token", "secret")),
    PushChannelSpec(
        "feishu_apps", "飞书自建应用", ("app_id", "app_secret", "receive_id_type", "receive_id")
    ),
    PushChannelSpec("feishu_bot", "飞书机器人", ("webhook_key", "sign_secret")),
    PushChannelSpec("telegram_bot", "Telegram机器人", ("api_token", "chat_id")),
    PushChannelSpec("qq_bot", "QQ机器人", ("base_url", "app_id", "app_secret", "push_target_list")),
    PushChannelSpec("napcat_qq", "NapCatQQ", ("api_url", "token", "user_id", "group_id", "at_qq")),
    PushChannelSpec("bark", "Bark", ("server_url", "key")),
    PushChannelSpec("gotify", "Gotify", ("web_server_url",)),
    PushChannelSpec("webhook", "Webhook", ("webhook_url", "request_method")),
    PushChannelSpec("pushplus", "PushPlus", ("token", "channel", "topic", "template", "to")),
    PushChannelSpec(
        "email",
        "Email",
        (
            "smtp_host",
            "smtp_port",
            "smtp_ssl",
            "smtp_tls",
            "sender_email",
            "sender_password",
            "receiver_email",
        ),
    ),
    PushChannelSpec("wxpusher", "WxPusher", ("app_token", "uids", "topic_ids", "content_type")),
    PushChannelSpec("demo", "Demo", ()),
    PushChannelSpec("qlapi", "青龙 QLAPI", ()),
)


CONFIG_SECTION_ORDER: tuple[str, ...] = (
    "weibo",
    "weibo_chaohua",
    "huya",
    "bilibili",
    "douyin",
    "douyu",
    "xhs",
    "checkin",
    "rainyun",
    "tieba",
    "enshan",
    "tyyun",
    "aliyun",
    "smzdm",
    "zdm_draw",
    "fg",
    "miui",
    "iqiyi",
    "lenovo",
    "lbly",
    "pinzan",
    "dml",
    "xiaomao",
    "ydwx",
    "xingkong",
    "qtw",
    "freenom",
    "weather",
    "kuake",
    "kjwj",
    "fr",
    "nine_nine_nine",
    "zgfc",
    "ssq_500w",
    "log_cleanup",
    "app",
    "quiet_hours",
    "push_channel",
    "plugins",
)

MONITOR_MODULES: list[str] = [spec.module for spec in MONITOR_SPECS]
TASK_MODULES: list[str] = [spec.module for spec in TASK_SPECS]
MONITOR_JOB_ENABLE_FIELD_MAP: dict[str, str] = {
    spec.job_id: spec.enable_field for spec in MONITOR_SPECS if spec.enable_field
}
TASK_JOB_ENABLE_FIELD_MAP: dict[str, str] = {
    spec.job_id: spec.enable_field
    for spec in TASK_SPECS
    if spec.enable_field and not spec.plugin_only
}
TASK_ENV_MAP: dict[str, tuple[str, dict[str, str]]] = {
    spec.job_id: (spec.ql_prefix, dict(spec.ql_extra_env)) for spec in TASK_SPECS if spec.ql_prefix
}


def get_task_spec(job_id: str) -> TaskSpec | None:
    for spec in MONITOR_SPECS + TASK_SPECS:
        if spec.job_id == job_id:
            return spec
    return None
