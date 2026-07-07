"""异步数据库操作模块 - 使用 SQLite"""

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from datetime import date

import aiosqlite

from src.core.paths import DB_PATH

# 全局单例数据库连接
_shared_connection: aiosqlite.Connection | None = None
_connection_lock = asyncio.Lock()
_connection_ref_count = 0
_active_shared_databases: set["AsyncDatabase"] = set()
_logger = logging.getLogger(__name__)

# MySQL 风格 %(name)s 占位符 -> SQLite :name（预编译避免每条 SQL 重复编译正则）
_MYSQL_STYLE_PARAM = re.compile(r"%\((\w+)\)s")


class AsyncDatabase:
    """异步数据库操作类 - 使用 SQLite（支持共享连接）"""

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
                    # 设置行工厂，返回字典格式的结果
                    _shared_connection.row_factory = aiosqlite.Row

                    # 启用 WAL 模式以提高并发性能
                    await _shared_connection.execute("PRAGMA journal_mode=WAL")
                    await _shared_connection.execute("PRAGMA synchronous=NORMAL")
                    await _shared_connection.execute("PRAGMA busy_timeout=30000")  # 30秒超时
                    await _shared_connection.commit()

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
                self._conn.row_factory = aiosqlite.Row
                await self._conn.execute("PRAGMA journal_mode=WAL")
                await self._conn.execute("PRAGMA synchronous=NORMAL")
                await self._conn.execute("PRAGMA busy_timeout=30000")
                await self._conn.commit()
                await self._init_tables(self._conn)

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
                转发微博 TEXT DEFAULT '{}'
            )
        """
        )
        # 兼容旧版本：为 weibo 表增加 图片 / 转发微博 字段（若不存在）
        try:
            async with conn.execute("PRAGMA table_info(weibo)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
            if "图片" not in columns:
                await conn.execute("ALTER TABLE weibo ADD COLUMN 图片 TEXT DEFAULT '[]'")
            if "转发微博" not in columns:
                await conn.execute("ALTER TABLE weibo ADD COLUMN 转发微博 TEXT DEFAULT '{}'")
        except Exception as e:
            _logger.warning("为 weibo 表添加图片/转发微博字段失败（不影响主流程）: %s", e)

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
            _shared_connection.row_factory = aiosqlite.Row

            await _shared_connection.execute("PRAGMA journal_mode=WAL")
            await _shared_connection.execute("PRAGMA synchronous=NORMAL")
            await _shared_connection.execute("PRAGMA busy_timeout=30000")
            await _shared_connection.commit()

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
        """执行查询操作（带重试机制和连接检查）"""
        # 转换 SQL 和参数
        sqlite_sql = self._convert_sql(sql)

        async def _query():
            async with self._conn.execute(sqlite_sql, params) as cursor:
                rows = await cursor.fetchall()
                # 将 Row 对象转换为元组
                return [tuple(row) for row in rows]

        try:
            return await self._execute_with_retry(_query)
        except Exception as e:
            _logger.error("数据库查询失败: %s\nSQL: %s\nParams: %s", e, sqlite_sql, params)
            raise

    async def execute_update(self, sql: str, params: dict | None = None) -> bool:
        """执行更新操作（INSERT/UPDATE/DELETE，带重试机制和连接检查）"""
        # 转换 SQL 和参数
        sqlite_sql = self._convert_sql(sql)

        async def _update():
            await self._conn.execute(sqlite_sql, params)
            await self._conn.commit()
            return True

        try:
            return await self._execute_with_retry(_update)
        except Exception as e:
            try:
                if self._conn:
                    await self._conn.rollback()
            except Exception:
                pass
            _logger.error("数据库操作失败: %s\nSQL: %s\nParams: %s", e, sqlite_sql, params)
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


async def _ensure_shared_connection() -> aiosqlite.Connection:
    """确保共享连接已建立（供 task_run_history 等模块级 API 使用）。"""
    global _shared_connection

    if _shared_connection is not None:
        return _shared_connection

    async with _connection_lock:
        if _shared_connection is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _shared_connection = await aiosqlite.connect(str(DB_PATH.resolve()), timeout=30.0)
            _shared_connection.row_factory = aiosqlite.Row
            await _shared_connection.execute("PRAGMA journal_mode=WAL")
            await _shared_connection.execute("PRAGMA synchronous=NORMAL")
            await _shared_connection.execute("PRAGMA busy_timeout=30000")
            await _shared_connection.commit()
            await AsyncDatabase()._init_tables(_shared_connection)

    return _shared_connection


async def has_run_today(job_id: str) -> bool:
    """检查指定任务今天是否已经运行过。"""
    conn = await _ensure_shared_connection()
    today_str = date.today().isoformat()

    async with conn.execute(
        "SELECT last_run_date FROM task_run_history WHERE job_id = ?",
        (job_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return False
        return row[0] == today_str


async def mark_as_run_today(job_id: str) -> None:
    """标记指定任务今天已经运行过。"""
    conn = await _ensure_shared_connection()
    today_str = date.today().isoformat()

    await conn.execute(
        """
        INSERT OR REPLACE INTO task_run_history (job_id, last_run_date)
        VALUES (?, ?)
        """,
        (job_id, today_str),
    )
    await conn.commit()


async def clear_run_history(job_id: str | None = None) -> None:
    """清除任务运行记录；job_id 为 None 时清除全部。"""
    conn = await _ensure_shared_connection()

    if job_id is None:
        await conn.execute("DELETE FROM task_run_history")
    else:
        await conn.execute(
            "DELETE FROM task_run_history WHERE job_id = ?",
            (job_id,),
        )
    await conn.commit()


async def close_shared_connection():
    """关闭共享数据库连接（程序退出时调用）"""
    global _shared_connection, _connection_ref_count

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
