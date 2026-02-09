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


class AppConfig(BaseModel):
    """应用配置"""

    # 微博
    weibo_cookie: str = ""
    weibo_uids: str = ""  # 逗号分隔的UID列表
    weibo_concurrency: int = 3  # 微博监控并发数，建议2-5（避免触发限流）
    weibo_push_channels: list[str] = []  # 推送通道名称列表，为空时使用全部通道

    # 虎牙
    huya_rooms: str = ""  # 逗号分隔的房间号列表
    huya_concurrency: int = 7  # 虎牙监控并发数，建议5-10（相对宽松）
    huya_push_channels: list[str] = []  # 推送通道名称列表，为空时使用全部通道

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

    # 调度器配置
    huya_monitor_interval_seconds: int = 65  # 虎牙监控间隔（秒），默认65秒
    weibo_monitor_interval_seconds: int = 300  # 微博监控间隔（秒），默认300秒（5分钟）
    cleanup_logs_hour: int = 2  # 日志清理时间（小时），默认2点
    cleanup_logs_minute: int = 0  # 日志清理时间（分钟），默认0分
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
            "weibo": {
                "cookie": "weibo_cookie",
                "uids": "weibo_uids",
                "concurrency": "weibo_concurrency",
                "push_channels": "weibo_push_channels",
            },
            "huya": {
                "rooms": "huya_rooms",
                "concurrency": "huya_concurrency",
                "push_channels": "huya_push_channels",
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
            "scheduler": {
                "huya_monitor_interval_seconds": "huya_monitor_interval_seconds",
                "weibo_monitor_interval_seconds": "weibo_monitor_interval_seconds",
                "cleanup_logs_hour": "cleanup_logs_hour",
                "cleanup_logs_minute": "cleanup_logs_minute",
                "retention_days": "retention_days",
            },
            "quiet_hours": {
                "enable": "quiet_hours_enable",
                "start": "quiet_hours_start",
                "end": "quiet_hours_end",
            },
        }

        # 通用配置映射处理
        for section_key, field_mapping in config_mappings.items():
            if section_key in yml_config:
                section = yml_config[section_key]
                for yaml_field, config_field in field_mapping.items():
                    if yaml_field in section:
                        value = section[yaml_field]
                        # 特殊处理：cookie字段可能为空字符串
                        if yaml_field == "cookie" and value is None:
                            value = ""
                        # 特殊处理：push_channels 字段确保为列表
                        if yaml_field == "push_channels":
                            if value is None:
                                value = []
                            elif isinstance(value, str):
                                value = [v.strip() for v in value.split(",") if v.strip()]
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

    try:
        # 解析时间字符串（格式：HH:MM）
        start_time_str = config.quiet_hours_start
        end_time_str = config.quiet_hours_end

        # 解析开始和结束时间
        start_hour, start_minute = map(int, start_time_str.split(":"))
        end_hour, end_minute = map(int, end_time_str.split(":"))

        start_time = time(start_hour, start_minute)
        end_time = time(end_hour, end_minute)

        # 获取当前时间
        now = datetime.now().time()

        # 判断是否跨天（例如：22:00 到 08:00）
        if start_time > end_time:
            # 跨天情况：当前时间 >= 开始时间 或 当前时间 <= 结束时间
            return now >= start_time or now <= end_time
        else:
            # 不跨天情况：开始时间 <= 当前时间 <= 结束时间
            return start_time <= now <= end_time
    except Exception as e:
        logger.warning(f"检查免打扰时段时出错: {e}，默认返回False")
        return False


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
