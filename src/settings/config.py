"""配置管理模块 - 从YAML配置文件读取配置"""

import logging
import os
import threading
from datetime import datetime, time
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from src.core.paths import CONFIG_YAML_FILE
from src.settings.loader_specs import (
    CONFIG_MAPPINGS,
    MULTI_ACCOUNT_SPECS,
    MULTI_STRING_SPECS,
    STRING_FIELDS,
)

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
    weibo_push_channels: list[str] = Field(
        default_factory=list
    )  # 推送通道名称列表，为空时使用全部通道

    # 虎牙
    huya_enable: bool = True  # 是否启用虎牙监控
    huya_rooms: str = ""  # 逗号分隔的房间号列表
    huya_concurrency: int = 7  # 虎牙监控并发数，建议5-10（相对宽松）
    huya_push_channels: list[str] = Field(
        default_factory=list
    )  # 推送通道名称列表，为空时使用全部通道

    # 哔哩哔哩
    bilibili_enable: bool = True  # 是否启用哔哩哔哩监控
    bilibili_cookie: str = ""
    bilibili_payload: str = ""
    bilibili_uids: str = ""
    bilibili_skip_forward: bool = True
    bilibili_concurrency: int = 2
    bilibili_push_channels: list[str] = Field(default_factory=list)

    # 抖音
    douyin_enable: bool = True  # 是否启用抖音直播监控
    douyin_douyin_ids: str = ""
    douyin_concurrency: int = 2
    douyin_push_channels: list[str] = Field(default_factory=list)

    # 斗鱼
    douyu_enable: bool = True  # 是否启用斗鱼直播监控
    douyu_rooms: str = ""
    douyu_concurrency: int = 2
    douyu_push_channels: list[str] = Field(default_factory=list)

    # 小红书
    xhs_enable: bool = True  # 是否启用小红书动态监控
    xhs_cookie: str = ""
    xhs_profile_ids: str = ""
    xhs_concurrency: int = 2
    xhs_push_channels: list[str] = Field(default_factory=list)

    # 每日签到配置（域名自动从 ikuuu.club 发现，无需手动配置 URL）
    checkin_enable: bool = False  # 是否启用每日签到
    checkin_email: str = ""  # 单账号：登录账号（与 checkin_password 搭配）
    checkin_password: str = ""  # 单账号：登录密码
    checkin_accounts: list[dict] = Field(
        default_factory=list
    )  # 多账号：[{"email": str, "password": str}, ...]，非空时优先于单账号
    checkin_time: str = "08:00"  # 签到时间（默认每天早上 8 点，格式：HH:MM）
    checkin_push_channels: list[str] = Field(
        default_factory=list
    )  # 推送通道名称列表，为空时使用全部通道

    # 百度贴吧签到配置（使用 Cookie）
    tieba_enable: bool = False  # 是否启用贴吧签到
    tieba_cookie: str = ""  # 单 Cookie（与 tieba_cookies 二选一，须包含 BDUSS）
    tieba_cookies: list[str] = Field(
        default_factory=list
    )  # 多 Cookie 列表，非空时优先于 tieba_cookie
    tieba_time: str = "08:10"  # 贴吧签到时间（格式：HH:MM），默认 08:10
    tieba_push_channels: list[str] = Field(
        default_factory=list
    )  # 推送通道名称列表，为空时使用全部通道

    # 微博超话签到配置（使用 Cookie）
    weibo_chaohua_enable: bool = False  # 是否启用微博超话签到
    weibo_chaohua_cookie: str = (
        ""  # 单 Cookie（与 weibo_chaohua_cookies 二选一，须包含 XSRF-TOKEN）
    )
    weibo_chaohua_cookies: list[str] = Field(
        default_factory=list
    )  # 多 Cookie 列表，非空时优先于 weibo_chaohua_cookie
    weibo_chaohua_time: str = "23:45"  # 微博超话签到时间（格式：HH:MM），默认 23:45
    weibo_chaohua_push_channels: list[str] = Field(
        default_factory=list
    )  # 推送通道名称列表，为空时使用全部通道

    # 雨云签到配置（参考 Rainyun-Qiandao：Selenium + 账号密码 + ddddocr）
    rainyun_enable: bool = False  # 是否启用雨云签到
    rainyun_accounts: list[dict] = Field(
        default_factory=list
    )  # [{"username": str, "password": str, "api_key": str?}, ...]
    rainyun_time: str = "08:30"  # 雨云签到时间（格式：HH:MM），默认 08:30
    rainyun_push_channels: list[str] = Field(
        default_factory=list
    )  # 推送通道名称列表，为空时使用全部通道
    # 雨云自动续费配置（参考 Jielumoon/Rainyun-Qiandao）
    rainyun_auto_renew: bool = True  # 是否启用服务器到期自动续费
    rainyun_renew_threshold_days: int = 7  # 剩余多少天内触发续费，默认 7 天
    rainyun_renew_product_ids: list[int] = Field(
        default_factory=list
    )  # 续费白名单（产品 ID 列表），为空则续费所有即将到期的服务器
    rainyun_chrome_bin: str = ""  # Chrome/Chromium 可执行路径，Docker 下通常用环境变量 CHROME_BIN
    rainyun_chromedriver_path: str = (
        ""  # chromedriver 路径，Docker 下通常用环境变量 CHROMEDRIVER_PATH
    )

    # 恩山论坛签到配置（Cookie）
    enshan_enable: bool = False
    enshan_cookie: str = ""
    enshan_cookies: list[str] = Field(default_factory=list)
    enshan_time: str = "02:00"
    enshan_push_channels: list[str] = Field(default_factory=list)

    # 天翼云盘签到配置（账号密码，多账号）
    tyyun_enable: bool = False
    tyyun_username: str = ""
    tyyun_password: str = ""
    tyyun_accounts: list[dict] = Field(
        default_factory=list
    )  # [{"username": str, "password": str}, ...]
    tyyun_time: str = "04:30"
    tyyun_push_channels: list[str] = Field(default_factory=list)

    # 阿里云盘签到配置（refresh_token，多账号）
    aliyun_enable: bool = False
    aliyun_refresh_token: str = ""
    aliyun_refresh_tokens: list[str] = Field(default_factory=list)
    aliyun_time: str = "05:30"
    aliyun_push_channels: list[str] = Field(default_factory=list)

    # 什么值得买签到配置（Cookie，多账号）
    smzdm_enable: bool = False
    smzdm_cookie: str = ""
    smzdm_cookies: list[str] = Field(default_factory=list)
    smzdm_time: str = "00:30"
    smzdm_push_channels: list[str] = Field(default_factory=list)

    # 值得买每日抽奖配置（与 smzdm 共用 Cookie）
    zdm_draw_enable: bool = False
    zdm_draw_cookie: str = ""
    zdm_draw_cookies: list[str] = Field(default_factory=list)
    zdm_draw_time: str = "07:30"
    zdm_draw_push_channels: list[str] = Field(default_factory=list)

    # 富贵论坛签到配置（Cookie，多账号）
    fg_enable: bool = False
    fg_cookie: str = ""
    fg_cookies: list[str] = Field(default_factory=list)
    fg_time: str = "00:01"
    fg_push_channels: list[str] = Field(default_factory=list)

    # 小米社区签到配置（账号+密码，多账号；需 pycryptodome，有封号风险）
    miui_enable: bool = False
    miui_account: str = ""
    miui_password: str = ""
    miui_accounts: list[dict] = Field(
        default_factory=list
    )  # [{"account": str, "password": str}, ...]
    miui_time: str = "08:30"
    miui_push_channels: list[str] = Field(default_factory=list)

    # 爱奇艺签到配置（Cookie 须含 P00001/P00003/QC005/__dfp，多 Cookie）
    iqiyi_enable: bool = False
    iqiyi_cookie: str = ""
    iqiyi_cookies: list[str] = Field(default_factory=list)
    iqiyi_time: str = "06:00"
    iqiyi_push_channels: list[str] = Field(default_factory=list)

    # 联想乐豆签到配置（access_token，多账号）
    lenovo_enable: bool = False
    lenovo_access_token: str = ""
    lenovo_access_tokens: list[str] = Field(default_factory=list)
    lenovo_time: str = "05:30"
    lenovo_push_channels: list[str] = Field(default_factory=list)

    # 丽宝乐园小程序签到配置（请求体 JSON 字符串，多账号）
    lbly_enable: bool = False
    lbly_request_body: str = ""
    lbly_request_bodies: list[str] = Field(default_factory=list)
    lbly_time: str = "05:30"
    lbly_push_channels: list[str] = Field(default_factory=list)

    # 品赞代理签到配置（账号#密码，多账号）
    pinzan_enable: bool = False
    pinzan_account: str = ""
    pinzan_password: str = ""
    pinzan_accounts: list[dict] = Field(
        default_factory=list
    )  # [{"account": str, "password": str}, ...]
    pinzan_time: str = "08:00"
    pinzan_push_channels: list[str] = Field(default_factory=list)

    # 达美乐任务配置（openid，多账号 dmlck 格式 openid 或 openid,xxx）
    dml_enable: bool = False
    dml_openid: str = ""
    dml_openids: list[str] = Field(default_factory=list)  # 多账号 openid 列表
    dml_time: str = "06:00"
    dml_push_channels: list[str] = Field(default_factory=list)

    # 小茅预约（i茅台）配置，参考 only_for_happly/backup/imaotai.py；需 pycryptodome
    # 每条 token 格式：省份,城市,经度,纬度,设备id,token,MT-Token-Wap（小茅运领奖励，不需要可留空）
    xiaomao_enable: bool = False
    xiaomao_token: str = ""  # 单条，与 xiaomao_tokens 二选一
    xiaomao_tokens: list[str] = Field(default_factory=list)  # 多账号，每条格式同上
    xiaomao_mt_version: str = ""  # 可选，不填则尝试从 App Store 页获取
    xiaomao_time: str = "09:00"  # 建议 9:00/9:30 等开放时段
    xiaomao_push_channels: list[str] = Field(default_factory=list)

    # 一点万象签到（deviceParams + token，多账号，参考 only_for_happly/ydwx.py）
    ydwx_enable: bool = False
    ydwx_device_params: str = ""
    ydwx_token: str = ""
    ydwx_accounts: list[dict] = Field(
        default_factory=list
    )  # [{"device_params": str, "token": str}, ...]
    ydwx_time: str = "06:00"
    ydwx_push_channels: list[str] = Field(default_factory=list)

    # 星空代理签到（用户名+密码，多账号，参考 only_for_happly/xingkong.py）
    xingkong_enable: bool = False
    xingkong_username: str = ""
    xingkong_password: str = ""
    xingkong_accounts: list[dict] = Field(
        default_factory=list
    )  # [{"username": str, "password": str}, ...]
    xingkong_time: str = "07:30"
    xingkong_push_channels: list[str] = Field(default_factory=list)

    # Freenom 免费域名续期（多账号）
    freenom_enable: bool = False
    freenom_accounts: list[dict] = Field(
        default_factory=list
    )  # [{"email": str, "password": str}, ...]
    freenom_time: str = "07:33"
    freenom_push_channels: list[str] = Field(default_factory=list)

    # 天气推送（城市代码 + 7 日预报）
    weather_enable: bool = False
    weather_city_code: str = ""
    weather_time: str = "07:30"
    weather_push_channels: list[str] = Field(default_factory=list)

    # 千图网签到（Cookie，多账号，参考 only_for_happly/qtw.py）
    qtw_enable: bool = False
    qtw_cookie: str = ""
    qtw_cookies: list[str] = Field(default_factory=list)
    qtw_time: str = "01:30"
    qtw_push_channels: list[str] = Field(default_factory=list)

    # 夸克网盘签到（Cookie，多账号，参考 only_for_happly/kuake.py）
    kuake_enable: bool = False
    kuake_cookie: str = ""
    kuake_cookies: list[str] = Field(default_factory=list)
    kuake_time: str = "02:00"
    kuake_push_channels: list[str] = Field(default_factory=list)

    # 科技玩家签到（账号+密码，多账号，参考 only_for_happly/kjwj.py）
    kjwj_enable: bool = False
    kjwj_accounts: list[dict] = Field(
        default_factory=list
    )  # [{"username": str, "password": str}, ...]
    kjwj_time: str = "07:30"
    kjwj_push_channels: list[str] = Field(default_factory=list)

    # 帆软社区签到 + 摇摇乐（Cookie）
    fr_enable: bool = False
    fr_cookie: str = ""
    fr_time: str = "06:30"
    fr_push_channels: list[str] = Field(default_factory=list)

    # 999 会员中心健康打卡任务（Authorization，多账号）
    nine_nine_nine_enable: bool = False
    nine_nine_nine_tokens: list[str] = Field(default_factory=list)
    nine_nine_nine_time: str = "15:15"
    nine_nine_nine_push_channels: list[str] = Field(default_factory=list)

    # 中国福彩抽奖活动（Authorization，多账号）
    zgfc_enable: bool = False
    zgfc_tokens: list[str] = Field(default_factory=list)
    zgfc_time: str = "08:00"
    zgfc_push_channels: list[str] = Field(default_factory=list)

    # 双色球开奖监控 + 守号检测 + 冷号机选
    ssq_500w_enable: bool = False
    ssq_500w_time: str = "21:30"
    ssq_500w_push_channels: list[str] = Field(default_factory=list)

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
    push_channel_list: list[dict] = Field(default_factory=list)

    # 免打扰时段配置
    quiet_hours_enable: bool = False  # 是否启用免打扰时段
    quiet_hours_start: str = "22:00"  # 免打扰时段开始时间（格式：HH:MM）
    quiet_hours_end: str = "08:00"  # 免打扰时段结束时间（格式：HH:MM）

    # 插件/扩展任务配置（供二次开发使用，key 为任务名，value 为任意配置 dict）
    plugins: dict = Field(default_factory=dict)

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


def _parse_multi_strings(
    yml_config: dict,
    section_key: str,
    yaml_key: str,
    config_key: str,
    config_dict: dict,
) -> None:
    """从 YAML 节点解析字符串列表（cookies / tokens / openids / request_bodies 等）"""
    section = yml_config.get(section_key) or {}
    raw = section.get(yaml_key)
    if isinstance(raw, list):
        values = [str(v).strip() for v in raw if v]
        if values:
            config_dict[config_key] = values


def _parse_multi_accounts(
    yml_config: dict,
    section_key: str,
    fields: list[str],
    config_key: str,
    config_dict: dict,
) -> None:
    """从 YAML 节点解析账号字典列表，每个账号按 fields 指定的键名提取并 strip"""
    section = yml_config.get(section_key) or {}
    raw = section.get("accounts")
    if isinstance(raw, list):
        accounts = []
        for item in raw:
            if isinstance(item, dict):
                accounts.append({f: str(item.get(f, "")).strip() for f in fields})
        if accounts:
            config_dict[config_key] = accounts


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

        # Convert nested YAML sections into AppConfig flat fields.
        for section_key, field_mapping in CONFIG_MAPPINGS.items():
            if section_key in yml_config:
                section = yml_config[section_key]
                for yaml_field, config_field in field_mapping.items():
                    if yaml_field in section:
                        value = section[yaml_field]
                        if yaml_field in STRING_FIELDS and value is None:
                            value = ""
                        if yaml_field == "push_channels":
                            if value is None:
                                value = []
                            elif isinstance(value, str):
                                value = [v.strip() for v in value.split(",") if v.strip()]
                        if yaml_field in ("uids", "rooms", "douyin_ids", "profile_ids"):
                            if isinstance(value, list):
                                value = ",".join(str(v).strip() for v in value if v)
                            elif not isinstance(value, str):
                                value = str(value) if value is not None else ""
                        config_dict[config_field] = value

        # Multi-account sections.
        for spec in MULTI_ACCOUNT_SPECS:
            _parse_multi_accounts(
                yml_config, spec.section_key, list(spec.fields), spec.config_key, config_dict
            )

        # Multi-cookie / token / string-list sections.
        for spec in MULTI_STRING_SPECS:
            _parse_multi_strings(
                yml_config, spec.section_key, spec.yaml_key, spec.config_key, config_dict
            )

        # Rainyun renewal options (accounts are handled by the specs above).
        rainyun = yml_config.get("rainyun") or {}
        if "auto_renew" in rainyun:
            config_dict["rainyun_auto_renew"] = bool(rainyun["auto_renew"])
        if "renew_threshold_days" in rainyun:
            try:
                config_dict["rainyun_renew_threshold_days"] = int(rainyun["renew_threshold_days"])
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
        if rainyun.get("chrome_bin"):
            config_dict["rainyun_chrome_bin"] = str(rainyun["chrome_bin"]).strip()
        if rainyun.get("chromedriver_path"):
            config_dict["rainyun_chromedriver_path"] = str(rainyun["chromedriver_path"]).strip()

        # 推送通道配置（直接复制，需确保为 list 类型）
        if "push_channel" in yml_config:
            push_ch = yml_config["push_channel"]
            config_dict["push_channel_list"] = push_ch if isinstance(push_ch, list) else []

        # 插件/扩展任务配置（直接复制，需确保为 dict 类型）
        if "plugins" in yml_config:
            plugins_val = yml_config["plugins"]
            config_dict["plugins"] = plugins_val if isinstance(plugins_val, dict) else {}

        logger.debug("成功从 %s 加载配置", yml_path)
        return config_dict

    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValueError(f"加载配置文件 {yml_path} 失败: {e}") from e


# 全局配置缓存，用于热重载时检测变化
_config_cache: AppConfig | None = None
_config_file_mtime: float = 0  # 配置文件最后修改时间
_config_lock = threading.RLock()


def _read_config_mtime() -> float:
    """读取配置文件修改时间；不存在时返回 0。"""
    config_file_path = CONFIG_YAML_FILE
    if config_file_path.exists():
        return config_file_path.stat().st_mtime
    return 0


def _try_return_cached_config(reload: bool, current_mtime: float) -> AppConfig | None:
    """无锁快速路径：缓存仍有效时直接返回。"""
    if reload or _config_cache is None:
        return None
    if current_mtime <= _config_file_mtime:
        return _config_cache
    return None


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

    current_mtime = _read_config_mtime()
    cached = _try_return_cached_config(reload, current_mtime)
    if cached is not None:
        return cached

    with _config_lock:
        # 青龙面板兼容：当通过 python -m src.ql 运行时，从环境变量加载配置
        if os.environ.get("WEBMONITER_QL_CRON"):
            try:
                from src.ql import compat as ql_compat

                task_id = getattr(ql_compat, "_current_ql_task_id", None)
                if task_id is not None:
                    cfg = ql_compat.load_config_from_env(task_id)
                    _config_cache = AppConfig(**cfg)
                    return _config_cache
            except Exception:  # noqa: BLE001
                pass

        current_mtime = _read_config_mtime()
        cached = _try_return_cached_config(reload, current_mtime)
        if cached is not None:
            return cached

        if not reload and _config_cache is not None and current_mtime > _config_file_mtime:
            logger.debug("检测到配置文件已修改，自动重新加载...")

        old_weibo_cookie = _config_cache.weibo_cookie if _config_cache is not None else None

        if reload:
            logger.debug("开始重新加载配置文件...")
        yml_config = load_config_from_yml()
        _config_file_mtime = current_mtime

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
    parts = time_str.strip().split(":", 2)
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
