"""Tests for shared SQLite connection reference tracking."""

import pytest

import src.storage.database as db_module
from src.storage.database import AsyncDatabase


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    """Use a temp DB path; tests must call reset helper when done."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    return db_path


async def _reset_shared_db_state() -> None:
    await db_module.close_shared_connection()


@pytest.mark.asyncio
async def test_shared_ref_count_tracks_active_instances(isolated_db):
    db1 = AsyncDatabase()
    db2 = AsyncDatabase()
    try:
        await db1.initialize()
        await db2.initialize()

        assert db_module._connection_ref_count == 2
        assert db1._conn is db2._conn

        await db1.close()
        assert db_module._connection_ref_count == 1

        await db2.close()
        assert db_module._connection_ref_count == 0
    finally:
        await _reset_shared_db_state()


@pytest.mark.asyncio
async def test_reconnect_updates_all_active_instances(isolated_db):
    db1 = AsyncDatabase()
    db2 = AsyncDatabase()
    try:
        await db1.initialize()
        await db2.initialize()

        old_conn = db_module._shared_connection
        assert db_module._connection_ref_count == 2
        assert len(db_module._active_shared_databases) == 2

        await db1._reconnect()

        assert db_module._connection_ref_count == 2
        assert db_module._shared_connection is not old_conn
        assert db1._conn is db_module._shared_connection
        assert db2._conn is db_module._shared_connection

        await db1.close()
        await db2.close()
    finally:
        await _reset_shared_db_state()


@pytest.mark.asyncio
async def test_double_initialize_does_not_inflate_ref_count(isolated_db):
    db = AsyncDatabase()
    try:
        await db.initialize()
        await db.initialize()

        assert db_module._connection_ref_count == 1

        await db.close()
        assert db_module._connection_ref_count == 0
    finally:
        await _reset_shared_db_state()
