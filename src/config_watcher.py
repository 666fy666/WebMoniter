"""配置文件监控模块 - 支持配置文件热重载"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from src.config import AppConfig, get_config

logger = logging.getLogger(__name__)


class ConfigWatcher:
    """配置文件监控器 - 检测配置文件变化并触发回调"""

    def __init__(
        self,
        config_path: str = "config.yml",
        check_interval: int = 5,
        on_config_changed: Callable[[AppConfig, AppConfig], Awaitable[None] | None] | None = None,
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
        self._last_mtime: float = 0
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
            self._last_mtime = self.config_path.stat().st_mtime
            try:
                self._last_config = get_config(reload=True)
                logger.info(f"配置监控器已启动，监控文件: {self.config_path}")
            except Exception as e:
                logger.error(f"初始化配置监控器失败: {e}")

        self._running = True
        self._task = asyncio.create_task(self._watch_loop())

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
                logger.error(f"停止配置监控器时出错: {e}", exc_info=True)
        logger.info("配置监控器已停止")

    async def _watch_loop(self):
        """监控循环"""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)

                if not self.config_path.exists():
                    logger.warning(f"配置文件不存在: {self.config_path}")
                    continue

                current_mtime = self.config_path.stat().st_mtime

                # 检查文件是否被修改
                if current_mtime > self._last_mtime:
                    try:
                        # 重新加载配置
                        new_config = get_config(reload=True)

                        # 检查配置是否真的发生了变化（避免因文件保存但内容未变而触发）
                        if self._config_changed(self._last_config, new_config):
                            # 保存旧配置的引用（在更新之前）
                            old_config = self._last_config
                            self._last_mtime = current_mtime
                            self._last_config = new_config

                            # 调用回调函数
                            if self.on_config_changed:
                                try:
                                    await self._call_callback(old_config, new_config)
                                except Exception as e:
                                    logger.error(f"执行配置变化回调失败: {e}", exc_info=True)
                        else:
                            logger.debug("配置文件已修改但内容未变化，跳过重载")
                            self._last_mtime = current_mtime

                    except Exception as e:
                        logger.error(f"重新加载配置失败: {e}", exc_info=True)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"配置监控循环出错: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)

    def _config_changed(self, old_config: AppConfig | None, new_config: AppConfig) -> bool:
        """
        检查配置是否真的发生了变化

        Args:
            old_config: 旧配置
            new_config: 新配置

        Returns:
            如果配置发生变化返回 True，否则返回 False
        """
        if old_config is None:
            return True

        # 检查关键配置项是否变化
        # 微博配置
        if (
            old_config.weibo_cookie != new_config.weibo_cookie
            or old_config.weibo_uids != new_config.weibo_uids
            or old_config.weibo_concurrency != new_config.weibo_concurrency
        ):
            return True

        # 虎牙配置
        if (
            old_config.huya_rooms != new_config.huya_rooms
            or old_config.huya_concurrency != new_config.huya_concurrency
        ):
            return True

        # 调度器配置
        if (
            old_config.huya_monitor_interval_seconds != new_config.huya_monitor_interval_seconds
            or old_config.weibo_monitor_interval_seconds
            != new_config.weibo_monitor_interval_seconds
            or old_config.cleanup_logs_hour != new_config.cleanup_logs_hour
            or old_config.cleanup_logs_minute != new_config.cleanup_logs_minute
        ):
            return True

        # 推送通道配置（简单比较列表长度和内容）
        old_channels = old_config.push_channel_list
        new_channels = new_config.push_channel_list
        if len(old_channels) != len(new_channels):
            return True

        # 比较每个通道的配置（转换为字符串比较，简单但有效）
        old_channels_str = str(sorted(old_channels, key=lambda x: x.get("name", "")))
        new_channels_str = str(sorted(new_channels, key=lambda x: x.get("name", "")))
        if old_channels_str != new_channels_str:
            return True

        # 免打扰时段配置
        if (
            old_config.quiet_hours_enable != new_config.quiet_hours_enable
            or old_config.quiet_hours_start != new_config.quiet_hours_start
            or old_config.quiet_hours_end != new_config.quiet_hours_end
        ):
            return True

        return False

    async def _call_callback(self, old_config: AppConfig | None, new_config: AppConfig):
        """调用回调函数（支持同步和异步回调）"""
        if self.on_config_changed is None:
            return

        # 检查回调函数是否是协程函数
        if asyncio.iscoroutinefunction(self.on_config_changed):
            await self.on_config_changed(old_config, new_config)
        else:
            # 同步函数，在线程池中执行
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.on_config_changed, old_config, new_config)
