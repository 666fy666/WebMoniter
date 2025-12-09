"""异步数据库操作模块"""
from contextlib import asynccontextmanager
from typing import Any, Optional

import aiomysql
from aiomysql import Connection, Cursor

from src.config import DatabaseConfig


class AsyncDatabase:
    """异步数据库操作类"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._pool: Optional[aiomysql.Pool] = None

    async def initialize(self):
        """初始化连接池"""
        if self._pool is None:
            self._pool = await aiomysql.create_pool(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                db=self.config.db,
                charset="utf8mb4",
                autocommit=False,
                minsize=1,
                maxsize=10,
            )

    async def close(self):
        """关闭连接池"""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接的上下文管理器"""
        if self._pool is None:
            await self.initialize()

        async with self._pool.acquire() as conn:
            yield conn

    async def execute_query(self, sql: str, params: Optional[dict] = None) -> list[tuple]:
        """执行查询操作"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                return await cur.fetchall()

    async def execute_update(self, sql: str, params: Optional[dict] = None) -> bool:
        """执行更新操作（INSERT/UPDATE/DELETE）"""
        async with self.get_connection() as conn:
            try:
                async with conn.cursor() as cur:
                    await cur.execute(sql, params)
                    await conn.commit()
                    return True
            except Exception as e:
                await conn.rollback()
                print(f"数据库操作失败: {e}\nSQL: {sql}")
                return False

    async def execute_insert(self, sql: str, params: Optional[dict] = None) -> bool:
        """执行插入操作"""
        return await self.execute_update(sql, params)

    async def execute_delete(self, sql: str, params: Optional[dict] = None) -> bool:
        """执行删除操作"""
        return await self.execute_update(sql, params)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

