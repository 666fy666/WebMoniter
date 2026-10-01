"""主流程就绪后的有界、可取消 Web 资源预热。"""

import asyncio
import logging
import time

from src.core.http import get_certifi_ssl_context
from src.storage.database import AsyncDatabase
from src.web.data_support import _weibo_page_ids
from src.web.templating import templates

logger = logging.getLogger(__name__)
WARMUP_STAGE_TIMEOUT_SECONDS = 10


def _warm_templates() -> None:
    for name in (
        "base.html",
        "partials/icon.html",
        "partials/sidebar.html",
        "login.html",
        "config.html",
        "tasks.html",
        "data.html",
        "logs.html",
    ):
        templates.env.get_template(name)


async def _warm_weibo_dates() -> None:
    async with AsyncDatabase() as db:
        rows = await db.execute_query("SELECT UID, 文本 FROM weibo LIMIT :limit", {"limit": 4096})
    await asyncio.to_thread(_weibo_page_ids, rows, 0, 25)


async def warmup_web_resources() -> None:
    for name, warm in (
        ("templates", lambda: asyncio.to_thread(_warm_templates)),
        ("tls", lambda: asyncio.to_thread(get_certifi_ssl_context)),
        ("weibo_dates", _warm_weibo_dates),
    ):
        started = time.perf_counter()
        try:
            await asyncio.wait_for(warm(), timeout=WARMUP_STAGE_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Web 预热失败 stage=%s error=%s", name, type(exc).__name__)
        else:
            logger.info(
                "Web 预热完成 stage=%s duration_ms=%.1f",
                name,
                (time.perf_counter() - started) * 1000,
            )


async def stop_web_warmup(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
