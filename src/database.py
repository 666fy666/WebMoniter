"""异步数据库操作模块 - 使用 SQLite"""

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

# 数据库文件路径（始终使用 data/ 目录，如果不存在则自动创建）
# Docker 环境：如果宿主机没有 ./data 目录，Docker 会自动创建空目录并挂载
# 本地环境：如果 data 目录不存在，程序会自动创建
# 使用 resolve() 获取绝对路径，避免因工作目录不同导致路径错误
_base_path = Path(__file__).resolve().parent.parent
_data_dir = _base_path / "data"
# 确保 data 目录存在（Docker 挂载时已存在也不会报错，exist_ok=True）
_data_dir.mkdir(parents=True, exist_ok=True)
# 确保 DB_PATH 是绝对路径，避免因工作目录不同导致在根目录创建数据库文件
DB_PATH = (_data_dir / "data.db").resolve()

# 全局单例数据库连接
_shared_connection: aiosqlite.Connection | None = None
_connection_lock = asyncio.Lock()
_connection_ref_count = 0
_logger = logging.getLogger(__name__)


class AsyncDatabase:
    """异步数据库操作类 - 使用 SQLite（支持共享连接）"""

    def __init__(self):
        """初始化数据库连接"""
        self.db_path = DB_PATH
        self._conn: aiosqlite.Connection | None = None
        self._use_shared = True  # 默认使用共享连接

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
                _connection_ref_count += 1
                _logger.debug(f"数据库连接引用计数: {_connection_ref_count}")
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
                mid TEXT
            )
        """
        )

        # 创建 huya 表
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS huya (
                room TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                is_live TEXT
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
            _logger.debug(f"数据库连接健康检查失败: {e}")
            return False
        except Exception as e:
            _logger.warning(f"数据库连接健康检查异常: {e}")
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
                    _logger.debug(f"关闭旧连接时出错（可忽略）: {e}")
                finally:
                    _shared_connection = None
                    _connection_ref_count = 0

            # 重新创建连接
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            # 确保使用绝对路径，避免因工作目录不同导致在根目录创建数据库文件
            _shared_connection = await aiosqlite.connect(str(self.db_path.resolve()), timeout=30.0)
            _shared_connection.row_factory = aiosqlite.Row

            # 重新设置 WAL 模式
            await _shared_connection.execute("PRAGMA journal_mode=WAL")
            await _shared_connection.execute("PRAGMA synchronous=NORMAL")
            await _shared_connection.execute("PRAGMA busy_timeout=30000")
            await _shared_connection.commit()

            # 重新初始化表结构（CREATE TABLE IF NOT EXISTS 是安全的）
            await self._init_tables(_shared_connection)

            # 更新当前实例的连接引用
            self._conn = _shared_connection
            _connection_ref_count = 1

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
                if _connection_ref_count > 0:
                    _connection_ref_count -= 1
                    _logger.debug(f"数据库连接引用计数: {_connection_ref_count}")
                else:
                    _logger.warning("数据库连接引用计数已为0，可能存在重复关闭")
                # 共享连接不在这里关闭，由全局清理函数处理
                self._conn = None
        else:
            if self._conn:
                await self._conn.close()
                self._conn = None

    def _convert_params(self, params: dict | None) -> dict | None:
        """将 MySQL 风格的参数占位符转换为 SQLite 风格"""
        if params is None:
            return None
        # SQLite 使用 :key 格式，MySQL 使用 %(key)s
        # 这里保持兼容，直接返回原参数，SQL 语句中需要适配
        return params

    def _convert_sql(self, sql: str) -> str:
        """将 MySQL 风格的 SQL 转换为 SQLite 风格"""
        # 将 %(key)s 替换为 :key
        return re.sub(r"%\((\w+)\)s", r":\1", sql)

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
                            f"数据库锁定，重试 {attempt + 1}/{max_retries} " f"(延迟 {delay:.2f}秒)"
                        )
                        await asyncio.sleep(delay)
                        delay *= 2  # 指数退避
                    else:
                        _logger.error(f"数据库操作失败，已达到最大重试次数: {e}")
                        raise
                elif "no such table" in error_str or "unable to open" in error_str:
                    # 数据库文件或表结构问题，尝试重连
                    _logger.warning(f"检测到数据库结构问题，尝试重新连接: {e}")
                    try:
                        await self._reconnect()
                        # 重连后立即重试
                        if attempt < max_retries - 1:
                            await asyncio.sleep(0.1)
                            continue
                    except Exception as reconnect_error:
                        _logger.error(f"重新连接失败: {reconnect_error}")
                        raise
                    raise
                else:
                    # 其他类型的 OperationalError，尝试重连一次
                    if attempt == 0:
                        _logger.warning(f"数据库操作错误，尝试重新连接: {e}")
                        try:
                            await self._reconnect()
                            await asyncio.sleep(0.1)
                            continue
                        except Exception as reconnect_error:
                            _logger.debug(f"重新连接失败: {reconnect_error}")
                    raise
            except (AttributeError, RuntimeError) as e:
                # 连接对象可能已失效
                if attempt == 0:
                    _logger.warning(f"检测到连接对象异常，尝试重新连接: {e}")
                    try:
                        await self._reconnect()
                        await asyncio.sleep(0.1)
                        continue
                    except Exception as reconnect_error:
                        _logger.error(f"重新连接失败: {reconnect_error}")
                        raise
                raise
            except Exception as e:
                _logger.error(f"数据库操作异常: {e}")
                raise

        if last_exception:
            raise last_exception

    async def execute_query(self, sql: str, params: dict | None = None) -> list[tuple]:
        """执行查询操作（带重试机制和连接检查）"""
        # 转换 SQL 和参数
        sqlite_sql = self._convert_sql(sql)
        sqlite_params = self._convert_params(params)

        async def _query():
            async with self._conn.execute(sqlite_sql, sqlite_params) as cursor:
                rows = await cursor.fetchall()
                # 将 Row 对象转换为元组
                return [tuple(row) for row in rows]

        try:
            return await self._execute_with_retry(_query)
        except Exception as e:
            _logger.error(f"数据库查询失败: {e}\nSQL: {sqlite_sql}\nParams: {sqlite_params}")
            raise

    async def execute_update(self, sql: str, params: dict | None = None) -> bool:
        """执行更新操作（INSERT/UPDATE/DELETE，带重试机制和连接检查）"""
        # 转换 SQL 和参数
        sqlite_sql = self._convert_sql(sql)
        sqlite_params = self._convert_params(params)

        async def _update():
            await self._conn.execute(sqlite_sql, sqlite_params)
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
            _logger.error(f"数据库操作失败: {e}\nSQL: {sqlite_sql}\nParams: {sqlite_params}")
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
            table_name: 表名

        Returns:
            True 如果表为空，False 如果表有数据
        """
        try:
            sql = f"SELECT COUNT(*) FROM {table_name}"
            results = await self.execute_query(sql)
            count = results[0][0] if results else 0
            return count == 0
        except Exception as e:
            _logger.error(f"检查表 {table_name} 是否为空失败: {e}")
            # 如果表不存在，也认为是首次创建
            return True

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


async def close_shared_connection():
    """关闭共享数据库连接（程序退出时调用）"""
    global _shared_connection, _connection_ref_count

    async with _connection_lock:
        if _shared_connection is not None:
            try:
                await _shared_connection.close()
                _logger.info("共享数据库连接已关闭")
            except Exception as e:
                _logger.error(f"关闭数据库连接时出错: {e}")
            finally:
                _shared_connection = None
                _connection_ref_count = 0
