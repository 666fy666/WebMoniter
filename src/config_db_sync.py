"""配置与数据库同步模块 - 确保配置文件中的 uid/room 与数据库记录一致

当从配置文件中删除 uid 或 room 时，同步删除数据库中对应的记录。
"""

import logging
from typing import Callable

from src.config import AppConfig
from src.database import AsyncDatabase

logger = logging.getLogger(__name__)


def _parse_ids(value: str) -> set[str]:
    """解析逗号分隔的 ID 列表，返回去重后的集合"""
    if not value or not isinstance(value, str):
        return set()
    return {i.strip() for i in value.split(",") if i.strip()}


async def sync_config_to_db(old_config: AppConfig | None, new_config: AppConfig) -> None:
    """
    根据配置变化同步数据库：删除配置中已移除的 uid/room 对应的数据库记录。

    Args:
        old_config: 旧配置（首次启动时为 None，此时不执行删除）
        new_config: 新配置
    """
    if old_config is None:
        return

    # 定义各监控平台：((旧配置获取函数, 新配置获取函数), (表名, 主键列名))
    # 对于多表的情况（如 bilibili），使用列表
    sync_rules: list[tuple[tuple[Callable[[AppConfig], set[str]], Callable[[AppConfig], set[str]]], list[tuple[str, str]]]] = [
        # 微博: weibo_uids -> weibo.UID
        (
            (lambda c: _parse_ids(getattr(c, "weibo_uids", "") or ""), lambda c: _parse_ids(getattr(c, "weibo_uids", "") or "")),
            [("weibo", "UID")],
        ),
        # 虎牙: huya_rooms -> huya.room
        (
            (lambda c: _parse_ids(getattr(c, "huya_rooms", "") or ""), lambda c: _parse_ids(getattr(c, "huya_rooms", "") or "")),
            [("huya", "room")],
        ),
        # 哔哩哔哩: bilibili_uids -> bilibili_dynamic.uid, bilibili_live.uid
        (
            (lambda c: _parse_ids(getattr(c, "bilibili_uids", "") or ""), lambda c: _parse_ids(getattr(c, "bilibili_uids", "") or "")),
            [("bilibili_dynamic", "uid"), ("bilibili_live", "uid")],
        ),
        # 抖音: douyin_douyin_ids -> douyin.douyin_id
        (
            (lambda c: _parse_ids(getattr(c, "douyin_douyin_ids", "") or ""), lambda c: _parse_ids(getattr(c, "douyin_douyin_ids", "") or "")),
            [("douyin", "douyin_id")],
        ),
        # 斗鱼: douyu_rooms -> douyu.room
        (
            (lambda c: _parse_ids(getattr(c, "douyu_rooms", "") or ""), lambda c: _parse_ids(getattr(c, "douyu_rooms", "") or "")),
            [("douyu", "room")],
        ),
        # 小红书: xhs_profile_ids -> xhs.profile_id
        (
            (lambda c: _parse_ids(getattr(c, "xhs_profile_ids", "") or ""), lambda c: _parse_ids(getattr(c, "xhs_profile_ids", "") or "")),
            [("xhs", "profile_id")],
        ),
    ]

    async with AsyncDatabase() as db:
        for (get_old_ids, get_new_ids), tables in sync_rules:
            old_ids = get_old_ids(old_config)
            new_ids = get_new_ids(new_config)
            removed_ids = old_ids - new_ids

            if not removed_ids:
                continue

            for table_name, pk_column in tables:
                for uid in removed_ids:
                    try:
                        # 使用参数化查询避免 SQL 注入（表名和列名来自代码常量，非用户输入）
                        sql = f"DELETE FROM {table_name} WHERE {pk_column}=%(pk)s"
                        ok = await db.execute_update(sql, {"pk": uid})
                        if ok:
                            logger.info(
                                "配置同步: 已从 %s 表删除 %s=%s（已从配置中移除）",
                                table_name,
                                pk_column,
                                uid,
                            )
                    except Exception as e:
                        logger.error(
                            "配置同步: 删除 %s 表中 %s=%s 失败: %s",
                            table_name,
                            pk_column,
                            uid,
                            e,
                        )
