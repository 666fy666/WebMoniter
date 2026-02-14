"""配置管理模块 - 从YAML配置文件读取配置"""

import logging
from datetime import datetime, time
from pathlib import Path

import yaml
from pydantic import BaseModel

# 获取logger
logger = logging.getLogger(__name__)


class WeiboConfig(BaseModel):
    """微博配置"""

    cookie: str
    uids: list[str]
    concurrency: int = 3  # 并发数，默认3，建议2-5


class HuyaConfig(BaseModel):
    """虎牙配置"""

    rooms: list[str]
    concurrency: int = 7  # 并发数，默认7，建议5-10


class BilibiliConfig(BaseModel):
    """哔哩哔哩配置"""

    cookie: str = ""
    payload: str = ""
    uids: list[str]
    skip_forward: bool = True
    concurrency: int = 2


class DouyinConfig(BaseModel):
    """抖音配置"""

    douyin_ids: list[str]
    concurrency: int = 2


class DouyuConfig(BaseModel):
    """斗鱼配置"""

    rooms: list[str]
    concurrency: int = 2


class XhsConfig(BaseModel):
    """小红书配置"""

    cookie: str = ""
    profile_ids: list[str]
    concurrency: int = 2


class AppConfig(BaseModel):
    """应用配置"""

    # 基础访问地址，用于构造对外可访问的 HTTP 链接（例如微博封面图 URL）
    base_url: str = ""

    # 微博
    weibo_enable: bool = True  # 是否启用微博监控
    weibo_cookie: str = ""
    weibo_uids: str = ""  # 逗号分隔的UID列表
    weibo_concurrency: int = 3  # 微博监控并发数，建议2-5（避免触发限流）
    weibo_push_channels: list[str] = []  # 推送通道名称列表，为空时使用全部通道
    weibo_compress_with_llm: bool = False  # 推送超限时是否用 LLM 压缩（需配置 ai_assistant）

    # 虎牙
    huya_enable: bool = True  # 是否启用虎牙监控
    huya_rooms: str = ""  # 逗号分隔的房间号列表
    huya_concurrency: int = 7  # 虎牙监控并发数，建议5-10（相对宽松）
    huya_push_channels: list[str] = []  # 推送通道名称列表，为空时使用全部通道

    # 哔哩哔哩
    bilibili_enable: bool = True  # 是否启用哔哩哔哩监控
    bilibili_cookie: str = ""
    bilibili_payload: str = ""
    bilibili_uids: str = ""
    bilibili_skip_forward: bool = True
    bilibili_concurrency: int = 2
    bilibili_push_channels: list[str] = []

    # 抖音
    douyin_enable: bool = True  # 是否启用抖音直播监控
    douyin_douyin_ids: str = ""
    douyin_concurrency: int = 2
    douyin_push_channels: list[str] = []

    # 斗鱼
    douyu_enable: bool = True  # 是否启用斗鱼直播监控
    douyu_rooms: str = ""
    douyu_concurrency: int = 2
    douyu_push_channels: list[str] = []

    # 小红书
    xhs_enable: bool = True  # 是否启用小红书动态监控
    xhs_cookie: str = ""
    xhs_profile_ids: str = ""
    xhs_concurrency: int = 2
    xhs_push_channels: list[str] = []

    # 每日签到配置（域名自动从 ikuuu.club 发现，无需手动配置 URL）
    checkin_enable: bool = False  # 是否启用每日签到
    checkin_email: str = ""  # 单账号：登录账号（与 checkin_password 搭配）
    checkin_password: str = ""  # 单账号：登录密码
    checkin_accounts: list[dict] = (
        []
    )  # 多账号：[{"email": str, "password": str}, ...]，非空时优先于单账号
    checkin_time: str = "08:00"  # 签到时间（默认每天早上 8 点，格式：HH:MM）
    checkin_push_channels: list[str] = []  # 推送通道名称列表，为空时使用全部通道

    # 百度贴吧签到配置（使用 Cookie）
    tieba_enable: bool = False  # 是否启用贴吧签到
    tieba_cookie: str = ""  # 单 Cookie（与 tieba_cookies 二选一，须包含 BDUSS）
    tieba_cookies: list[str] = []  # 多 Cookie 列表，非空时优先于 tieba_cookie
    tieba_time: str = "08:10"  # 贴吧签到时间（格式：HH:MM），默认 08:10
    tieba_push_channels: list[str] = []  # 推送通道名称列表，为空时使用全部通道

    # 微博超话签到配置（使用 Cookie）
    weibo_chaohua_enable: bool = False  # 是否启用微博超话签到
    weibo_chaohua_cookie: str = (
        ""  # 单 Cookie（与 weibo_chaohua_cookies 二选一，须包含 XSRF-TOKEN）
    )
    weibo_chaohua_cookies: list[str] = []  # 多 Cookie 列表，非空时优先于 weibo_chaohua_cookie
    weibo_chaohua_time: str = "23:45"  # 微博超话签到时间（格式：HH:MM），默认 23:45
    weibo_chaohua_push_channels: list[str] = []  # 推送通道名称列表，为空时使用全部通道

    # 雨云签到配置（参考 Rainyun-Qiandao：Selenium + 账号密码 + ddddocr）
    rainyun_enable: bool = False  # 是否启用雨云签到
    rainyun_accounts: list[dict] = []  # [{"username": str, "password": str, "api_key": str?}, ...]
    rainyun_time: str = "08:30"  # 雨云签到时间（格式：HH:MM），默认 08:30
    rainyun_push_channels: list[str] = []  # 推送通道名称列表，为空时使用全部通道
    # 雨云自动续费配置（参考 Jielumoon/Rainyun-Qiandao）
    rainyun_auto_renew: bool = True  # 是否启用服务器到期自动续费
    rainyun_renew_threshold_days: int = 7  # 剩余多少天内触发续费，默认 7 天
    rainyun_renew_product_ids: list[int] = (
        []
    )  # 续费白名单（产品 ID 列表），为空则续费所有即将到期的服务器
    rainyun_chrome_bin: str = ""  # Chrome/Chromium 可执行路径，Docker 下通常用环境变量 CHROME_BIN
    rainyun_chromedriver_path: str = (
        ""  # chromedriver 路径，Docker 下通常用环境变量 CHROMEDRIVER_PATH
    )

    # 恩山论坛签到配置（Cookie）
    enshan_enable: bool = False
    enshan_cookie: str = ""
    enshan_cookies: list[str] = []
    enshan_time: str = "02:00"
    enshan_push_channels: list[str] = []

    # 天翼云盘签到配置（账号密码，多账号）
    tyyun_enable: bool = False
    tyyun_username: str = ""
    tyyun_password: str = ""
    tyyun_accounts: list[dict] = []  # [{"username": str, "password": str}, ...]
    tyyun_time: str = "04:30"
    tyyun_push_channels: list[str] = []

    # 阿里云盘签到配置（refresh_token，多账号）
    aliyun_enable: bool = False
    aliyun_refresh_token: str = ""
    aliyun_refresh_tokens: list[str] = []
    aliyun_time: str = "05:30"
    aliyun_push_channels: list[str] = []

    # 什么值得买签到配置（Cookie，多账号）
    smzdm_enable: bool = False
    smzdm_cookie: str = ""
    smzdm_cookies: list[str] = []
    smzdm_time: str = "00:30"
    smzdm_push_channels: list[str] = []

    # 值得买每日抽奖配置（与 smzdm 共用 Cookie）
    zdm_draw_enable: bool = False
    zdm_draw_cookie: str = ""
    zdm_draw_cookies: list[str] = []
    zdm_draw_time: str = "07:30"
    zdm_draw_push_channels: list[str] = []

    # 富贵论坛签到配置（Cookie，多账号）
    fg_enable: bool = False
    fg_cookie: str = ""
    fg_cookies: list[str] = []
    fg_time: str = "00:01"
    fg_push_channels: list[str] = []

    # 小米社区签到配置（账号+密码，多账号；需 pycryptodome，有封号风险）
    miui_enable: bool = False
    miui_account: str = ""
    miui_password: str = ""
    miui_accounts: list[dict] = []  # [{"account": str, "password": str}, ...]
    miui_time: str = "08:30"
    miui_push_channels: list[str] = []

    # 爱奇艺签到配置（Cookie 须含 P00001/P00003/QC005/__dfp，多 Cookie）
    iqiyi_enable: bool = False
    iqiyi_cookie: str = ""
    iqiyi_cookies: list[str] = []
    iqiyi_time: str = "06:00"
    iqiyi_push_channels: list[str] = []

    # 联想乐豆签到配置（access_token，多账号）
    lenovo_enable: bool = False
    lenovo_access_token: str = ""
    lenovo_access_tokens: list[str] = []
    lenovo_time: str = "05:30"
    lenovo_push_channels: list[str] = []

    # 丽宝乐园小程序签到配置（请求体 JSON 字符串，多账号）
    lbly_enable: bool = False
    lbly_request_body: str = ""
    lbly_request_bodies: list[str] = []
    lbly_time: str = "05:30"
    lbly_push_channels: list[str] = []

    # 品赞代理签到配置（账号#密码，多账号）
    pinzan_enable: bool = False
    pinzan_account: str = ""
    pinzan_password: str = ""
    pinzan_accounts: list[dict] = []  # [{"account": str, "password": str}, ...]
    pinzan_time: str = "08:00"
    pinzan_push_channels: list[str] = []

    # 达美乐任务配置（openid，多账号 dmlck 格式 openid 或 openid,xxx）
    dml_enable: bool = False
    dml_openid: str = ""
    dml_openids: list[str] = []  # 多账号 openid 列表
    dml_time: str = "06:00"
    dml_push_channels: list[str] = []

    # 小茅预约（i茅台）配置，参考 only_for_happly/backup/imaotai.py；需 pycryptodome
    # 每条 token 格式：省份,城市,经度,纬度,设备id,token,MT-Token-Wap（小茅运领奖励，不需要可留空）
    xiaomao_enable: bool = False
    xiaomao_token: str = ""  # 单条，与 xiaomao_tokens 二选一
    xiaomao_tokens: list[str] = []  # 多账号，每条格式同上
    xiaomao_mt_version: str = ""  # 可选，不填则尝试从 App Store 页获取
    xiaomao_time: str = "09:00"  # 建议 9:00/9:30 等开放时段
    xiaomao_push_channels: list[str] = []

    # 一点万象签到（deviceParams + token，多账号，参考 only_for_happly/ydwx.py）
    ydwx_enable: bool = False
    ydwx_device_params: str = ""
    ydwx_token: str = ""
    ydwx_accounts: list[dict] = []  # [{"device_params": str, "token": str}, ...]
    ydwx_time: str = "06:00"
    ydwx_push_channels: list[str] = []

    # 星空代理签到（用户名+密码，多账号，参考 only_for_happly/xingkong.py）
    xingkong_enable: bool = False
    xingkong_username: str = ""
    xingkong_password: str = ""
    xingkong_accounts: list[dict] = []  # [{"username": str, "password": str}, ...]
    xingkong_time: str = "07:30"
    xingkong_push_channels: list[str] = []

    # Freenom 免费域名续期（多账号）
    freenom_enable: bool = False
    freenom_accounts: list[dict] = []  # [{"email": str, "password": str}, ...]
    freenom_time: str = "07:33"
    freenom_push_channels: list[str] = []

    # 天气推送（城市代码 + 7 日预报）
    weather_enable: bool = False
    weather_city_code: str = ""
    weather_time: str = "07:30"
    weather_push_channels: list[str] = []

    # 千图网签到（Cookie，多账号，参考 only_for_happly/qtw.py）
    qtw_enable: bool = False
    qtw_cookie: str = ""
    qtw_cookies: list[str] = []
    qtw_time: str = "01:30"
    qtw_push_channels: list[str] = []

    # 夸克网盘签到（Cookie，多账号，参考 only_for_happly/kuake.py）
    kuake_enable: bool = False
    kuake_cookie: str = ""
    kuake_cookies: list[str] = []
    kuake_time: str = "02:00"
    kuake_push_channels: list[str] = []

    # 科技玩家签到（账号+密码，多账号，参考 only_for_happly/kjwj.py）
    kjwj_enable: bool = False
    kjwj_accounts: list[dict] = []  # [{"username": str, "password": str}, ...]
    kjwj_time: str = "07:30"
    kjwj_push_channels: list[str] = []

    # 帆软社区签到 + 摇摇乐（Cookie）
    fr_enable: bool = False
    fr_cookie: str = ""
    fr_time: str = "06:30"
    fr_push_channels: list[str] = []

    # 999 会员中心健康打卡任务（Authorization，多账号）
    nine_nine_nine_enable: bool = False
    nine_nine_nine_tokens: list[str] = []
    nine_nine_nine_time: str = "15:15"
    nine_nine_nine_push_channels: list[str] = []

    # 中国福彩抽奖活动（Authorization，多账号）
    zgfc_enable: bool = False
    zgfc_tokens: list[str] = []
    zgfc_time: str = "08:00"
    zgfc_push_channels: list[str] = []

    # 双色球开奖监控 + 守号检测 + 冷号机选
    ssq_500w_enable: bool = False
    ssq_500w_time: str = "21:30"
    ssq_500w_push_channels: list[str] = []

    # 监控任务间隔配置
    huya_monitor_interval_seconds: int = 65  # 虎牙监控间隔（秒），默认65秒
    weibo_monitor_interval_seconds: int = 300  # 微博监控间隔（秒），默认300秒（5分钟）
    bilibili_monitor_interval_seconds: int = 60  # 哔哩哔哩监控间隔（秒），默认60秒
    douyin_monitor_interval_seconds: int = 30  # 抖音监控间隔（秒），默认30秒
    douyu_monitor_interval_seconds: int = 300  # 斗鱼监控间隔（秒），默认300秒
    xhs_monitor_interval_seconds: int = 300  # 小红书监控间隔（秒），默认300秒

    # 日志清理任务配置
    log_cleanup_enable: bool = True  # 是否启用日志清理任务
    log_cleanup_time: str = "02:10"  # 日志清理时间（HH:MM），默认 02:10
    retention_days: int = 3  # 日志保留天数，默认3天

    # 推送通道配置
    push_channel_list: list[dict] = []

    # 免打扰时段配置
    quiet_hours_enable: bool = False  # 是否启用免打扰时段
    quiet_hours_start: str = "22:00"  # 免打扰时段开始时间（格式：HH:MM）
    quiet_hours_end: str = "08:00"  # 免打扰时段结束时间（格式：HH:MM）

    # 插件/扩展任务配置（供二次开发使用，key 为任务名，value 为任意配置 dict）
    plugins: dict = {}

    def get_weibo_config(self) -> WeiboConfig:
        """获取微博配置"""
        if not self.weibo_uids:
            raise ValueError("微博配置不完整：weibo.uids 不能为空")
        uids = [uid.strip() for uid in self.weibo_uids.split(",") if uid.strip()]
        return WeiboConfig(
            cookie=self.weibo_cookie,
            uids=uids,
            concurrency=self.weibo_concurrency,
        )

    def get_huya_config(self) -> HuyaConfig:
        """获取虎牙配置"""
        if not self.huya_rooms:
            raise ValueError("虎牙配置不完整：huya.rooms 不能为空")
        rooms = [room.strip() for room in self.huya_rooms.split(",") if room.strip()]
        return HuyaConfig(
            rooms=rooms,
            concurrency=self.huya_concurrency,
        )

    def get_bilibili_config(self) -> BilibiliConfig:
        """获取哔哩哔哩配置"""
        uids = [uid.strip() for uid in (self.bilibili_uids or "").split(",") if uid.strip()]
        return BilibiliConfig(
            cookie=self.bilibili_cookie or "",
            payload=self.bilibili_payload or "",
            uids=uids,
            skip_forward=self.bilibili_skip_forward,
            concurrency=self.bilibili_concurrency,
        )

    def get_douyin_config(self) -> DouyinConfig:
        """获取抖音配置"""
        ids = [i.strip() for i in (self.douyin_douyin_ids or "").split(",") if i.strip()]
        return DouyinConfig(
            douyin_ids=ids,
            concurrency=self.douyin_concurrency,
        )

    def get_douyu_config(self) -> DouyuConfig:
        """获取斗鱼配置"""
        rooms = [room.strip() for room in (self.douyu_rooms or "").split(",") if room.strip()]
        return DouyuConfig(
            rooms=rooms,
            concurrency=self.douyu_concurrency,
        )

    def get_xhs_config(self) -> XhsConfig:
        """获取小红书配置"""
        ids = [i.strip() for i in (self.xhs_profile_ids or "").split(",") if i.strip()]
        return XhsConfig(
            cookie=self.xhs_cookie or "",
            profile_ids=ids,
            concurrency=self.xhs_concurrency,
        )


def load_config_from_yml(yml_path: str = "config.yml") -> dict:
    """
    从YAML文件加载配置并转换为AppConfig所需的格式

    Args:
        yml_path: YAML配置文件路径，默认为 config.yml

    Returns:
        配置字典（扁平化格式，用于创建AppConfig实例）
    """
    config_dict = {}
    yml_file = Path(yml_path)

    if not yml_file.exists():
        raise FileNotFoundError(f"配置文件 {yml_path} 不存在，请先创建配置文件")

    try:
        with open(yml_file, encoding="utf-8") as f:
            yml_config = yaml.safe_load(f)

        if not yml_config:
            raise ValueError(f"配置文件 {yml_path} 为空")

        # 将嵌套的YAML配置转换为扁平化格式
        # 定义配置映射：{yaml_key: {field_mapping: {yaml_field: config_field}}}
        config_mappings = {
            "app": {
                # 例如 app.base_url: "http://localhost:8866"
                "base_url": "base_url",
            },
            "weibo": {
                "enable": "weibo_enable",
                "cookie": "weibo_cookie",
                "uids": "weibo_uids",
                "concurrency": "weibo_concurrency",
                "monitor_interval_seconds": "weibo_monitor_interval_seconds",
                "push_channels": "weibo_push_channels",
                "compress_with_llm": "weibo_compress_with_llm",
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
                "accounts": "rainyun_accounts",
                "time": "rainyun_time",
                "push_channels": "rainyun_push_channels",
                "auto_renew": "rainyun_auto_renew",
                "renew_threshold_days": "rainyun_renew_threshold_days",
                "renew_product_ids": "rainyun_renew_product_ids",
                "chrome_bin": "rainyun_chrome_bin",
                "chromedriver_path": "rainyun_chromedriver_path",
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

        # 通用配置映射处理
        # 需要将 None 转换为空字符串的字段（Pydantic 期望 str 类型）
        # 注意：YAML 中类似 `account:`、`access_token:` 这类写法会被解析为 None，
        # 如果不在此列表中转换为 ""，会导致 AppConfig 校验时报 "Input should be a valid string"。
        string_fields = {
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
            # 下面这些字段在若干签到配置中经常为空配置，需要一并处理
            "account",
            "access_token",
            "request_body",
            "openid",
        }

        for section_key, field_mapping in config_mappings.items():
            if section_key in yml_config:
                section = yml_config[section_key]
                for yaml_field, config_field in field_mapping.items():
                    if yaml_field in section:
                        value = section[yaml_field]
                        # 特殊处理：字符串字段可能在 YAML 中为空（解析为 None）
                        if yaml_field in string_fields and value is None:
                            value = ""
                        # 特殊处理：push_channels 字段确保为列表
                        if yaml_field == "push_channels":
                            if value is None:
                                value = []
                            elif isinstance(value, str):
                                value = [v.strip() for v in value.split(",") if v.strip()]
                        # 特殊处理：uids/rooms/douyin_ids/profile_ids 支持 YAML 列表格式或数字，转为逗号分隔字符串
                        if yaml_field in ("uids", "rooms", "douyin_ids", "profile_ids"):
                            if isinstance(value, list):
                                value = ",".join(str(v).strip() for v in value if v)
                            elif not isinstance(value, str):
                                value = str(value) if value is not None else ""
                        config_dict[config_field] = value

        # 特殊处理：多账号配置
        if "checkin" in yml_config:
            checkin = yml_config["checkin"]
            if "accounts" in checkin and isinstance(checkin["accounts"], list):
                accounts = []
                for a in checkin["accounts"]:
                    if isinstance(a, dict):
                        accounts.append(
                            {
                                "email": str(a.get("email", "")).strip(),
                                "password": str(a.get("password", "")).strip(),
                            }
                        )
                if accounts:
                    config_dict["checkin_accounts"] = accounts

        # 特殊处理：多Cookie配置
        for cookie_section in ["tieba", "weibo_chaohua"]:
            if cookie_section in yml_config:
                section = yml_config[cookie_section]
                if "cookies" in section and isinstance(section["cookies"], list):
                    cookies = [str(c).strip() for c in section["cookies"] if c]
                    if cookies:
                        config_field = (
                            f"{cookie_section}_cookies"
                            if cookie_section == "tieba"
                            else "weibo_chaohua_cookies"
                        )
                        config_dict[config_field] = cookies

        # 特殊处理：雨云多账号（参考 Rainyun-Qiandao）及续费配置
        if "rainyun" in yml_config:
            rainyun = yml_config["rainyun"]
            if "accounts" in rainyun and isinstance(rainyun["accounts"], list):
                accounts = []
                for a in rainyun["accounts"]:
                    if isinstance(a, dict):
                        accounts.append(
                            {
                                "username": str(a.get("username", "")).strip(),
                                "password": str(a.get("password", "")).strip(),
                                "api_key": str(a.get("api_key", "")).strip(),
                            }
                        )
                if accounts:
                    config_dict["rainyun_accounts"] = accounts
            if "auto_renew" in rainyun:
                config_dict["rainyun_auto_renew"] = bool(rainyun["auto_renew"])
            if "renew_threshold_days" in rainyun:
                try:
                    config_dict["rainyun_renew_threshold_days"] = int(
                        rainyun["renew_threshold_days"]
                    )
                except (TypeError, ValueError):
                    pass
            if "renew_product_ids" in rainyun:
                ids_raw = rainyun["renew_product_ids"]
                if isinstance(ids_raw, list):
                    ids = []
                    for x in ids_raw:
                        if isinstance(x, int):
                            ids.append(x)
                        elif isinstance(x, str) and x.strip().isdigit():
                            ids.append(int(x.strip()))
                    config_dict["rainyun_renew_product_ids"] = ids
                elif isinstance(ids_raw, str) and ids_raw.strip():
                    ids = []
                    for part in ids_raw.replace(",", " ").split():
                        if part.strip().isdigit():
                            ids.append(int(part.strip()))
                    config_dict["rainyun_renew_product_ids"] = ids
            if "chrome_bin" in rainyun and rainyun["chrome_bin"]:
                config_dict["rainyun_chrome_bin"] = str(rainyun["chrome_bin"]).strip()
            if "chromedriver_path" in rainyun and rainyun["chromedriver_path"]:
                config_dict["rainyun_chromedriver_path"] = str(rainyun["chromedriver_path"]).strip()

        # 特殊处理：恩山多 Cookie
        if "enshan" in yml_config:
            en = yml_config.get("enshan") or {}
            if "cookies" in en and isinstance(en["cookies"], list):
                cookies = [str(c).strip() for c in en["cookies"] if c]
                if cookies:
                    config_dict["enshan_cookies"] = cookies

        # 特殊处理：天翼云盘多账号
        if "tyyun" in yml_config:
            ty = yml_config.get("tyyun") or {}
            if "accounts" in ty and isinstance(ty["accounts"], list):
                accounts = []
                for a in ty["accounts"]:
                    if isinstance(a, dict):
                        accounts.append(
                            {
                                "username": str(a.get("username", "")).strip(),
                                "password": str(a.get("password", "")).strip(),
                            }
                        )
                if accounts:
                    config_dict["tyyun_accounts"] = accounts

        # 特殊处理：阿里云盘多 refresh_token
        if "aliyun" in yml_config:
            ali = yml_config.get("aliyun") or {}
            if "refresh_tokens" in ali and isinstance(ali["refresh_tokens"], list):
                tokens = [str(t).strip() for t in ali["refresh_tokens"] if t]
                if tokens:
                    config_dict["aliyun_refresh_tokens"] = tokens

        # 特殊处理：什么值得买 / 值得买抽奖 / 富贵论坛 多 Cookie
        for section, config_key in [
            ("smzdm", "smzdm_cookies"),
            ("zdm_draw", "zdm_draw_cookies"),
            ("fg", "fg_cookies"),
        ]:
            sec = yml_config.get(section) or {}
            if section in yml_config and "cookies" in sec and isinstance(sec["cookies"], list):
                cookies = [str(c).strip() for c in sec["cookies"] if c]
                if cookies:
                    config_dict[config_key] = cookies

        # 小米社区多账号
        if "miui" in yml_config:
            mi = yml_config.get("miui") or {}
            if "accounts" in mi and isinstance(mi["accounts"], list):
                accounts = []
                for a in mi["accounts"]:
                    if isinstance(a, dict):
                        accounts.append(
                            {
                                "account": str(a.get("account", "")).strip(),
                                "password": str(a.get("password", "")).strip(),
                            }
                        )
                if accounts:
                    config_dict["miui_accounts"] = accounts

        # 爱奇艺多 Cookie
        if "iqiyi" in yml_config:
            iq = yml_config.get("iqiyi") or {}
            if "cookies" in iq and isinstance(iq["cookies"], list):
                cookies = [str(c).strip() for c in iq["cookies"] if c]
                if cookies:
                    config_dict["iqiyi_cookies"] = cookies

        # 联想乐豆多 access_token
        if "lenovo" in yml_config:
            lv = yml_config.get("lenovo") or {}
            if "access_tokens" in lv and isinstance(lv["access_tokens"], list):
                tokens = [str(t).strip() for t in lv["access_tokens"] if t]
                if tokens:
                    config_dict["lenovo_access_tokens"] = tokens

        # 丽宝乐园多请求体
        if "lbly" in yml_config:
            lb = yml_config.get("lbly") or {}
            if "request_bodies" in lb and isinstance(lb["request_bodies"], list):
                bodies = [str(b).strip() for b in lb["request_bodies"] if b]
                if bodies:
                    config_dict["lbly_request_bodies"] = bodies

        # 品赞多账号
        if "pinzan" in yml_config:
            pz = yml_config.get("pinzan") or {}
            if "accounts" in pz and isinstance(pz["accounts"], list):
                accounts = []
                for a in pz["accounts"]:
                    if isinstance(a, dict):
                        accounts.append(
                            {
                                "account": str(a.get("account", "")).strip(),
                                "password": str(a.get("password", "")).strip(),
                            }
                        )
                if accounts:
                    config_dict["pinzan_accounts"] = accounts

        # 达美乐多 openid
        if "dml" in yml_config:
            dm = yml_config.get("dml") or {}
            if "openids" in dm and isinstance(dm["openids"], list):
                openids = [str(o).strip() for o in dm["openids"] if o]
                if openids:
                    config_dict["dml_openids"] = openids

        # 小茅预约多 token
        if "xiaomao" in yml_config:
            xm = yml_config.get("xiaomao") or {}
            if "tokens" in xm and isinstance(xm["tokens"], list):
                tokens = [str(t).strip() for t in xm["tokens"] if t]
                if tokens:
                    config_dict["xiaomao_tokens"] = tokens

        # 一点万象多账号 (device_params + token)
        if "ydwx" in yml_config:
            yd = yml_config.get("ydwx") or {}
            if "accounts" in yd and isinstance(yd["accounts"], list):
                accs = []
                for a in yd["accounts"]:
                    if isinstance(a, dict):
                        accs.append(
                            {
                                "device_params": str(a.get("device_params", "")).strip(),
                                "token": str(a.get("token", "")).strip(),
                            }
                        )
                if accs:
                    config_dict["ydwx_accounts"] = accs

        # 星空代理多账号
        if "xingkong" in yml_config:
            xk = yml_config.get("xingkong") or {}
            if "accounts" in xk and isinstance(xk["accounts"], list):
                accs = []
                for a in xk["accounts"]:
                    if isinstance(a, dict):
                        accs.append(
                            {
                                "username": str(a.get("username", "")).strip(),
                                "password": str(a.get("password", "")).strip(),
                            }
                        )
                if accs:
                    config_dict["xingkong_accounts"] = accs

        # 千图网多 Cookie
        if "qtw" in yml_config:
            qt = yml_config.get("qtw") or {}
            if "cookies" in qt and isinstance(qt["cookies"], list):
                cookies = [str(c).strip() for c in qt["cookies"] if c]
                if cookies:
                    config_dict["qtw_cookies"] = cookies

        # 夸克网盘多 Cookie
        if "kuake" in yml_config:
            kq = yml_config.get("kuake") or {}
            if "cookies" in kq and isinstance(kq["cookies"], list):
                cookies = [str(c).strip() for c in kq["cookies"] if c]
                if cookies:
                    config_dict["kuake_cookies"] = cookies

        # 科技玩家多账号
        if "kjwj" in yml_config:
            kj = yml_config.get("kjwj") or {}
            if "accounts" in kj and isinstance(kj["accounts"], list):
                accs: list[dict] = []
                for a in kj["accounts"]:
                    if isinstance(a, dict):
                        accs.append(
                            {
                                "username": str(a.get("username", "")).strip(),
                                "password": str(a.get("password", "")).strip(),
                            }
                        )
                if accs:
                    config_dict["kjwj_accounts"] = accs

        # 999 会员中心多 token
        if "nine_nine_nine" in yml_config:
            nnn = yml_config.get("nine_nine_nine") or {}
            if "tokens" in nnn and isinstance(nnn["tokens"], list):
                toks = [str(t).strip() for t in nnn["tokens"] if t]
                if toks:
                    config_dict["nine_nine_nine_tokens"] = toks

        # 中国福彩抽奖多 token
        if "zgfc" in yml_config:
            zc = yml_config.get("zgfc") or {}
            if "tokens" in zc and isinstance(zc["tokens"], list):
                toks = [str(t).strip() for t in zc["tokens"] if t]
                if toks:
                    config_dict["zgfc_tokens"] = toks

        # Freenom 多账号
        if "freenom" in yml_config:
            fn = yml_config.get("freenom") or {}
            if "accounts" in fn and isinstance(fn["accounts"], list):
                accs: list[dict] = []
                for a in fn["accounts"]:
                    if isinstance(a, dict):
                        accs.append(
                            {
                                "email": str(a.get("email", "")).strip(),
                                "password": str(a.get("password", "")).strip(),
                            }
                        )
                if accs:
                    config_dict["freenom_accounts"] = accs

        # 推送通道配置（直接复制）
        if "push_channel" in yml_config:
            config_dict["push_channel_list"] = yml_config["push_channel"]

        # 插件/扩展任务配置（直接复制）
        if "plugins" in yml_config:
            config_dict["plugins"] = yml_config["plugins"]

        logger.debug(f"成功从 {yml_path} 加载配置")
        return config_dict

    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValueError(f"加载配置文件 {yml_path} 失败: {e}") from e


# 全局配置缓存，用于热重载时检测变化
_config_cache: AppConfig | None = None
_config_file_mtime: float = 0  # 配置文件最后修改时间


def get_config(reload: bool = False) -> AppConfig:
    """
    从config.yml文件获取配置

    Args:
        reload: 是否重新加载配置文件（用于热重载）
               如果为True，会强制重新读取config.yml文件

    Returns:
        AppConfig实例
    """
    global _config_cache, _config_file_mtime

    # 青龙面板兼容：当通过 ql/*.py 脚本运行时，从环境变量加载配置
    import os

    if os.environ.get("WEBMONITER_QL_CRON"):
        try:
            from src import ql_compat

            task_id = getattr(ql_compat, "_current_ql_task_id", None)
            if task_id is not None:
                cfg = ql_compat.load_config_from_env(task_id)
                _config_cache = AppConfig(**cfg)
                return _config_cache
        except Exception:  # noqa: BLE001
            pass

    old_weibo_cookie = _config_cache.weibo_cookie if _config_cache is not None else None

    # 检查配置文件修改时间（优化热重载效率）
    config_file_path = Path("config.yml")
    current_mtime = 0
    if config_file_path.exists():
        current_mtime = config_file_path.stat().st_mtime

    # 如果不需要重载且已有缓存，检查文件是否被修改
    if not reload and _config_cache is not None:
        # 如果文件未被修改，直接返回缓存
        if current_mtime <= _config_file_mtime:
            return _config_cache
        # 文件被修改了，需要重新加载
        logger.debug("检测到配置文件已修改，自动重新加载...")

    if reload:
        logger.debug("开始重新加载配置文件...")
    yml_config = load_config_from_yml()
    _config_file_mtime = current_mtime  # 更新文件修改时间

    # 创建AppConfig实例
    config = AppConfig(**yml_config)

    _config_cache = config
    new_weibo_cookie = config.weibo_cookie
    if old_weibo_cookie is not None and old_weibo_cookie != new_weibo_cookie:
        logger.info("微博Cookie已更新 (长度: %s 字符)", len(new_weibo_cookie or ""))

    return config


def _parse_quiet_time(time_str: str) -> time | None:
    """解析 HH:MM 格式时间为 time 对象，非法格式返回 None"""
    if not time_str or not isinstance(time_str, str):
        return None
    parts = (time_str or "").strip().split(":", 2)
    if len(parts) < 2:
        return None
    try:
        h, m = int(parts[0].strip()), int(parts[1].strip())
        if 0 <= h <= 23 and 0 <= m <= 59:
            return time(h, m)
    except (ValueError, TypeError):
        pass
    return None


def is_in_quiet_hours(config: AppConfig) -> bool:
    """
    检查当前时间是否在免打扰时段内

    Args:
        config: 应用配置实例

    Returns:
        如果当前时间在免打扰时段内返回True，否则返回False
    """
    if not config.quiet_hours_enable:
        return False

    start_time = _parse_quiet_time(config.quiet_hours_start)
    end_time = _parse_quiet_time(config.quiet_hours_end)
    if start_time is None or end_time is None:
        logger.warning(
            "免打扰时段配置格式有误（应为 HH:MM），start=%s, end=%s，默认返回False",
            config.quiet_hours_start,
            config.quiet_hours_end,
        )
        return False

    now = datetime.now().time()

    # 判断是否跨天（例如：22:00 到 08:00）
    if start_time > end_time:
        return now >= start_time or now <= end_time
    return start_time <= now <= end_time


def parse_checkin_time(checkin_time: str) -> tuple[str, str]:
    """
    解析签到时间配置（HH:MM）为 cron 的 hour、minute。
    供调度器与配置热重载使用。

    Args:
        checkin_time: 时间字符串，如 "08:00"、"23:55"

    Returns:
        (hour, minute) 字符串元组，如 ("8", "0")。无效时默认 ("8", "0")。
    """
    raw = (checkin_time or "08:00").strip()
    parts = raw.split(":", 1)
    try:
        h = int(parts[0].strip()) if parts else 8
        m = int(parts[1].strip()) if len(parts) > 1 else 0
        if 0 <= h <= 23 and 0 <= m <= 59:
            return str(h), str(m)
    except (ValueError, IndexError):
        pass
    return "8", "0"
