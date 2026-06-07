"""HTTP client helpers shared across tasks and monitors."""

import ssl

import aiohttp
import certifi


def create_certifi_connector(**kwargs) -> aiohttp.TCPConnector:
    """Create an aiohttp connector that verifies TLS with certifi's CA bundle."""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    return aiohttp.TCPConnector(ssl=ssl_context, **kwargs)
