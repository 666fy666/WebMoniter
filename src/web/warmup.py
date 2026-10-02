"""主流程就绪后的有界、可取消 Web 资源预热。"""

import asyncio
import logging
import time

from src.core.http import get_certifi_ssl_context

logger = logging.getLogger(__name__)
WARMUP_STAGE_TIMEOUT_SECONDS = 10


async def warmup_web_resources() -> None:
    for name, warm in (("tls", lambda: asyncio.to_thread(get_certifi_ssl_context)),):
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
