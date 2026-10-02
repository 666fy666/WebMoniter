"""One browser/OCR process at a time; no credentials in argv or environment."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys

_slot = asyncio.Semaphore(1)


class BrowserProcessError(RuntimeError):
    def __init__(self, kind: str):
        self.kind = kind
        super().__init__(f"浏览器执行失败（{kind}）")


async def _terminate(process: asyncio.subprocess.Process) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        elif process.returncode is None:
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/PID",
                str(process.pid),
                "/T",
                "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
    except ProcessLookupError:
        pass
    await process.wait()


async def run_browser(operation: str, payload: dict, *, timeout: float = 180) -> object:
    async with _slot:
        args = (
            [sys.executable, "--browser-worker"]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-m", "src.core.browser_worker"]
        )
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=os.name == "posix",
        )
        try:
            raw, _ = await asyncio.wait_for(
                process.communicate(
                    json.dumps({"operation": operation, "payload": payload}).encode()
                ),
                timeout=timeout,
            )
            if process.returncode or len(raw) > 1024 * 1024:
                raise BrowserProcessError("worker_exit")
            reply = json.loads(raw)
            if not reply.get("ok"):
                raise BrowserProcessError(reply.get("kind", "unknown"))
            return reply["result"]
        finally:
            # Also reap descendants if the driver failed before it could call quit().
            await asyncio.shield(_terminate(process))
