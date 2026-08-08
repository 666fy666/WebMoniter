"""MySQL 连接池、表结构与同步原语。"""

from __future__ import annotations

import asyncio
import re
import warnings
from dataclasses import dataclass
from typing import Any

import aiomysql


@dataclass(frozen=True)
class TableSpec:
    name: str
    primary_key: str
    columns: tuple[str, ...]
    mysql_ddl: str


TABLE_SPECS: dict[str, TableSpec] = {
    "weibo": TableSpec(
        "weibo",
        "UID",
        (
            "UID",
            "用户名",
            "认证信息",
            "简介",
            "粉丝数",
            "微博数",
            "文本",
            "mid",
            "图片",
            "转发微博",
            "正文结构",
            "标签",
            "内容类型",
            "视频封面",
        ),
        """
        CREATE TABLE IF NOT EXISTS `weibo` (
            `UID` VARCHAR(255) COLLATE utf8mb4_bin PRIMARY KEY,
            `用户名` LONGTEXT NOT NULL,
            `认证信息` LONGTEXT,
            `简介` LONGTEXT,
            `粉丝数` LONGTEXT,
            `微博数` LONGTEXT,
            `文本` LONGTEXT,
            `mid` LONGTEXT,
            `图片` LONGTEXT,
            `转发微博` LONGTEXT,
            `正文结构` LONGTEXT,
            `标签` LONGTEXT,
            `内容类型` LONGTEXT,
            `视频封面` LONGTEXT
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """,
    ),
    "huya": TableSpec(
        "huya",
        "room",
        ("room", "name", "is_live", "room_pic", "avatar_url"),
        """
        CREATE TABLE IF NOT EXISTS `huya` (
            `room` VARCHAR(255) COLLATE utf8mb4_bin PRIMARY KEY,
            `name` LONGTEXT NOT NULL,
            `is_live` LONGTEXT,
            `room_pic` LONGTEXT,
            `avatar_url` LONGTEXT
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """,
    ),
    "bilibili_dynamic": TableSpec(
        "bilibili_dynamic",
        "uid",
        ("uid", "uname", "dynamic_id", "dynamic_text"),
        """
        CREATE TABLE IF NOT EXISTS `bilibili_dynamic` (
            `uid` VARCHAR(255) COLLATE utf8mb4_bin PRIMARY KEY,
            `uname` LONGTEXT NOT NULL,
            `dynamic_id` LONGTEXT,
            `dynamic_text` LONGTEXT
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """,
    ),
    "bilibili_live": TableSpec(
        "bilibili_live",
        "uid",
        ("uid", "uname", "room_id", "is_live"),
        """
        CREATE TABLE IF NOT EXISTS `bilibili_live` (
            `uid` VARCHAR(255) COLLATE utf8mb4_bin PRIMARY KEY,
            `uname` LONGTEXT NOT NULL,
            `room_id` LONGTEXT,
            `is_live` LONGTEXT
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """,
    ),
    "douyin": TableSpec(
        "douyin",
        "douyin_id",
        ("douyin_id", "name", "is_live"),
        """
        CREATE TABLE IF NOT EXISTS `douyin` (
            `douyin_id` VARCHAR(255) COLLATE utf8mb4_bin PRIMARY KEY,
            `name` LONGTEXT NOT NULL,
            `is_live` LONGTEXT
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """,
    ),
    "douyu": TableSpec(
        "douyu",
        "room",
        ("room", "name", "is_live"),
        """
        CREATE TABLE IF NOT EXISTS `douyu` (
            `room` VARCHAR(255) COLLATE utf8mb4_bin PRIMARY KEY,
            `name` LONGTEXT NOT NULL,
            `is_live` LONGTEXT
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """,
    ),
    "xhs": TableSpec(
        "xhs",
        "profile_id",
        ("profile_id", "user_name", "latest_note_title", "note_id"),
        """
        CREATE TABLE IF NOT EXISTS `xhs` (
            `profile_id` VARCHAR(255) COLLATE utf8mb4_bin PRIMARY KEY,
            `user_name` LONGTEXT NOT NULL,
            `latest_note_title` LONGTEXT,
            `note_id` LONGTEXT
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """,
    ),
    "task_run_history": TableSpec(
        "task_run_history",
        "job_id",
        ("job_id", "last_run_date"),
        """
        CREATE TABLE IF NOT EXISTS `task_run_history` (
            `job_id` VARCHAR(255) COLLATE utf8mb4_bin PRIMARY KEY,
            `last_run_date` VARCHAR(32) NOT NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """,
    ),
}

# 这些字段曾通过 SQLite 的增量迁移加入。MySQL 的 CREATE TABLE IF NOT EXISTS
# 不会更新旧表，因此连接旧数据库时需要显式补齐，保证两种后端结构一致。
MYSQL_COLUMN_MIGRATIONS: dict[str, dict[str, str]] = {
    "weibo": {
        "图片": "LONGTEXT NULL",
        "转发微博": "LONGTEXT NULL",
        "正文结构": "LONGTEXT NULL",
        "标签": "LONGTEXT NULL",
        "内容类型": "LONGTEXT NULL",
        "视频封面": "LONGTEXT NULL",
    },
    "huya": {
        "room_pic": "LONGTEXT NULL",
        "avatar_url": "LONGTEXT NULL",
    },
    "xhs": {
        "note_id": "LONGTEXT NULL",
    },
}


@dataclass(frozen=True)
class MySQLSettings:
    enabled: bool
    host: str
    port: int
    user: str
    password: str
    database: str
    connect_timeout: int
    pool_min_size: int
    pool_max_size: int

    @classmethod
    def from_config(cls, config: Any) -> MySQLSettings:
        return cls(
            enabled=bool(getattr(config, "mysql_enabled", False)),
            host=str(getattr(config, "mysql_host", "") or "").strip(),
            port=int(getattr(config, "mysql_port", 3306)),
            user=str(getattr(config, "mysql_user", "") or "").strip(),
            password=str(getattr(config, "mysql_password", "") or ""),
            database=str(getattr(config, "mysql_database", "") or "").strip(),
            connect_timeout=int(getattr(config, "mysql_connect_timeout", 5)),
            pool_min_size=int(getattr(config, "mysql_pool_min_size", 1)),
            pool_max_size=int(getattr(config, "mysql_pool_max_size", 5)),
        )

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.host and self.user and self.database)

    @property
    def fingerprint(self) -> tuple[Any, ...]:
        return (
            self.enabled,
            self.host,
            self.port,
            self.user,
            self.password,
            self.database,
            self.connect_timeout,
            self.pool_min_size,
            self.pool_max_size,
        )


_COLON_PARAM = re.compile(r"(?<!:):([A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff]*)")
_MYSQL_NAMED_PARAM = re.compile(r"%\(([A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff]*)\)s")
_INSERT_OR_REPLACE = re.compile(r"\bINSERT\s+OR\s+REPLACE\s+INTO\b", re.IGNORECASE)
_CONNECTION_ERROR_CODES = {0, 1040, 1042, 1043, 1047, 1158, 1159, 1160, 1161, 2002, 2003, 2006, 2013}


def convert_mysql_sql(sql: str) -> str:
    """将项目兼容 SQL 转为 aiomysql 使用的 MySQL 方言。"""
    converted = _INSERT_OR_REPLACE.sub("REPLACE INTO", sql)
    return _COLON_PARAM.sub(r"%(\1)s", converted)


def select_mysql_params(sql: str, params: dict | None) -> dict | None:
    """仅保留 SQL 实际引用的参数，避免驱动转义业务字典中的附加对象。"""
    if params is None:
        return None
    names = dict.fromkeys(_MYSQL_NAMED_PARAM.findall(sql))
    return {name: params[name] for name in names}


def is_mysql_connection_error(exc: BaseException) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, ConnectionError, OSError)):
        return True
    if isinstance(exc, aiomysql.OperationalError):
        code = exc.args[0] if exc.args else 0
        return isinstance(code, int) and code in _CONNECTION_ERROR_CODES
    return False


async def create_mysql_pool(settings: MySQLSettings) -> aiomysql.Pool:
    return await aiomysql.create_pool(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        db=settings.database,
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=settings.connect_timeout,
        minsize=settings.pool_min_size,
        maxsize=settings.pool_max_size,
        pool_recycle=300,
    )


async def close_mysql_pool(pool: aiomysql.Pool | None) -> None:
    if pool is None:
        return
    pool.close()
    await pool.wait_closed()


async def initialize_mysql_schema(pool: aiomysql.Pool) -> None:
    async with pool.acquire() as conn:
        try:
            async with conn.cursor() as cursor:
                for spec in TABLE_SPECS.values():
                    with warnings.catch_warnings():
                        warnings.filterwarnings(
                            "ignore",
                            message=r"Table '.*' already exists",
                            category=Warning,
                        )
                        await cursor.execute(spec.mysql_ddl)
                await _migrate_mysql_columns(cursor)
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise


async def _migrate_mysql_columns(cursor) -> None:
    """补齐旧 MySQL 表缺少的增量字段。"""
    for table_name, columns in MYSQL_COLUMN_MIGRATIONS.items():
        await cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            """,
            (table_name,),
        )
        existing = {row[0] for row in await cursor.fetchall()}
        for column_name, column_ddl in columns.items():
            if column_name in existing:
                continue
            try:
                await cursor.execute(
                    f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {column_ddl}"
                )
            except aiomysql.OperationalError as exc:
                # 多实例可能同时完成同一迁移；重复列表示目标结构已经满足。
                if not exc.args or exc.args[0] != 1060:
                    raise


async def mysql_query(pool: aiomysql.Pool, sql: str, params: dict | None = None) -> list[tuple]:
    converted_sql = convert_mysql_sql(sql)
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(converted_sql, select_mysql_params(converted_sql, params))
            return list(await cursor.fetchall())


async def mysql_update(pool: aiomysql.Pool, sql: str, params: dict | None = None) -> None:
    converted_sql = convert_mysql_sql(sql)
    async with pool.acquire() as conn:
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(converted_sql, select_mysql_params(converted_sql, params))
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise


async def test_mysql_connection(settings: MySQLSettings) -> None:
    pool = await create_mysql_pool(settings)
    try:
        await mysql_query(pool, "SELECT 1")
    finally:
        await close_mysql_pool(pool)


def _quoted_columns(spec: TableSpec) -> str:
    return ", ".join(f"`{column}`" for column in spec.columns)


async def fetch_mysql_tables(pool: aiomysql.Pool) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            for spec in TABLE_SPECS.values():
                await cursor.execute(f"SELECT {_quoted_columns(spec)} FROM `{spec.name}`")
                rows = await cursor.fetchall()
                result[spec.name] = [dict(zip(spec.columns, row, strict=True)) for row in rows]
    return result


async def mysql_tables_empty(pool: aiomysql.Pool) -> bool:
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            for spec in TABLE_SPECS.values():
                await cursor.execute(f"SELECT 1 FROM `{spec.name}` LIMIT 1")
                if await cursor.fetchone() is not None:
                    return False
    return True


async def _upsert_row(cursor, spec: TableSpec, row: dict[str, Any]) -> None:
    columns = spec.columns
    placeholders = ", ".join(f"%({column})s" for column in columns)
    update_columns = [column for column in columns if column != spec.primary_key]
    updates = ", ".join(f"`{column}`=VALUES(`{column}`)" for column in update_columns)
    sql = (
        f"INSERT INTO `{spec.name}` ({_quoted_columns(spec)}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    await cursor.execute(sql, {column: row.get(column) for column in columns})


async def replace_mysql_tables(
    pool: aiomysql.Pool,
    tables: dict[str, list[dict[str, Any]]],
) -> None:
    async with pool.acquire() as conn:
        try:
            async with conn.cursor() as cursor:
                for spec in TABLE_SPECS.values():
                    await cursor.execute(f"DELETE FROM `{spec.name}`")
                    for row in tables.get(spec.name, []):
                        await _upsert_row(cursor, spec, row)
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise


async def replay_mysql_events(pool: aiomysql.Pool, events: list[dict[str, Any]]) -> None:
    """在单个 MySQL 事务内幂等回放 SQLite 离线日志。"""
    async with pool.acquire() as conn:
        try:
            async with conn.cursor() as cursor:
                for event in events:
                    spec = TABLE_SPECS[event["table_name"]]
                    operation = event["operation"]
                    if operation == "clear":
                        await cursor.execute(f"DELETE FROM `{spec.name}`")
                    elif operation == "delete":
                        await cursor.execute(
                            f"DELETE FROM `{spec.name}` WHERE `{spec.primary_key}`=%s",
                            (event["pk_value"],),
                        )
                    else:
                        await _upsert_row(cursor, spec, event["row_data"])
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
