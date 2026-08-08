"""异步数据库操作模块 - MySQL 主库与 SQLite 本地镜像。"""

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import date, datetime
from typing import Any

import aiosqlite

from src.core.paths import DB_PATH
from src.storage.mysql_backend import (
    TABLE_SPECS,
    MySQLSettings,
    close_mysql_pool,
    create_mysql_pool,
    fetch_mysql_tables,
    initialize_mysql_schema,
    is_mysql_connection_error,
    mysql_query,
    mysql_tables_empty,
    mysql_update,
    replace_mysql_tables,
    replay_mysql_events,
    test_mysql_connection,
)

# 全局单例数据库连接
_shared_connection: aiosqlite.Connection | None = None
_connection_lock = asyncio.Lock()
_connection_ref_count = 0
_active_shared_databases: set["AsyncDatabase"] = set()
_logger = logging.getLogger(__name__)

# MySQL/SQLite 协调状态。SQLite 连接仍沿用上面的共享连接与引用计数。
_mysql_pool = None
_mysql_settings: MySQLSettings | None = None
_active_backend = "sqlite"
_sync_state = "sqlite_only"
_last_sync_at: str | None = None
_status_message = "未启用 MySQL，正在使用 SQLite"
_sqlite_healthy = True
_mysql_reachable = False
_mirror_degraded = False
_hybrid_init_lock = asyncio.Lock()
_database_operation_lock = asyncio.Lock()
_maintenance_task: asyncio.Task | None = None
_maintenance_stop = asyncio.Event()

_WRITE_TABLE = re.compile(
    r"^\s*(?:INSERT(?:\s+OR\s+REPLACE)?\s+INTO|REPLACE\s+INTO|UPDATE|DELETE\s+FROM)\s+[`\"]?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
_CLEAR_TABLE = re.compile(
    r'^\s*DELETE\s+FROM\s+[`"]?([A-Za-z_][A-Za-z0-9_]*)[`"]?\s*;?\s*$',
    re.IGNORECASE,
)

# MySQL 风格 %(name)s 占位符 -> SQLite :name（预编译避免每条 SQL 重复编译正则）
_MYSQL_STYLE_PARAM = re.compile(r"%\((\w+)\)s")


async def _configure_sqlite_connection(conn: aiosqlite.Connection) -> None:
    """统一 SQLite 连接的并发与返回值配置。"""
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA synchronous=NORMAL")
    await conn.execute("PRAGMA busy_timeout=30000")
    await conn.commit()


class AsyncDatabase:
    """兼容原 API 的异步数据库门面。"""

    def __init__(self):
        """初始化数据库连接"""
        self.db_path = DB_PATH
        self._conn: aiosqlite.Connection | None = None
        self._use_shared = True  # 默认使用共享连接
        self._shared_registered = False

    async def initialize(self):
        """初始化数据库连接并创建表结构"""
        global _shared_connection, _connection_ref_count

        if self._use_shared:
            # 使用共享连接
            async with _connection_lock:
                if _shared_connection is None:
                    # 确保数据库文件目录存在
                    self.db_path.parent.mkdir(parents=True, exist_ok=True)

                    # 创建数据库连接，启用 WAL 模式提高并发性能
                    # 确保使用绝对路径，避免因工作目录不同导致在根目录创建数据库文件
                    _shared_connection = await aiosqlite.connect(
                        str(self.db_path.resolve()), timeout=30.0  # 增加超时时间
                    )
                    await _configure_sqlite_connection(_shared_connection)

                    # 初始化表结构
                    await self._init_tables(_shared_connection)

                    _logger.debug("数据库连接已创建（WAL模式）")

                self._conn = _shared_connection
                if not self._shared_registered:
                    _active_shared_databases.add(self)
                    _connection_ref_count += 1
                    self._shared_registered = True
                    _logger.debug("数据库连接引用计数: %d", _connection_ref_count)
        else:
            # 使用独立连接（不推荐，仅用于特殊场景）
            if self._conn is None:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                # 确保使用绝对路径，避免因工作目录不同导致在根目录创建数据库文件
                self._conn = await aiosqlite.connect(str(self.db_path.resolve()), timeout=30.0)
                await _configure_sqlite_connection(self._conn)
                await self._init_tables(self._conn)

        await _ensure_hybrid_runtime()

    async def _init_tables(self, conn: aiosqlite.Connection):
        """初始化数据库表结构"""
        # 创建 weibo 表
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weibo (
                UID TEXT PRIMARY KEY,
                用户名 TEXT NOT NULL,
                认证信息 TEXT,
                简介 TEXT,
                粉丝数 TEXT,
                微博数 TEXT,
                文本 TEXT,
                mid TEXT,
                图片 TEXT DEFAULT '[]',
                转发微博 TEXT DEFAULT '{}',
                正文结构 TEXT DEFAULT '[]',
                标签 TEXT DEFAULT '[]',
                内容类型 TEXT DEFAULT 'text',
                视频封面 TEXT DEFAULT ''
            )
        """
        )
        # 兼容旧版本：为 weibo 表补齐新增展示字段（若不存在）
        try:
            async with conn.execute("PRAGMA table_info(weibo)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
            if "图片" not in columns:
                await conn.execute("ALTER TABLE weibo ADD COLUMN 图片 TEXT DEFAULT '[]'")
            if "转发微博" not in columns:
                await conn.execute("ALTER TABLE weibo ADD COLUMN 转发微博 TEXT DEFAULT '{}'")
            if "正文结构" not in columns:
                await conn.execute("ALTER TABLE weibo ADD COLUMN 正文结构 TEXT DEFAULT '[]'")
            if "标签" not in columns:
                await conn.execute("ALTER TABLE weibo ADD COLUMN 标签 TEXT DEFAULT '[]'")
            if "内容类型" not in columns:
                await conn.execute("ALTER TABLE weibo ADD COLUMN 内容类型 TEXT DEFAULT 'text'")
            if "视频封面" not in columns:
                await conn.execute("ALTER TABLE weibo ADD COLUMN 视频封面 TEXT DEFAULT ''")
        except Exception as e:
            _logger.warning("为 weibo 表添加展示字段失败（不影响主流程）: %s", e)

        # 创建 huya 表（基础字段）
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS huya (
                room TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                is_live TEXT
            )
        """
        )
        # 兼容旧版本：为 huya 表增加 room_pic / avatar_url 字段（若不存在）
        try:
            async with conn.execute("PRAGMA table_info(huya)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
            if "room_pic" not in columns:
                await conn.execute("ALTER TABLE huya ADD COLUMN room_pic TEXT")
            if "avatar_url" not in columns:
                await conn.execute("ALTER TABLE huya ADD COLUMN avatar_url TEXT")
        except Exception as e:
            # 表结构升级失败不会影响主流程，只记录告警方便排查
            _logger.warning("为 huya 表添加图片字段失败（不影响主流程）: %s", e)

        # 创建 bilibili 表（动态：uid+dynamic_id；直播：uid+room_id+is_live）
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bilibili_dynamic (
                uid TEXT PRIMARY KEY,
                uname TEXT NOT NULL,
                dynamic_id TEXT,
                dynamic_text TEXT
            )
        """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bilibili_live (
                uid TEXT PRIMARY KEY,
                uname TEXT NOT NULL,
                room_id TEXT,
                is_live TEXT
            )
        """
        )

        # 创建 douyin 表
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS douyin (
                douyin_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                is_live TEXT
            )
        """
        )

        # 创建 douyu 表
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS douyu (
                room TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                is_live TEXT
            )
        """
        )

        # 创建 xhs 表
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS xhs (
                profile_id TEXT PRIMARY KEY,
                user_name TEXT NOT NULL,
                latest_note_title TEXT
            )
        """
        )
        try:
            async with conn.execute("PRAGMA table_info(xhs)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
            if "note_id" not in columns:
                await conn.execute("ALTER TABLE xhs ADD COLUMN note_id TEXT DEFAULT ''")
        except Exception as e:
            _logger.warning("为 xhs 表添加 note_id 字段失败（不影响主流程）: %s", e)

        # 定时任务运行记录（当天已运行则跳过）
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_run_history (
                job_id TEXT PRIMARY KEY,
                last_run_date TEXT NOT NULL
            )
        """
        )

        # MySQL 故障期间的本地变更日志，只存在 SQLite，不参与主备表同步。
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mysql_sync_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                pk_value TEXT,
                operation TEXT NOT NULL,
                row_data TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        await conn.commit()

    async def _check_connection_health(self) -> bool:
        """
        检查数据库连接是否健康

        Returns:
            True 如果连接健康，False 如果连接失效
        """
        if self._conn is None:
            return False

        try:
            # 执行一个简单的查询来检查连接
            async with self._conn.execute("SELECT 1") as cursor:
                await cursor.fetchone()
            return True
        except (
            aiosqlite.OperationalError,
            aiosqlite.ProgrammingError,
            AttributeError,
            RuntimeError,
        ) as e:
            _logger.debug("数据库连接健康检查失败: %s", e)
            return False
        except Exception as e:
            _logger.warning("数据库连接健康检查异常: %s", e)
            return False

    async def _reconnect(self):
        """
        重新建立数据库连接（仅在共享连接模式下使用）
        """
        global _shared_connection, _connection_ref_count

        if not self._use_shared:
            # 独立连接模式，直接重新初始化
            if self._conn:
                try:
                    await self._conn.close()
                except Exception:
                    pass
                self._conn = None
            await self.initialize()
            return

        # 共享连接模式
        async with _connection_lock:
            _logger.warning("检测到数据库连接失效，正在重新连接...")

            # 关闭旧连接
            if _shared_connection is not None:
                try:
                    await _shared_connection.close()
                except Exception as e:
                    _logger.debug("关闭旧连接时出错（可忽略）: %s", e)
                finally:
                    _shared_connection = None

            # 重新创建连接
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            _shared_connection = await aiosqlite.connect(str(self.db_path.resolve()), timeout=30.0)
            await _configure_sqlite_connection(_shared_connection)

            await self._init_tables(_shared_connection)

            for db in list(_active_shared_databases):
                db._conn = _shared_connection

            _logger.info("数据库连接已重新建立（WAL模式）")

    async def _ensure_connection(self):
        """
        确保数据库连接有效，如果失效则重新连接
        """
        if self._conn is None:
            await self.initialize()
            return

        # 检查连接健康状态
        if not await self._check_connection_health():
            await self._reconnect()

    async def close(self):
        """关闭数据库连接（共享连接时只减少引用计数）"""
        global _shared_connection, _connection_ref_count

        if self._use_shared:
            async with _connection_lock:
                if self._shared_registered:
                    _active_shared_databases.discard(self)
                    _connection_ref_count -= 1
                    self._shared_registered = False
                    _logger.debug("数据库连接引用计数: %d", _connection_ref_count)
                else:
                    _logger.warning("数据库连接引用计数已为0，可能存在重复关闭")
                # 共享连接不在这里关闭，由全局清理函数处理
                self._conn = None
        else:
            if self._conn:
                await self._conn.close()
                self._conn = None

    def _convert_sql(self, sql: str) -> str:
        """将 MySQL 风格的 SQL 转换为 SQLite 风格"""
        return _MYSQL_STYLE_PARAM.sub(r":\1", sql)

    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接的上下文管理器"""
        await self._ensure_connection()
        yield self._conn

    async def _execute_with_retry(self, operation, max_retries=5, initial_delay=0.1):
        """
        执行数据库操作，带重试机制和连接恢复

        Args:
            operation: 要执行的异步操作函数
            max_retries: 最大重试次数
            initial_delay: 初始延迟（秒），每次重试会指数退避

        Returns:
            操作结果
        """
        delay = initial_delay
        last_exception = None

        for attempt in range(max_retries):
            try:
                # 在执行前确保连接有效
                await self._ensure_connection()
                return await operation()
            except aiosqlite.OperationalError as e:
                error_str = str(e).lower()
                if "database is locked" in error_str or "locked" in error_str:
                    last_exception = e
                    if attempt < max_retries - 1:
                        _logger.warning(
                            "数据库锁定，重试 %d/%d (延迟 %.2f秒)",
                            attempt + 1,
                            max_retries,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        delay *= 2
                    else:
                        _logger.error("数据库操作失败，已达到最大重试次数: %s", e)
                        raise
                elif "no such table" in error_str or "unable to open" in error_str:
                    _logger.warning("检测到数据库结构问题，尝试重新连接: %s", e)
                    try:
                        await self._reconnect()
                        # 重连后立即重试
                        if attempt < max_retries - 1:
                            await asyncio.sleep(0.1)
                            continue
                    except Exception as reconnect_error:
                        _logger.error("重新连接失败: %s", reconnect_error)
                        raise
                    raise
                else:
                    if attempt == 0:
                        _logger.warning("数据库操作错误，尝试重新连接: %s", e)
                        try:
                            await self._reconnect()
                            await asyncio.sleep(0.1)
                            continue
                        except Exception as reconnect_error:
                            _logger.debug("重新连接失败: %s", reconnect_error)
                    raise
            except (AttributeError, RuntimeError) as e:
                if attempt == 0:
                    _logger.warning("检测到连接对象异常，尝试重新连接: %s", e)
                    try:
                        await self._reconnect()
                        await asyncio.sleep(0.1)
                        continue
                    except Exception as reconnect_error:
                        _logger.error("重新连接失败: %s", reconnect_error)
                        raise
                raise
            except Exception as e:
                _logger.error("数据库操作异常: %s", e)
                raise

        if last_exception:
            raise last_exception

    async def execute_query(self, sql: str, params: dict | None = None) -> list[tuple]:
        """从当前权威后端查询；MySQL 断连时自动回退 SQLite。"""
        sqlite_sql = self._convert_sql(sql)
        await self._ensure_connection()
        await _ensure_hybrid_runtime()
        try:
            async with _database_operation_lock:
                if _active_backend == "mysql" and _mysql_pool is not None:
                    try:
                        return await mysql_query(_mysql_pool, sql, params)
                    except Exception as exc:
                        if not is_mysql_connection_error(exc):
                            raise
                        await _activate_sqlite_fallback_locked("MySQL 连接中断，已回退 SQLite")
                return await _sqlite_query(self._conn, sqlite_sql, params)
        except Exception as e:
            _logger.error("数据库查询失败: %s\nSQL: %s", e, sqlite_sql)
            raise

    async def execute_update(self, sql: str, params: dict | None = None) -> bool:
        """写入权威后端并维护 SQLite 镜像。"""
        sqlite_sql = self._convert_sql(sql)
        await self._ensure_connection()
        await _ensure_hybrid_runtime()
        try:
            async with _database_operation_lock:
                if _active_backend == "mysql" and _mysql_pool is not None:
                    try:
                        await mysql_update(_mysql_pool, sql, params)
                    except Exception as exc:
                        if not is_mysql_connection_error(exc):
                            raise
                        await _activate_sqlite_fallback_locked("MySQL 连接中断，已回退 SQLite")
                    else:
                        try:
                            await _sqlite_update(self._conn, sqlite_sql, params)
                            _set_sqlite_health(True)
                        except Exception as mirror_error:
                            _mark_mirror_degraded(mirror_error)
                        return True

                journal = bool(_mysql_settings and _mysql_settings.configured)
                if journal:
                    await _sqlite_update_with_outbox(self._conn, sqlite_sql, params)
                else:
                    await _sqlite_update(self._conn, sqlite_sql, params)
                _set_sqlite_health(True)
                return True
        except Exception as e:
            try:
                if self._conn:
                    await self._conn.rollback()
            except Exception:
                pass
            if _active_backend != "mysql":
                _set_sqlite_health(False)
            _logger.error("数据库操作失败: %s\nSQL: %s", e, sqlite_sql)
            return False

    async def execute_insert(self, sql: str, params: dict | None = None) -> bool:
        """执行插入操作"""
        return await self.execute_update(sql, params)

    async def execute_delete(self, sql: str, params: dict | None = None) -> bool:
        """执行删除操作"""
        return await self.execute_update(sql, params)

    async def is_table_empty(self, table_name: str) -> bool:
        """
        检查表是否为空（用于判断是否是首次创建数据库）

        Args:
            table_name: 表名（仅允许字母、数字、下划线，防止 SQL 注入）

        Returns:
            True 如果表为空，False 如果表有数据
        """
        if not table_name or not all(c.isalnum() or c == "_" for c in table_name):
            _logger.warning("is_table_empty: 非法表名 %r，视为空", table_name)
            return True
        try:
            sql = f"SELECT COUNT(*) FROM {table_name}"
            results = await self.execute_query(sql)
            count = results[0][0] if results else 0
            return count == 0
        except Exception as e:
            _logger.error("检查表 %s 是否为空失败: %s", table_name, e)
            # 如果表不存在，也认为是首次创建
            return True

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


def _set_sqlite_health(healthy: bool) -> None:
    global _sqlite_healthy
    _sqlite_healthy = healthy


def _mark_mirror_degraded(exc: BaseException) -> None:
    global _mirror_degraded, _sync_state, _status_message, _sqlite_healthy
    _mirror_degraded = True
    _sqlite_healthy = False
    _sync_state = "mirror_degraded"
    _status_message = "MySQL 正常，但 SQLite 镜像写入失败，等待重新校准"
    _logger.error("SQLite 镜像写入失败: %s", type(exc).__name__)


async def _sqlite_query(
    conn: aiosqlite.Connection,
    sql: str,
    params: dict | None = None,
) -> list[tuple]:
    async with conn.execute(sql, params) as cursor:
        return [tuple(row) for row in await cursor.fetchall()]


async def _sqlite_update(
    conn: aiosqlite.Connection,
    sql: str,
    params: dict | None = None,
) -> None:
    try:
        await conn.execute(sql, params)
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


def _table_from_write_sql(sql: str) -> str | None:
    match = _WRITE_TABLE.match(sql)
    if match is None:
        return None
    table_name = match.group(1)
    return table_name if table_name in TABLE_SPECS else None


async def _sqlite_update_with_outbox(
    conn: aiosqlite.Connection,
    sql: str,
    params: dict | None,
) -> None:
    """原子写入 SQLite 业务表和 MySQL 离线日志。"""
    table_name = _table_from_write_sql(sql)
    if table_name is None:
        raise ValueError("MySQL 回退模式不支持未登记的数据表写入")
    spec = TABLE_SPECS[table_name]
    normalized = sql.lstrip().upper()
    is_delete = normalized.startswith("DELETE")
    is_clear = bool(_CLEAR_TABLE.fullmatch(sql))
    param_values = params or {}
    pk_value_raw = param_values.get(spec.primary_key, param_values.get("pk"))
    if not is_clear and pk_value_raw is None:
        raise ValueError(
            f"MySQL 回退模式写入 {table_name} 时缺少主键参数 {spec.primary_key}"
        )

    try:
        await conn.execute("BEGIN IMMEDIATE")
        await conn.execute(sql, params)
        if is_clear:
            operation = "clear"
            pk_value = None
            row_data = None
        else:
            pk_value = str(pk_value_raw)
            if is_delete:
                operation = "delete"
                row_data = None
            else:
                quoted_columns = ", ".join(f'"{column}"' for column in spec.columns)
                async with conn.execute(
                    f'SELECT {quoted_columns} FROM "{table_name}" WHERE "{spec.primary_key}"=:pk',
                    {"pk": pk_value},
                ) as cursor:
                    row = await cursor.fetchone()
                if row is None:
                    raise RuntimeError(
                        f"写入 {table_name} 后未找到主键 {spec.primary_key}={pk_value}"
                    )
                operation = "upsert"
                row_data = json.dumps(
                    dict(zip(spec.columns, tuple(row), strict=True)),
                    ensure_ascii=False,
                )
        await conn.execute(
            """
            INSERT INTO mysql_sync_outbox
                (table_name, pk_value, operation, row_data, created_at)
            VALUES (:table_name, :pk_value, :operation, :row_data, :created_at)
            """,
            {
                "table_name": table_name,
                "pk_value": pk_value,
                "operation": operation,
                "row_data": row_data,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


async def _fetch_sqlite_tables(
    conn: aiosqlite.Connection,
) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for spec in TABLE_SPECS.values():
        quoted_columns = ", ".join(f'"{column}"' for column in spec.columns)
        async with conn.execute(f'SELECT {quoted_columns} FROM "{spec.name}"') as cursor:
            rows = await cursor.fetchall()
        tables[spec.name] = [
            dict(zip(spec.columns, tuple(row), strict=True)) for row in rows
        ]
    return tables


async def _replace_sqlite_tables(
    conn: aiosqlite.Connection,
    tables: dict[str, list[dict[str, Any]]],
) -> None:
    try:
        await conn.execute("BEGIN IMMEDIATE")
        for spec in TABLE_SPECS.values():
            await conn.execute(f'DELETE FROM "{spec.name}"')
            rows = tables.get(spec.name, [])
            if not rows:
                continue
            quoted_columns = ", ".join(f'"{column}"' for column in spec.columns)
            placeholders = ", ".join(f":{column}" for column in spec.columns)
            await conn.executemany(
                f'INSERT INTO "{spec.name}" ({quoted_columns}) VALUES ({placeholders})',
                [{column: row.get(column) for column in spec.columns} for row in rows],
            )
        await conn.commit()
        _set_sqlite_health(True)
    except Exception:
        await conn.rollback()
        _set_sqlite_health(False)
        raise


async def _load_outbox(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
    async with conn.execute(
        "SELECT id, table_name, pk_value, operation, row_data FROM mysql_sync_outbox ORDER BY id"
    ) as cursor:
        rows = await cursor.fetchall()
    events = []
    for row in rows:
        events.append(
            {
                "id": row[0],
                "table_name": row[1],
                "pk_value": row[2],
                "operation": row[3],
                "row_data": json.loads(row[4]) if row[4] else None,
            }
        )
    return events


async def _clear_outbox(conn: aiosqlite.Connection, event_ids: list[int] | None = None) -> None:
    if event_ids:
        placeholders = ",".join("?" for _ in event_ids)
        await conn.execute(
            f"DELETE FROM mysql_sync_outbox WHERE id IN ({placeholders})",
            event_ids,
        )
    else:
        await conn.execute("DELETE FROM mysql_sync_outbox")
    await conn.commit()


async def _synchronize_connected_mysql_locked(pool) -> None:
    """按初始化规则对齐已连接的 MySQL 与 SQLite。"""
    global _sync_state, _last_sync_at, _status_message, _mirror_degraded
    conn = _shared_connection
    if conn is None:
        raise RuntimeError("SQLite 尚未初始化")

    _sync_state = "replaying"
    _status_message = "正在同步 MySQL 与 SQLite"
    events = await _load_outbox(conn)
    if await mysql_tables_empty(pool):
        await replace_mysql_tables(pool, await _fetch_sqlite_tables(conn))
        await _clear_outbox(conn)
    else:
        if events:
            await replay_mysql_events(pool, events)
            await _clear_outbox(conn, [event["id"] for event in events])
        await _replace_sqlite_tables(conn, await fetch_mysql_tables(pool))

    _mirror_degraded = False
    _last_sync_at = datetime.now().isoformat(timespec="seconds")
    _sync_state = "in_sync"
    _status_message = "MySQL 主库与 SQLite 镜像已同步"


async def _activate_sqlite_fallback_locked(message: str) -> None:
    global _mysql_pool, _active_backend, _sync_state, _mysql_reachable, _status_message
    pool = _mysql_pool
    _mysql_pool = None
    _active_backend = "sqlite"
    _sync_state = "fallback"
    _mysql_reachable = False
    _status_message = message
    await close_mysql_pool(pool)
    _start_maintenance_task()


def _start_maintenance_task() -> None:
    global _maintenance_task, _maintenance_stop
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    if _maintenance_task is not None and not _maintenance_task.done():
        return
    _maintenance_stop = asyncio.Event()
    _maintenance_task = asyncio.create_task(
        _maintenance_loop(),
        name="database-mysql-maintenance",
    )


async def _maintenance_loop() -> None:
    calibration_ticks = 0
    while not _maintenance_stop.is_set():
        try:
            await asyncio.wait_for(_maintenance_stop.wait(), timeout=30)
            break
        except TimeoutError:
            pass

        try:
            if _mysql_settings is None or not _mysql_settings.configured:
                continue
            if _active_backend != "mysql" or _mysql_pool is None:
                from src.settings.config import get_config

                await reconfigure_database(get_config(), force=True)
                calibration_ticks = 0
                continue
            calibration_ticks += 1
            if calibration_ticks >= 2:
                await calibrate_sqlite_mirror()
                calibration_ticks = 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _logger.warning("数据库后台维护失败: %s", type(exc).__name__)


async def calibrate_sqlite_mirror() -> None:
    global _last_sync_at, _sync_state, _status_message, _mirror_degraded
    async with _database_operation_lock:
        if _active_backend != "mysql" or _mysql_pool is None or _shared_connection is None:
            return
        try:
            tables = await fetch_mysql_tables(_mysql_pool)
            await _replace_sqlite_tables(_shared_connection, tables)
            _last_sync_at = datetime.now().isoformat(timespec="seconds")
            _mirror_degraded = False
            _sync_state = "in_sync"
            _status_message = "MySQL 主库与 SQLite 镜像已同步"
        except Exception as exc:
            if is_mysql_connection_error(exc):
                await _activate_sqlite_fallback_locked("MySQL 校准时断连，已回退 SQLite")
            else:
                _mark_mirror_degraded(exc)


async def reconfigure_database(config=None, *, force: bool = False) -> dict[str, Any]:
    """按最新配置热切换数据库后端，失败时保持 SQLite 可用。"""
    global _mysql_pool, _mysql_settings, _active_backend, _sync_state
    global _mysql_reachable, _status_message

    if config is None:
        from src.settings.config import get_config

        config = get_config()
    settings = MySQLSettings.from_config(config)
    await _ensure_shared_connection()

    async with _hybrid_init_lock:
        if (
            not force
            and _mysql_settings is not None
            and settings.fingerprint == _mysql_settings.fingerprint
            and ((_mysql_pool is not None) or not settings.configured)
        ):
            _start_maintenance_task()
            return await get_database_status()

        async with _database_operation_lock:
            old_pool = _mysql_pool
            _mysql_pool = None
            if old_pool is not None:
                if _active_backend == "mysql" and _shared_connection is not None:
                    try:
                        await _replace_sqlite_tables(
                            _shared_connection,
                            await fetch_mysql_tables(old_pool),
                        )
                    except Exception as exc:
                        _logger.warning("切换前校准 SQLite 失败: %s", type(exc).__name__)
                await close_mysql_pool(old_pool)

            _mysql_settings = settings
            _active_backend = "sqlite"
            _mysql_reachable = False
            if not settings.configured:
                _sync_state = "sqlite_only"
                _status_message = (
                    "MySQL 配置不完整，正在使用 SQLite"
                    if settings.enabled
                    else "未启用 MySQL，正在使用 SQLite"
                )
                return await get_database_status()

            pool = None
            try:
                pool = await create_mysql_pool(settings)
                await initialize_mysql_schema(pool)
                await _synchronize_connected_mysql_locked(pool)
            except Exception as exc:
                await close_mysql_pool(pool)
                _sync_state = "fallback"
                _status_message = "MySQL 暂时不可用，正在使用 SQLite 并等待重连"
                _logger.warning("MySQL 连接或同步失败，已回退 SQLite: %s", type(exc).__name__)
            else:
                _mysql_pool = pool
                _active_backend = "mysql"
                _mysql_reachable = True

        _start_maintenance_task()
        return await get_database_status()


async def _ensure_hybrid_runtime() -> None:
    if _mysql_settings is None:
        await reconfigure_database()
    else:
        _start_maintenance_task()


async def get_database_status() -> dict[str, Any]:
    pending = 0
    if _shared_connection is not None:
        try:
            async with _shared_connection.execute(
                "SELECT COUNT(*) FROM mysql_sync_outbox"
            ) as cursor:
                row = await cursor.fetchone()
                pending = int(row[0]) if row else 0
        except Exception:
            pass
    settings = _mysql_settings
    return {
        "configured": bool(settings and settings.configured),
        "active_backend": _active_backend,
        "mysql_reachable": _mysql_reachable,
        "sqlite_healthy": _sqlite_healthy,
        "sync_state": _sync_state,
        "pending_changes": pending,
        "last_sync_at": _last_sync_at,
        "message": _status_message,
    }


async def test_database_config(config) -> None:
    settings = MySQLSettings.from_config(config)
    if not settings.host or not settings.user or not settings.database:
        raise ValueError("请填写 MySQL 主机、用户和数据库名")
    settings = replace(settings, enabled=True)
    await test_mysql_connection(settings)


async def _ensure_shared_connection() -> aiosqlite.Connection:
    """确保共享连接已建立（供 task_run_history 等模块级 API 使用）。"""
    global _shared_connection

    if _shared_connection is not None:
        return _shared_connection

    async with _connection_lock:
        if _shared_connection is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _shared_connection = await aiosqlite.connect(str(DB_PATH.resolve()), timeout=30.0)
            await _configure_sqlite_connection(_shared_connection)
            await AsyncDatabase()._init_tables(_shared_connection)

    return _shared_connection


async def has_run_today(job_id: str) -> bool:
    """检查指定任务今天是否已经运行过。"""
    today_str = date.today().isoformat()
    async with AsyncDatabase() as db:
        rows = await db.execute_query(
            "SELECT last_run_date FROM task_run_history WHERE job_id=%(job_id)s",
            {"job_id": job_id},
        )
    return bool(rows and rows[0][0] == today_str)


async def mark_as_run_today(job_id: str) -> None:
    """标记指定任务今天已经运行过。"""
    today_str = date.today().isoformat()
    async with AsyncDatabase() as db:
        ok = await db.execute_update(
            """
            INSERT OR REPLACE INTO task_run_history (job_id, last_run_date)
            VALUES (%(job_id)s, %(last_run_date)s)
            """,
            {"job_id": job_id, "last_run_date": today_str},
        )
    if not ok:
        raise RuntimeError("写入任务运行历史失败")


async def clear_run_history(job_id: str | None = None) -> None:
    """清除任务运行记录；job_id 为 None 时清除全部。"""
    async with AsyncDatabase() as db:
        if job_id is None:
            ok = await db.execute_update("DELETE FROM task_run_history")
        else:
            ok = await db.execute_update(
                "DELETE FROM task_run_history WHERE job_id=%(job_id)s",
                {"job_id": job_id},
            )
    if not ok:
        raise RuntimeError("清除任务运行历史失败")


async def close_shared_connection():
    """关闭共享数据库连接（程序退出时调用）"""
    global _shared_connection, _connection_ref_count, _mysql_pool, _mysql_settings
    global _maintenance_task, _active_backend, _mysql_reachable, _sync_state
    global _sqlite_healthy, _mirror_degraded, _last_sync_at, _status_message

    _maintenance_stop.set()
    task = _maintenance_task
    _maintenance_task = None
    if task is not None and task is not asyncio.current_task():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    pool = _mysql_pool
    _mysql_pool = None
    await close_mysql_pool(pool)
    _mysql_settings = None
    _active_backend = "sqlite"
    _mysql_reachable = False
    _sync_state = "sqlite_only"
    _sqlite_healthy = True
    _mirror_degraded = False
    _last_sync_at = None
    _status_message = "未启用 MySQL，正在使用 SQLite"

    async with _connection_lock:
        if _shared_connection is not None:
            try:
                await _shared_connection.close()
                _logger.info("共享数据库连接已关闭")
            except Exception as e:
                _logger.error("关闭数据库连接时出错: %s", e)
            finally:
                _shared_connection = None
                for db in _active_shared_databases:
                    db._shared_registered = False
                    db._conn = None
                _active_shared_databases.clear()
                _connection_ref_count = 0
