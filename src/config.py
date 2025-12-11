"""配置管理模块 - 支持环境变量、YAML配置和远程配置"""
import logging
import os
from pathlib import Path
from typing import Optional

import aiohttp
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# 获取logger
logger = logging.getLogger(__name__)


class DatabaseConfig(BaseModel):
    """数据库配置"""
    host: str
    port: int = 3306
    user: str
    password: str
    db: str


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


class AppConfig(BaseSettings):
    """应用配置"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 企业微信
    wechat_corpid: str
    wechat_secret: str
    wechat_agentid: str
    wechat_touser: str
    wechat_pushplus: Optional[str] = None
    wechat_email: Optional[str] = None

    # 数据库
    db_host: str
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str

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

    def get_database_config(self) -> DatabaseConfig:
        """获取数据库配置"""
        return DatabaseConfig(
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_password,
            db=self.db_name,
        )

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
    从YAML文件加载配置并转换为环境变量格式
    
    Args:
        yml_path: YAML配置文件路径，默认为 config.yml
    
    Returns:
        配置字典（扁平化的环境变量格式）
    """
    config_dict = {}
    yml_file = Path(yml_path)
    
    if not yml_file.exists():
        logger.debug(f"YAML配置文件 {yml_path} 不存在，跳过")
        return config_dict
    
    try:
        with open(yml_file, "r", encoding="utf-8") as f:
            yml_config = yaml.safe_load(f)
        
        if not yml_config:
            logger.debug(f"YAML配置文件 {yml_path} 为空")
            return config_dict
        
        # 将嵌套的YAML配置转换为扁平化的环境变量格式
        # 企业微信配置
        if "wechat" in yml_config:
            wechat = yml_config["wechat"]
            if "corpid" in wechat:
                config_dict["wechat_corpid"] = wechat["corpid"]
            if "secret" in wechat:
                config_dict["wechat_secret"] = wechat["secret"]
            if "agentid" in wechat:
                config_dict["wechat_agentid"] = wechat["agentid"]
            if "touser" in wechat:
                config_dict["wechat_touser"] = wechat["touser"]
            if "pushplus" in wechat and wechat["pushplus"]:
                config_dict["wechat_pushplus"] = wechat["pushplus"]
            if "email" in wechat and wechat["email"]:
                config_dict["wechat_email"] = wechat["email"]
        
        # 数据库配置
        if "database" in yml_config:
            db = yml_config["database"]
            if "host" in db:
                config_dict["db_host"] = db["host"]
            if "port" in db:
                config_dict["db_port"] = str(db["port"])
            if "user" in db:
                config_dict["db_user"] = db["user"]
            if "password" in db:
                config_dict["db_password"] = db["password"]
            if "name" in db:
                config_dict["db_name"] = db["name"]
        
        # 微博配置
        if "weibo" in yml_config:
            weibo = yml_config["weibo"]
            if "cookie" in weibo:
                config_dict["weibo_cookie"] = weibo["cookie"]
            if "uids" in weibo:
                config_dict["weibo_uids"] = weibo["uids"]
            if "concurrency" in weibo:
                config_dict["weibo_concurrency"] = str(weibo["concurrency"])
        
        # 虎牙配置
        if "huya" in yml_config:
            huya = yml_config["huya"]
            if "user_agent" in huya:
                config_dict["huya_user_agent"] = huya["user_agent"]
            if "cookie" in huya:
                config_dict["huya_cookie"] = huya["cookie"]
            if "rooms" in huya:
                config_dict["huya_rooms"] = huya["rooms"]
            if "concurrency" in huya:
                config_dict["huya_concurrency"] = str(huya["concurrency"])
        
        # 调度器配置
        if "scheduler" in yml_config:
            scheduler = yml_config["scheduler"]
            if "huya_monitor_interval_seconds" in scheduler:
                config_dict["huya_monitor_interval_seconds"] = str(scheduler["huya_monitor_interval_seconds"])
            if "weibo_monitor_interval_seconds" in scheduler:
                config_dict["weibo_monitor_interval_seconds"] = str(scheduler["weibo_monitor_interval_seconds"])
            if "cleanup_logs_hour" in scheduler:
                config_dict["cleanup_logs_hour"] = str(scheduler["cleanup_logs_hour"])
            if "cleanup_logs_minute" in scheduler:
                config_dict["cleanup_logs_minute"] = str(scheduler["cleanup_logs_minute"])
        
        # 可选配置
        if "optional" in yml_config:
            optional = yml_config["optional"]
            if "config_json_url" in optional and optional["config_json_url"]:
                config_dict["config_json_url"] = optional["config_json_url"]
        
        logger.debug(f"成功从 {yml_path} 加载配置")
        return config_dict
    
    except Exception as e:
        logger.warning(f"加载YAML配置文件 {yml_path} 失败: {e}")
        return config_dict


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


def get_config(reload: bool = False) -> AppConfig:
    """
    获取配置
    配置优先级：环境变量(.env) > config.yml
    如果环境变量中存在相同的配置项，将优先使用环境变量的值
    
    Args:
        reload: 是否重新加载配置文件（用于热重载）
               如果为True，会强制重新读取.env和config.yml文件并覆盖现有环境变量
    
    Returns:
        AppConfig实例
    """
    # 记录原始值（如果存在，用于检测变化）
    old_weibo_cookie = os.environ.get("weibo_cookie")
    old_huya_cookie = os.environ.get("huya_cookie")
    
    # 1. 首先加载.env文件（优先级较高）
    if reload:
        logger.debug("开始重新加载配置文件...")
        logger.debug("重新加载.env文件...")
        # override=True 会覆盖已存在的环境变量，确保使用最新的值
        load_dotenv(override=True)
    else:
        logger.debug("加载.env文件（首次加载）")
        load_dotenv()
    
    # 2. 然后从YAML文件加载配置（优先级较低）
    # 只有当环境变量中不存在该配置项时，才使用YAML中的值
    yml_config = load_config_from_yml()
    for key, value in yml_config.items():
        # 如果环境变量中不存在该配置项，则使用YAML中的值
        if key not in os.environ:
            os.environ[key] = value
            logger.debug(f"从YAML加载配置: {key}")
    
    # 记录新值
    new_weibo_cookie = os.environ.get("weibo_cookie")
    new_huya_cookie = os.environ.get("huya_cookie")
    
    logger.debug("配置加载完成")
    # 只在Cookie真正变化时才记录INFO级别的日志
    if old_weibo_cookie != new_weibo_cookie:
        logger.info(f"微博Cookie已更新 (长度: {len(new_weibo_cookie or '')} 字符)")
    else:
        logger.debug("微博Cookie未变更")
        
    if old_huya_cookie != new_huya_cookie:
        logger.info(f"虎牙Cookie已更新 (长度: {len(new_huya_cookie or '')} 字符)")
    else:
        logger.debug("虎牙Cookie未变更")
    
    # 创建新实例，pydantic-settings会从环境变量读取配置
    config = AppConfig()

    # 如果配置了远程URL，尝试从远程加载（但环境变量优先级更高）
    if config.config_json_url:
        # 注意：这里不阻塞，因为环境变量已经加载了
        # 如果需要完全使用远程配置，可以在这里实现覆盖逻辑
        pass

    return config

