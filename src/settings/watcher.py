"""配置文件监控模块 - 支持配置文件热重载"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from src.settings.config import AppConfig, get_config

logger = logging.getLogger(__name__)


class ConfigWatcher:
    """配置文件监控器 - 检测配置文件变化并触发回调"""

    def __init__(
        self,
        config_path: str = "config.yml",
        check_interval: int = 5,
        on_config_changed: (
            Callable[[AppConfig | None, AppConfig], Awaitable[None] | None] | None
        ) = None,
    ):
        """
        初始化配置监控器

        Args:
            config_path: 配置文件路径
            check_interval: 检查间隔（秒），默认5秒
            on_config_changed: 配置变化时的回调函数，接收旧配置和新配置作为参数
        """
        self.config_path = Path(config_path)
        self.check_interval = check_interval
        self.on_config_changed = on_config_changed
        self._last_fingerprint: tuple[int, ...] | None = None
        self._retry_pending = False
        self._last_config: AppConfig | None = None
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """启动配置监控"""
        if self._running:
            logger.warning("配置监控器已在运行")
            return

        # 初始化：记录当前配置文件的修改时间和配置内容
        if self.config_path.exists():
            fingerprint = self._fingerprint()
            try:
                self._last_config = await asyncio.to_thread(get_config, True)
                self._last_fingerprint = fingerprint
                logger.debug("配置监控器已启动: %s", self.config_path)
            except Exception as e:
                logger.error("初始化配置监控器失败: %s", e)

        self._running = True
        try:
            self._task = asyncio.create_task(self._watch_loop())
        except Exception:
            self._running = False
            self._task = None
            raise

    async def stop(self):
        """停止配置监控"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error("停止配置监控器时出错: %s", e, exc_info=True)
        logger.debug("配置监控器已停止")

    async def _watch_loop(self):
        """监控循环"""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)

                if not self.config_path.exists():
                    logger.warning("配置文件不存在: %s", self.config_path)
                    continue

                fingerprint = self._fingerprint()
                if fingerprint != self._last_fingerprint or self._retry_pending:
                    try:
                        new_config = await asyncio.to_thread(get_config, True)
                        if self._retry_pending or self._config_changed(
                            self._last_config, new_config
                        ):
                            self._retry_pending = True
                            await self._call_callback(self._last_config, new_config)
                        # Only acknowledge fully applied settings; failed callbacks retry next poll.
                        self._last_config = new_config
                        self._last_fingerprint = fingerprint
                        self._retry_pending = False
                    except Exception as e:
                        logger.error("配置加载或应用失败，下次轮询重试: %s", type(e).__name__)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("配置监控循环出错: %s", e, exc_info=True)
                await asyncio.sleep(self.check_interval)

    def _fingerprint(self) -> tuple[int, ...]:
        stat = self.config_path.stat()
        return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)

    def _config_changed(self, old_config: AppConfig | None, new_config: AppConfig) -> bool:
        """
        检查配置是否真的发生了变化。
        利用 Pydantic model_dump() 做完整比较，新增字段时无需手动维护字段列表。
        """
        if old_config is None:
            return True
        return old_config.model_dump() != new_config.model_dump()

    async def _call_callback(self, old_config: AppConfig | None, new_config: AppConfig):
        """调用回调函数（支持同步和异步回调）"""
        if self.on_config_changed is None:
            return

        # 检查回调函数是否是协程函数
        if asyncio.iscoroutinefunction(self.on_config_changed):
            await self.on_config_changed(old_config, new_config)
        else:
            # 同步函数，在线程池中执行
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.on_config_changed, old_config, new_config)
