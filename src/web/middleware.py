"""Web 响应耗时与动态 API 缓存控制，不记录请求数据或查询参数。"""

import logging
import time

from starlette.datastructures import MutableHeaders
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class WebGZipMiddleware:
    def __init__(self, app: ASGIApp, minimum_size: int = 1024, compresslevel: int = 5) -> None:
        self.app = app
        self.compressed_app = GZipMiddleware(
            app, minimum_size=minimum_size, compresslevel=compresslevel
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path.startswith(("/weibo_img/", "/static/images/")):
            await self.app(scope, receive, send)
        else:
            await self.compressed_app(scope, receive, send)


class WebPerformanceMiddleware:
    def __init__(self, app: ASGIApp, slow_request_seconds: float = 0.5) -> None:
        self.app = app
        self.slow_request_seconds = slow_request_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()

        async def send_response(message: Message) -> None:
            if message["type"] == "http.response.start":
                elapsed = time.perf_counter() - started
                headers = MutableHeaders(scope=message)
                headers["Server-Timing"] = f"app;dur={elapsed * 1000:.1f}"
                if scope.get("path", "").startswith("/api/"):
                    headers["Cache-Control"] = "no-store"
                if elapsed >= self.slow_request_seconds:
                    route = scope.get("route")
                    logger.warning(
                        "Web 慢请求 method=%s route=%s status=%s duration_ms=%.1f",
                        scope["method"],
                        getattr(route, "path", "unmatched"),
                        message["status"],
                        elapsed * 1000,
                    )
            await send(message)

        await self.app(scope, receive, send_response)
