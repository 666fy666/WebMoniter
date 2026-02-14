"""配置文件监控模块 - 支持配置文件热重载"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

import yaml

from src.config import AppConfig, get_config

logger = logging.getLogger(__name__)


def _read_yaml_sync(config_path: Path) -> dict:
    """同步读取 YAML 文件（供 asyncio.to_thread 调用）"""
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


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
        self._last_mtime: float = 0
        self._last_config: AppConfig | None = None
        self._last_ai_assistant: dict = {}
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
                self._last_config = await asyncio.to_thread(get_config, True)
                raw = await asyncio.to_thread(_read_yaml_sync, self.config_path)
                self._last_ai_assistant = raw.get("ai_assistant") or {}
                logger.debug("配置监控器已启动: %s", self.config_path)
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
        logger.debug("配置监控器已停止")

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
                        # 重新加载配置（在线程池执行避免阻塞事件循环）
                        new_config = await asyncio.to_thread(get_config, True)
                        # 读取 ai_assistant 节点（独立于 AppConfig）
                        raw = await asyncio.to_thread(_read_yaml_sync, self.config_path)
                        current_ai = raw.get("ai_assistant") or {}

                        # 检查配置是否真的发生了变化（避免因文件保存但内容未变而触发）
                        config_changed = self._config_changed(self._last_config, new_config)
                        ai_changed = current_ai != self._last_ai_assistant
                        if config_changed or ai_changed:
                            # 保存旧配置的引用（在更新之前）
                            old_config = self._last_config
                            self._last_mtime = current_mtime
                            self._last_config = new_config
                            self._last_ai_assistant = current_ai

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

        # 定义需要比较的配置字段组（含监控 enable、任务 enable/time，用于触发调度器热更新）
        config_groups = {
            "weibo": ["weibo_enable", "weibo_cookie", "weibo_uids", "weibo_concurrency"],
            "huya": ["huya_enable", "huya_rooms", "huya_concurrency"],
            "bilibili": ["bilibili_enable", "bilibili_uids", "bilibili_concurrency"],
            "douyin": ["douyin_enable", "douyin_douyin_ids", "douyin_concurrency"],
            "douyu": ["douyu_enable", "douyu_rooms", "douyu_concurrency"],
            "xhs": ["xhs_enable", "xhs_profile_ids", "xhs_concurrency"],
            "checkin": [
                "checkin_enable",
                "checkin_email",
                "checkin_password",
                "checkin_time",
            ],
            "tieba": ["tieba_enable", "tieba_cookie", "tieba_time"],
            "weibo_chaohua": ["weibo_chaohua_enable", "weibo_chaohua_cookie", "weibo_chaohua_time"],
            "rainyun": [
                "rainyun_enable",
                "rainyun_time",
                "rainyun_auto_renew",
                "rainyun_renew_threshold_days",
                "rainyun_renew_product_ids",
            ],
            "enshan": ["enshan_enable", "enshan_time"],
            "tyyun": ["tyyun_enable", "tyyun_time"],
            "aliyun": ["aliyun_enable", "aliyun_time"],
            "smzdm": ["smzdm_enable", "smzdm_time"],
            "zdm_draw": ["zdm_draw_enable", "zdm_draw_time"],
            "fg": ["fg_enable", "fg_time"],
            "miui": ["miui_enable", "miui_time"],
            "iqiyi": ["iqiyi_enable", "iqiyi_time"],
            "lenovo": ["lenovo_enable", "lenovo_time"],
            "lbly": ["lbly_enable", "lbly_time"],
            "pinzan": ["pinzan_enable", "pinzan_time"],
            "dml": ["dml_enable", "dml_time"],
            "xiaomao": ["xiaomao_enable", "xiaomao_time"],
            "ydwx": ["ydwx_enable", "ydwx_time"],
            "xingkong": ["xingkong_enable", "xingkong_time"],
            "freenom": ["freenom_enable", "freenom_time"],
            "weather": ["weather_enable", "weather_time"],
            "qtw": ["qtw_enable", "qtw_time"],
            "kuake": ["kuake_enable", "kuake_time"],
            "kjwj": ["kjwj_enable", "kjwj_time"],
            "fr": ["fr_enable", "fr_time"],
            "nine_nine_nine": ["nine_nine_nine_enable", "nine_nine_nine_time"],
            "zgfc": ["zgfc_enable", "zgfc_time"],
            "ssq_500w": ["ssq_500w_enable", "ssq_500w_time"],
            "scheduler": [
                "huya_monitor_interval_seconds",
                "weibo_monitor_interval_seconds",
                "bilibili_monitor_interval_seconds",
                "douyin_monitor_interval_seconds",
                "douyu_monitor_interval_seconds",
                "xhs_monitor_interval_seconds",
            ],
            "log_cleanup": [
                "log_cleanup_enable",
                "log_cleanup_time",
                "retention_days",
            ],
            "quiet_hours": ["quiet_hours_enable", "quiet_hours_start", "quiet_hours_end"],
        }

        # 通用字段比较
        for group_name, fields in config_groups.items():
            for field in fields:
                old_value = getattr(old_config, field, None)
                new_value = getattr(new_config, field, None)
                if old_value != new_value:
                    return True

        # 特殊处理：多账号和多Cookie配置
        special_fields = {
            "checkin_accounts": (old_config, new_config),
            "tieba_cookies": (old_config, new_config),
            "weibo_chaohua_cookies": (old_config, new_config),
        }

        for field_name, (old_cfg, new_cfg) in special_fields.items():
            old_value = getattr(old_cfg, field_name, [])
            new_value = getattr(new_cfg, field_name, [])
            if old_value != new_value:
                return True

        # 插件配置
        if old_config.plugins != new_config.plugins:
            return True

        # 推送通道配置（比较列表内容）
        old_channels = old_config.push_channel_list
        new_channels = new_config.push_channel_list
        if len(old_channels) != len(new_channels):
            return True

        # 比较每个通道的配置（转换为字符串比较，简单但有效）
        old_channels_str = str(sorted(old_channels, key=lambda x: x.get("name", "")))
        new_channels_str = str(sorted(new_channels, key=lambda x: x.get("name", "")))
        if old_channels_str != new_channels_str:
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
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.on_config_changed, old_config, new_config)
