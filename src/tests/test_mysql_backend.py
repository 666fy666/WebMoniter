"""MySQL 方言和 SQLite 离线日志契约。"""

import aiomysql
import aiosqlite
import pytest

from src.settings.config import AppConfig
from src.storage import database as db_module
from src.storage.mysql_backend import (
    MySQLSettings,
    _migrate_mysql_columns,
    convert_mysql_sql,
    select_mysql_params,
)


def test_mysql_sql_conversion_supports_both_project_placeholder_styles() -> None:
    sql = convert_mysql_sql(
        "INSERT OR REPLACE INTO task_run_history (job_id) VALUES (:job_id)"
    )

    assert sql.startswith("REPLACE INTO")
    assert "%(job_id)s" in sql
    assert convert_mysql_sql("SELECT * FROM xhs WHERE profile_id=%(pk)s").endswith(
        "profile_id=%(pk)s"
    )


def test_mysql_params_exclude_unused_business_objects() -> None:
    sql = convert_mysql_sql("UPDATE weibo SET 正文结构=:正文结构 WHERE UID=:UID")
    params = {
        "UID": "1",
        "正文结构": "[]",
        "_url_struct": [{"url": "https://example.com"}],
        "_content_rich_text": object(),
    }

    assert select_mysql_params(sql, params) == {"正文结构": "[]", "UID": "1"}


def test_mysql_settings_requires_enabled_host_user_and_database() -> None:
    incomplete = MySQLSettings(False, "db", 3306, "u", "", "d", 5, 1, 5)
    complete = MySQLSettings(True, "db", 3306, "u", "", "d", 5, 1, 5)

    assert incomplete.configured is False
    assert complete.configured is True


@pytest.mark.asyncio
async def test_sqlite_connection_uses_consistent_pragmas() -> None:
    class FakeConnection:
        row_factory = None

        def __init__(self) -> None:
            self.statements: list[str] = []
            self.committed = False

        async def execute(self, sql) -> None:
            self.statements.append(sql)

        async def commit(self) -> None:
            self.committed = True

    conn = FakeConnection()
    await db_module._configure_sqlite_connection(conn)

    assert conn.row_factory is aiosqlite.Row
    assert conn.statements == [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA busy_timeout=30000",
    ]
    assert conn.committed is True


@pytest.mark.asyncio
async def test_mysql_schema_migration_adds_only_missing_legacy_columns() -> None:
    class FakeCursor:
        def __init__(self) -> None:
            self.current_table = ""
            self.statements: list[str] = []

        async def execute(self, sql, params=None) -> None:
            self.statements.append(" ".join(sql.split()))
            if params:
                self.current_table = params[0]

        async def fetchall(self):
            existing = {
                "weibo": [("图片",), ("转发微博",)],
                "huya": [("room_pic",)],
                "xhs": [],
            }
            return existing[self.current_table]

    cursor = FakeCursor()
    await _migrate_mysql_columns(cursor)

    alters = [statement for statement in cursor.statements if statement.startswith("ALTER TABLE")]
    assert not any("`weibo` ADD COLUMN `图片`" in statement for statement in alters)
    assert any("`weibo` ADD COLUMN `正文结构`" in statement for statement in alters)
    assert any("`huya` ADD COLUMN `avatar_url`" in statement for statement in alters)
    assert any("`xhs` ADD COLUMN `note_id`" in statement for statement in alters)


@pytest.mark.asyncio
async def test_mysql_schema_migration_tolerates_concurrent_duplicate_column() -> None:
    class RacingCursor:
        current_table = ""

        async def execute(self, sql, params=None) -> None:
            if params:
                self.current_table = params[0]
            elif sql.lstrip().startswith("ALTER TABLE"):
                raise aiomysql.OperationalError(1060, "Duplicate column name")

        async def fetchall(self):
            return []

    await _migrate_mysql_columns(RacingCursor())


@pytest.mark.asyncio
async def test_sqlite_fallback_write_and_outbox_are_committed_together(tmp_path) -> None:
    async with aiosqlite.connect(tmp_path / "fallback.db") as conn:
        conn.row_factory = aiosqlite.Row
        await db_module.AsyncDatabase()._init_tables(conn)
        await db_module._sqlite_update_with_outbox(
            conn,
            "INSERT INTO douyu (room, name, is_live) VALUES (:room, :name, :is_live)",
            {"room": "1", "name": "主播", "is_live": "1"},
        )

        rows = await db_module._sqlite_query(conn, "SELECT room, name, is_live FROM douyu")
        events = await db_module._load_outbox(conn)

    assert rows == [("1", "主播", "1")]
    assert events[0]["operation"] == "upsert"
    assert events[0]["row_data"]["room"] == "1"


@pytest.mark.asyncio
async def test_sqlite_fallback_delete_records_idempotent_delete(tmp_path) -> None:
    async with aiosqlite.connect(tmp_path / "fallback.db") as conn:
        conn.row_factory = aiosqlite.Row
        await db_module.AsyncDatabase()._init_tables(conn)
        await conn.execute(
            "INSERT INTO douyu (room, name, is_live) VALUES ('1', '主播', '1')"
        )
        await conn.commit()

        await db_module._sqlite_update_with_outbox(
            conn,
            "DELETE FROM douyu WHERE room=:pk",
            {"pk": "1"},
        )
        events = await db_module._load_outbox(conn)

    assert events[0]["operation"] == "delete"
    assert events[0]["pk_value"] == "1"


@pytest.mark.asyncio
async def test_sqlite_fallback_rejects_untracked_conditional_delete(tmp_path) -> None:
    async with aiosqlite.connect(tmp_path / "fallback.db") as conn:
        conn.row_factory = aiosqlite.Row
        await db_module.AsyncDatabase()._init_tables(conn)
        await conn.execute(
            "INSERT INTO douyu (room, name, is_live) VALUES ('1', '主播', '1')"
        )
        await conn.commit()

        with pytest.raises(ValueError, match="缺少主键参数"):
            await db_module._sqlite_update_with_outbox(
                conn,
                "DELETE FROM douyu WHERE room='1'",
                None,
            )
        rows = await db_module._sqlite_query(conn, "SELECT room FROM douyu")

    assert rows == [("1",)]


@pytest.mark.asyncio
async def test_sqlite_fallback_full_delete_records_clear_event(tmp_path) -> None:
    async with aiosqlite.connect(tmp_path / "fallback.db") as conn:
        conn.row_factory = aiosqlite.Row
        await db_module.AsyncDatabase()._init_tables(conn)
        await db_module._sqlite_update_with_outbox(conn, "DELETE FROM task_run_history", None)
        events = await db_module._load_outbox(conn)

    assert events[0]["operation"] == "clear"
    assert events[0]["pk_value"] is None


@pytest.mark.asyncio
async def test_empty_mysql_is_seeded_from_existing_sqlite(monkeypatch, tmp_path) -> None:
    await db_module.close_shared_connection()
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "seed.db")
    monkeypatch.setattr(db_module, "_start_maintenance_task", lambda: None)
    pool = object()
    copied = []

    async def fake_create(settings):
        return pool

    async def no_op(*args, **kwargs):
        return None

    async def fake_replace(target_pool, tables):
        copied.append((target_pool, tables))

    monkeypatch.setattr(db_module, "create_mysql_pool", fake_create)
    monkeypatch.setattr(db_module, "initialize_mysql_schema", no_op)
    monkeypatch.setattr(db_module, "mysql_tables_empty", lambda target: _async_result(True))
    monkeypatch.setattr(db_module, "replace_mysql_tables", fake_replace)
    monkeypatch.setattr(db_module, "close_mysql_pool", no_op)

    conn = await db_module._ensure_shared_connection()
    await conn.execute("INSERT INTO douyu (room, name, is_live) VALUES ('1', '主播', '1')")
    await conn.commit()
    config = AppConfig(
        mysql_enabled=True,
        mysql_host="db",
        mysql_user="monitor",
        mysql_database="webmoniter",
    )
    try:
        status = await db_module.reconfigure_database(config, force=True)
    finally:
        await db_module.close_shared_connection()

    assert status["active_backend"] == "mysql"
    assert copied[0][0] is pool
    assert copied[0][1]["douyu"][0]["room"] == "1"


async def _async_result(value):
    return value


@pytest.mark.asyncio
async def test_mysql_connection_failure_keeps_sqlite_available(monkeypatch, tmp_path) -> None:
    await db_module.close_shared_connection()
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "fallback.db")
    monkeypatch.setattr(db_module, "_start_maintenance_task", lambda: None)

    async def fail_connect(settings):
        raise OSError("unreachable")

    async def no_op(*args, **kwargs):
        return None

    monkeypatch.setattr(db_module, "create_mysql_pool", fail_connect)
    monkeypatch.setattr(db_module, "close_mysql_pool", no_op)
    config = AppConfig(
        mysql_enabled=True,
        mysql_host="db",
        mysql_user="monitor",
        mysql_database="webmoniter",
    )
    try:
        status = await db_module.reconfigure_database(config, force=True)
    finally:
        await db_module.close_shared_connection()

    assert status["active_backend"] == "sqlite"
    assert status["sync_state"] == "fallback"
    assert status["sqlite_healthy"] is True
