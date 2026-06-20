"""HTTP client helpers shared across tasks and monitors."""

import logging
import ssl

import aiohttp
import certifi

logger = logging.getLogger(__name__)


def create_certifi_connector(**kwargs) -> aiohttp.TCPConnector:
    """Create an aiohttp connector that verifies TLS with certifi's CA bundle."""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    return aiohttp.TCPConnector(ssl=ssl_context, **kwargs)


async def fetch_hitokoto_quote(
    session: aiohttp.ClientSession,
    *,
    timeout: float = 30,
) -> str:
    """获取一言语录，失败时返回空格占位。"""
    try:
        async with session.get(
            "https://v1.hitokoto.cn/",
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            if resp.status == 200:
                hitokoto = await resp.json()
                return (
                    f'\n{hitokoto.get("hitokoto", "")} —— {hitokoto.get("from", "")}\n'
                )
    except Exception as exc:
        logger.debug("获取一言语录失败: %s", exc)
    return " "
