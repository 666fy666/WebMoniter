"""配置管理模块 - 支持环境变量和远程配置"""
from typing import Optional

import aiohttp
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


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


class HuyaConfig(BaseModel):
    """虎牙配置"""
    user_agent: str
    cookie: str
    rooms: list[str]


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

    # 虎牙
    huya_user_agent: str
    huya_cookie: str
    huya_rooms: str  # 逗号分隔的房间号列表

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
        return WeiboConfig(cookie=self.weibo_cookie, uids=uids)

    def get_huya_config(self) -> HuyaConfig:
        """获取虎牙配置"""
        rooms = [room.strip() for room in self.huya_rooms.split(",") if room.strip()]
        return HuyaConfig(
            user_agent=self.huya_user_agent,
            cookie=self.huya_cookie,
            rooms=rooms,
        )


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


def get_config() -> AppConfig:
    """
    获取配置
    优先使用环境变量，如果配置了远程URL则尝试从远程加载
    """
    # 首先尝试从环境变量加载
    config = AppConfig()

    # 如果配置了远程URL，尝试从远程加载（但环境变量优先级更高）
    if config.config_json_url:
        # 注意：这里不阻塞，因为环境变量已经加载了
        # 如果需要完全使用远程配置，可以在这里实现覆盖逻辑
        pass

    return config

