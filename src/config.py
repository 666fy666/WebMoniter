"""配置管理模块 - 从YAML配置文件读取配置"""
import logging
from pathlib import Path
from typing import Optional

import aiohttp
import yaml
from pydantic import BaseModel

# 获取logger
logger = logging.getLogger(__name__)


class WeChatConfig(BaseModel):
    """企业微信配置"""
    corpid: str
    secret: str
    agentid: str
    touser: str
    pushplus: Optional[str] = None
    email: Optional[str] = None


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
    # 企业微信
    wechat_corpid: str
    wechat_secret: str
    wechat_agentid: str
    wechat_touser: str
    wechat_pushplus: Optional[str] = None
    wechat_email: Optional[str] = None

    # 微博
    weibo_cookie: str
    weibo_uids: str  # 逗号分隔的UID列表
    weibo_concurrency: int = 3  # 微博监控并发数，建议2-5（避免触发限流）

    # 虎牙
    huya_user_agent: str
    huya_cookie: str
    huya_rooms: str  # 逗号分隔的房间号列表
    huya_concurrency: int = 7  # 虎牙监控并发数，建议5-10（相对宽松）

    # 调度器配置
    huya_monitor_interval_seconds: int = 65  # 虎牙监控间隔（秒），默认65秒
    weibo_monitor_interval_seconds: int = 300  # 微博监控间隔（秒），默认300秒（5分钟）
    cleanup_logs_hour: int = 2  # 日志清理时间（小时），默认2点
    cleanup_logs_minute: int = 0  # 日志清理时间（分钟），默认0分

    # 可选配置
    config_json_url: Optional[str] = None

    def get_wechat_config(self) -> WeChatConfig:
        """获取企业微信配置"""
        return WeChatConfig(
            corpid=self.wechat_corpid,
            secret=self.wechat_secret,
            agentid=self.wechat_agentid,
            touser=self.wechat_touser,
            pushplus=self.wechat_pushplus,
            email=self.wechat_email,
        )

    def get_weibo_config(self) -> WeiboConfig:
        """获取微博配置"""
        uids = [uid.strip() for uid in self.weibo_uids.split(",") if uid.strip()]
        return WeiboConfig(
            cookie=self.weibo_cookie,
            uids=uids,
            concurrency=self.weibo_concurrency,
        )

    def get_huya_config(self) -> HuyaConfig:
        """获取虎牙配置"""
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
        with open(yml_file, "r", encoding="utf-8") as f:
            yml_config = yaml.safe_load(f)
        
        if not yml_config:
            raise ValueError(f"配置文件 {yml_path} 为空")
        
        # 将嵌套的YAML配置转换为扁平化格式
        # 企业微信配置
        if "wechat" in yml_config:
            wechat = yml_config["wechat"]
            if "corpid" in wechat:
                config_dict["wechat_corpid"] = str(wechat["corpid"])
            if "secret" in wechat:
                config_dict["wechat_secret"] = str(wechat["secret"])
            if "agentid" in wechat:
                # agentid在YAML中可能是数字，需要转换为字符串
                config_dict["wechat_agentid"] = str(wechat["agentid"])
            if "touser" in wechat:
                config_dict["wechat_touser"] = str(wechat["touser"])
            if "pushplus" in wechat and wechat["pushplus"]:
                config_dict["wechat_pushplus"] = str(wechat["pushplus"])
            if "email" in wechat and wechat["email"]:
                config_dict["wechat_email"] = str(wechat["email"])
        
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
                config_dict["huya_monitor_interval_seconds"] = scheduler["huya_monitor_interval_seconds"]
            if "weibo_monitor_interval_seconds" in scheduler:
                config_dict["weibo_monitor_interval_seconds"] = scheduler["weibo_monitor_interval_seconds"]
            if "cleanup_logs_hour" in scheduler:
                config_dict["cleanup_logs_hour"] = scheduler["cleanup_logs_hour"]
            if "cleanup_logs_minute" in scheduler:
                config_dict["cleanup_logs_minute"] = scheduler["cleanup_logs_minute"]
        
        # 可选配置
        if "optional" in yml_config:
            optional = yml_config["optional"]
            if "config_json_url" in optional and optional["config_json_url"]:
                config_dict["config_json_url"] = optional["config_json_url"]
        
        logger.debug(f"成功从 {yml_path} 加载配置")
        return config_dict
    
    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValueError(f"加载配置文件 {yml_path} 失败: {e}") from e


async def load_config_from_url(url: str) -> Optional[dict]:
    """从远程URL异步加载配置"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                return await response.json()
    except Exception as e:
        print(f"从远程URL加载配置失败: {e}")
        return None


# 全局配置缓存，用于热重载时检测变化
_config_cache: Optional[AppConfig] = None


def get_config(reload: bool = False) -> AppConfig:
    """
    从config.yml文件获取配置
    
    Args:
        reload: 是否重新加载配置文件（用于热重载）
               如果为True，会强制重新读取config.yml文件
    
    Returns:
        AppConfig实例
    """
    global _config_cache
    
    # 记录原始值（如果存在，用于检测变化）
    old_weibo_cookie = None
    old_huya_cookie = None
    if _config_cache is not None:
        old_weibo_cookie = _config_cache.weibo_cookie
        old_huya_cookie = _config_cache.huya_cookie
    
    # 如果不需要重载且已有缓存，直接返回缓存
    if not reload and _config_cache is not None:
        return _config_cache
    
    # 从YAML文件加载配置
    if reload:
        logger.debug("开始重新加载配置文件...")
    else:
        logger.debug("加载配置文件...")
    
    yml_config = load_config_from_yml()
    
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

