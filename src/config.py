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

    user_agent: str
    cookie: str
    rooms: list[str]
    concurrency: int = 7  # 并发数，默认7，建议5-10


class AppConfig(BaseModel):
    """应用配置"""

    # 微博
    weibo_cookie: str = ""
    weibo_uids: str = ""  # 逗号分隔的UID列表
    weibo_concurrency: int = 3  # 微博监控并发数，建议2-5（避免触发限流）

    # 虎牙
    huya_user_agent: str = ""
    huya_cookie: str = ""
    huya_rooms: str = ""  # 逗号分隔的房间号列表
    huya_concurrency: int = 7  # 虎牙监控并发数，建议5-10（相对宽松）

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
            user_agent=self.huya_user_agent,
            cookie=self.huya_cookie,
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
        # 微博配置
        if "weibo" in yml_config:
            weibo = yml_config["weibo"]
            if "cookie" in weibo:
                config_dict["weibo_cookie"] = weibo["cookie"]
            if "uids" in weibo:
                config_dict["weibo_uids"] = weibo["uids"]
            if "concurrency" in weibo:
                config_dict["weibo_concurrency"] = weibo["concurrency"]

        # 虎牙配置
        if "huya" in yml_config:
            huya = yml_config["huya"]
            if "user_agent" in huya:
                config_dict["huya_user_agent"] = huya["user_agent"]
            # cookie是可选的，如果不存在或为null，使用空字符串
            if "cookie" in huya:
                config_dict["huya_cookie"] = huya["cookie"] or ""
            else:
                config_dict["huya_cookie"] = ""
            if "rooms" in huya:
                config_dict["huya_rooms"] = huya["rooms"]
            if "concurrency" in huya:
                config_dict["huya_concurrency"] = huya["concurrency"]

        # 调度器配置
        if "scheduler" in yml_config:
            scheduler = yml_config["scheduler"]
            if "huya_monitor_interval_seconds" in scheduler:
                config_dict["huya_monitor_interval_seconds"] = scheduler[
                    "huya_monitor_interval_seconds"
                ]
            if "weibo_monitor_interval_seconds" in scheduler:
                config_dict["weibo_monitor_interval_seconds"] = scheduler[
                    "weibo_monitor_interval_seconds"
                ]
            if "cleanup_logs_hour" in scheduler:
                config_dict["cleanup_logs_hour"] = scheduler["cleanup_logs_hour"]
            if "cleanup_logs_minute" in scheduler:
                config_dict["cleanup_logs_minute"] = scheduler["cleanup_logs_minute"]
            if "retention_days" in scheduler:
                config_dict["retention_days"] = scheduler["retention_days"]

        # 推送通道配置
        if "push_channel" in yml_config:
            config_dict["push_channel_list"] = yml_config["push_channel"]

        # 免打扰时段配置
        if "quiet_hours" in yml_config:
            quiet_hours = yml_config["quiet_hours"]
            if "enable" in quiet_hours:
                config_dict["quiet_hours_enable"] = quiet_hours["enable"]
            if "start" in quiet_hours:
                config_dict["quiet_hours_start"] = quiet_hours["start"]
            if "end" in quiet_hours:
                config_dict["quiet_hours_end"] = quiet_hours["end"]

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

    # 记录原始值（如果存在，用于检测变化）
    old_weibo_cookie = None
    old_huya_cookie = None
    if _config_cache is not None:
        old_weibo_cookie = _config_cache.weibo_cookie
        old_huya_cookie = _config_cache.huya_cookie

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

    # 从YAML文件加载配置
    if reload:
        logger.debug("开始重新加载配置文件...")
    else:
        logger.debug("加载配置文件...")

    yml_config = load_config_from_yml()
    _config_file_mtime = current_mtime  # 更新文件修改时间

    # 创建AppConfig实例
    config = AppConfig(**yml_config)

    # 更新缓存
    _config_cache = config

    # 记录新值并检测变化
    new_weibo_cookie = config.weibo_cookie
    new_huya_cookie = config.huya_cookie

    logger.debug("配置加载完成")
    # 只在Cookie真正变化时才记录INFO级别的日志
    if old_weibo_cookie is not None and old_weibo_cookie != new_weibo_cookie:
        logger.info(f"微博Cookie已更新 (长度: {len(new_weibo_cookie or '')} 字符)")
    else:
        logger.debug("微博Cookie未变更")

    if old_huya_cookie is not None and old_huya_cookie != new_huya_cookie:
        logger.info(f"虎牙Cookie已更新 (长度: {len(new_huya_cookie or '')} 字符)")
    else:
        logger.debug("虎牙Cookie未变更")

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
