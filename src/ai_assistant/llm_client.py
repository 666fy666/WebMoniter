"""LLM 客户端 - 支持主流厂商 OpenAI 兼容 API"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from src.ai_assistant.config import get_ai_config

logger = logging.getLogger(__name__)

# 尝试导入 openai，若无则回退到 httpx
try:
    from openai import AsyncOpenAI, OpenAI

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
    raise RuntimeError("请安装 openai 或 httpx：uv sync")


def _create_async_client():
    """创建 OpenAI 兼容客户端（异步）"""
    cfg = get_ai_config()
    base = cfg.get_api_base()
    key = cfg.get_api_key()
    if HAS_OPENAI:
        return AsyncOpenAI(api_key=key or "sk-placeholder", base_url=base if base else None)
    if HAS_HTTPX:
        return _AsyncHttpClient(base, key)
    raise RuntimeError("请安装 openai 或 httpx：uv sync")


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

    async def chat_completions_create_stream(self, **kwargs: Any) -> AsyncIterator[str]:
        """流式调用，逐块 yield 文本内容（OpenAI SSE 格式）。"""
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": kwargs.get("model", "gpt-4o-mini"),
            "messages": kwargs.get("messages", []),
            "stream": True,
        }
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        j = json.loads(data)
                        content = j.get("choices", [{}])[0].get("delta", {}).get("content") or ""
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass


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


async def chat_completion_stream(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> AsyncIterator[str]:
    """
    流式调用 LLM，逐块 yield 助手回复的文本内容。
    """
    cfg = get_ai_config()
    model = model or cfg.model
    client = _create_async_client()
    try:
        if HAS_OPENAI:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return
        async for chunk in client.chat_completions_create_stream(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk
    except Exception as e:
        logger.error("LLM 流式调用失败: %s", e)
        raise


async def compress_text_with_llm(text: str, max_bytes: int) -> str | None:
    """
    使用 LLM 将文本压缩到指定字节数以内，保留核心语义。
    用于各推送渠道超限时用摘要替代简单截断（企业微信、钉钉、飞书、Telegram 等）。

    Args:
        text: 原始文本
        max_bytes: 压缩后 UTF-8 编码的最大字节数

    Returns:
        压缩后的文本，若 LLM 调用失败或超时则返回 None
    """
    # 目标字符数（中文约 3 字节/字，预留余量）
    max_chars = max(max_bytes // 2, 20)

    prompt = f"""请将以下文本压缩为简短摘要，要求：
1. 压缩后的文字不超过 {max_chars} 个字符（约 {max_bytes} 字节以内）
2. 保留核心观点、关键信息，可省略冗余表述
3. 使用简洁自然的汉语，直接输出压缩后的文本，不要加引号或多余说明

原文：
{text}"""

    try:
        result = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=256,
        )
        if not result or not result.strip():
            return None
        result = result.strip()
        # 校验长度，若仍超限则返回 None（调用方将回退到截断）
        if len(result.encode("utf-8")) > max_bytes:
            logger.warning(
                "LLM 压缩结果仍超限（%d > %d 字节），将使用截断",
                len(result.encode("utf-8")),
                max_bytes,
            )
            return None
        return result
    except Exception as e:
        logger.warning("LLM 压缩文本失败，将使用截断: %s", e)
        return None
