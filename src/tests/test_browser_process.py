import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from src.core import browser_process


@pytest.mark.asyncio
async def test_browser_timeout_kills_process_group_and_releases_slot(monkeypatch):
    process = type("Process", (), {"pid": 12345, "returncode": None})()

    async def communicate(data):
        assert json.loads(data)["payload"]["password"] == "test-only-secret"
        await asyncio.Event().wait()

    process.communicate = communicate
    process.wait = AsyncMock(return_value=0)
    spawn = AsyncMock(return_value=process)
    killed = []
    monkeypatch.setattr(browser_process.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(browser_process.os, "killpg", lambda pid, sig: killed.append(pid))
    monkeypatch.setattr(browser_process, "_slot", asyncio.Semaphore(1))
    with pytest.raises(TimeoutError):
        await browser_process.run_browser(
            "rainyun_account", {"password": "test-only-secret"}, timeout=0.01
        )
    assert killed == [12345]
    assert "test-only-secret" not in str(spawn.call_args)
    assert not browser_process._slot.locked()


@pytest.mark.asyncio
async def test_worker_failure_is_typed_and_does_not_expose_stderr(monkeypatch):
    process = type("Process", (), {"pid": 12345, "returncode": 0})()
    process.communicate = AsyncMock(
        return_value=(b'{"ok":false,"kind":"IkuuuLoginRejectedError"}', None)
    )
    process.wait = AsyncMock(return_value=0)
    monkeypatch.setattr(
        browser_process.asyncio, "create_subprocess_exec", AsyncMock(return_value=process)
    )
    monkeypatch.setattr(browser_process.os, "killpg", lambda *args: None)
    monkeypatch.setattr(browser_process, "_slot", asyncio.Semaphore(1))
    with pytest.raises(browser_process.BrowserProcessError) as error:
        await browser_process.run_browser("ikuuu_login", {})
    assert error.value.kind == "IkuuuLoginRejectedError"
