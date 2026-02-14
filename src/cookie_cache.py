"""Cookie缓存管理模块 - 管理各平台Cookie的过期状态"""

import asyncio
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _data_dir_path() -> Path:
    """data 目录路径；打包为 exe 时以可执行文件所在目录为基准。"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "data"


class CookieCache:
    """Cookie缓存管理器"""

    def __init__(self, cache_file: str | None = None):
        """
        初始化Cookie缓存管理器

        Args:
            cache_file: 缓存文件路径，如果为 None 则使用 data/cookie_cache.json（目录不存在则自动创建）
        """
        if cache_file is None:
            _data_dir = _data_dir_path()
            _data_dir.mkdir(parents=True, exist_ok=True)
            self.cache_file = _data_dir / "cookie_cache.json"
        else:
            self.cache_file = Path(cache_file)
        # 缓存结构: {platform: {"valid": bool, "notified": bool}}
        self._cache: dict[str, dict] = {}
        # 异步锁保护文件操作
        self._lock = asyncio.Lock()
        self._load_cache()

    def _load_cache(self):
        """从文件加载缓存"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                    # 兼容旧格式（只有bool值）和新格式（dict）
                    self._cache = {}
                    for platform, value in data.items():
                        if isinstance(value, dict):
                            self._cache[platform] = value
                        else:
                            # 旧格式：只有bool值，转换为新格式
                            self._cache[platform] = {"valid": value, "notified": False}
                logger.debug("已加载Cookie缓存: %s", self._cache)
            else:
                # 文件不存在，初始化为空字典并创建文件
                self._cache = {}
                self._save_cache()  # 创建空缓存文件
                logger.info("Cookie缓存文件不存在，已创建新文件")
        except Exception as e:
            logger.error(f"加载Cookie缓存失败: {e}")
            self._cache = {}
            # 即使加载失败，也尝试创建文件
            try:
                self._save_cache()
            except Exception:
                pass

    def _save_cache(self):
        """保存缓存到文件（同步方法，内部使用）"""
        try:
            # 确保目录存在
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            logger.debug(f"已保存Cookie缓存: {self._cache}")
        except Exception as e:
            logger.error(f"保存Cookie缓存失败: {e}")

    async def _save_cache_async(self):
        """异步保存缓存到文件（带锁保护）"""
        async with self._lock:
            self._save_cache()

    def is_valid(self, platform: str) -> bool:
        """
        检查指定平台的Cookie是否有效

        Args:
            platform: 平台名称，如 "weibo", "huya"

        Returns:
            True表示有效，False表示已过期
            如果平台不存在于缓存中，默认返回True（项目启动时默认有效）
        """
        # 如果平台不在缓存中，默认返回True（项目启动时默认有效）
        if platform not in self._cache:
            return True
        platform_data = self._cache[platform]
        if isinstance(platform_data, dict):
            return platform_data.get("valid", True)
        # 兼容旧格式
        return platform_data

    async def mark_expired(self, platform: str):
        """
        标记指定平台的Cookie为已过期（异步方法，带锁保护）

        Args:
            platform: 平台名称，如 "weibo", "huya"
        """
        async with self._lock:
            if platform not in self._cache or self._cache[platform].get("valid", True) is not False:
                if platform not in self._cache:
                    self._cache[platform] = {"valid": False, "notified": False}
                else:
                    self._cache[platform]["valid"] = False
                self._save_cache()
                logger.warning(f"已标记 {platform} Cookie为过期状态")

    async def mark_valid(self, platform: str):
        """
        标记指定平台的Cookie为有效（异步方法，带锁保护）

        Args:
            platform: 平台名称，如 "weibo", "huya"
        """
        async with self._lock:
            if platform not in self._cache or self._cache[platform].get("valid", False) is not True:
                if platform not in self._cache:
                    self._cache[platform] = {"valid": True, "notified": False}
                else:
                    self._cache[platform]["valid"] = True
                    # Cookie恢复有效时，重置提醒标记，以便下次过期时能再次提醒
                    self._cache[platform]["notified"] = False
                self._save_cache()
                logger.debug("已标记 %s Cookie为有效状态", platform)

    async def reset_all(self):
        """重置所有Cookie状态为有效（项目启动时调用，异步方法，带锁保护）"""
        async with self._lock:
            updated = False
            for platform in self._cache:
                platform_data = self._cache[platform]
                if isinstance(platform_data, dict):
                    if platform_data.get("valid", True) is False:
                        platform_data["valid"] = True
                        platform_data["notified"] = False  # 重置提醒标记
                        updated = True
                else:
                    # 兼容旧格式
                    if platform_data is False:
                        self._cache[platform] = {"valid": True, "notified": False}
                        updated = True
            # 即使没有更新，也保存一次以确保文件存在
            self._save_cache()
            if updated:
                logger.debug("已重置所有Cookie状态为有效")
            else:
                logger.debug("Cookie缓存文件已更新")

    def get_all_status(self) -> dict[str, bool]:
        """获取所有平台的Cookie状态"""
        result = {}
        for platform, data in self._cache.items():
            if isinstance(data, dict):
                result[platform] = data.get("valid", True)
            else:
                result[platform] = data
        return result

    def is_notified(self, platform: str) -> bool:
        """
        检查指定平台的Cookie过期提醒是否已发送

        Args:
            platform: 平台名称，如 "weibo", "huya"

        Returns:
            True表示已发送提醒，False表示未发送
        """
        if platform not in self._cache:
            return False
        platform_data = self._cache[platform]
        if isinstance(platform_data, dict):
            return platform_data.get("notified", False)
        return False

    async def mark_notified(self, platform: str):
        """
        标记指定平台的Cookie过期提醒已发送（异步方法，带锁保护）

        Args:
            platform: 平台名称，如 "weibo", "huya"
        """
        async with self._lock:
            if platform not in self._cache:
                self._cache[platform] = {"valid": False, "notified": True}
            else:
                if not isinstance(self._cache[platform], dict):
                    # 兼容旧格式
                    self._cache[platform] = {"valid": self._cache[platform], "notified": True}
                else:
                    self._cache[platform]["notified"] = True
            self._save_cache()
            logger.debug(f"已标记 {platform} Cookie过期提醒已发送")


# 全局Cookie缓存实例（延迟初始化）
cookie_cache: CookieCache | None = None


def get_cookie_cache() -> CookieCache:
    """获取全局Cookie缓存实例（单例模式）"""
    global cookie_cache
    if cookie_cache is None:
        cookie_cache = CookieCache()
    return cookie_cache
