"""LLM 客户端 - 支持主流厂商 OpenAI 兼容 API"""

import json
import logging
from typing import Any

from src.ai_assistant.config import get_ai_config

logger = logging.getLogger(__name__)

# 尝试导入 openai，若无则回退到 httpx
try:
    from openai import OpenAI, AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


def _create_client():
    """创建 OpenAI 兼容客户端（同步）"""
    cfg = get_ai_config()
    base = cfg.get_api_base()
    key = cfg.get_api_key()
    if HAS_OPENAI:
        return OpenAI(api_key=key or "sk-placeholder", base_url=base if base else None)
    if HAS_HTTPX:
        return _HttpClient(base, key)
    raise RuntimeError("请安装 openai 或 httpx：uv sync --extra ai")


def _create_async_client():
    """创建 OpenAI 兼容客户端（异步）"""
    cfg = get_ai_config()
    base = cfg.get_api_base()
    key = cfg.get_api_key()
    if HAS_OPENAI:
        return AsyncOpenAI(api_key=key or "sk-placeholder", base_url=base if base else None)
    if HAS_HTTPX:
        return _AsyncHttpClient(base, key)
    raise RuntimeError("请安装 openai 或 httpx：uv sync --extra ai")


class _HttpClient:
    """基于 httpx 的同步 HTTP 客户端，兼容 OpenAI API 格式"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or "sk-placeholder"

    def chat_completions_create(self, **kwargs: Any) -> Any:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": kwargs.get("model", "gpt-4o-mini"),
            "messages": kwargs.get("messages", []),
            "stream": kwargs.get("stream", False),
        }
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()


class _AsyncHttpClient:
    """基于 httpx 的异步 HTTP 客户端"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or "sk-placeholder"

    async def chat_completions_create(self, **kwargs: Any) -> Any:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": kwargs.get("model", "gpt-4o-mini"),
            "messages": kwargs.get("messages", []),
            "stream": kwargs.get("stream", False),
        }
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """
    调用 LLM 完成对话，返回 assistant 的 content 文本。
    """
    cfg = get_ai_config()
    model = model or cfg.model
    client = _create_async_client()
    try:
        if HAS_OPENAI:
            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return (resp.choices[0].message.content or "").strip()
        # 自定义 HttpClient
        resp = await client.chat_completions_create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choices = resp.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content") or ""
            return content.strip()
        return ""
    except Exception as e:
        logger.error("LLM 调用失败: %s", e)
        raise
