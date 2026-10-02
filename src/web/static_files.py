"""Static file handlers with HTTP cache headers."""

from urllib.parse import parse_qs

from starlette.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send

STATIC_ASSET_VERSION = "5"


class CachedStaticFiles(StaticFiles):
    """StaticFiles that adds Cache-Control headers to successful responses."""

    def __init__(
        self,
        *args,
        cache_max_age: int = 31536000,
        cache_immutable: bool = True,
        short_cache_paths: tuple[str, ...] = (),
        short_cache_max_age: int = 86400,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.cache_max_age = cache_max_age
        self.cache_immutable = cache_immutable
        self.short_cache_paths = short_cache_paths
        self.short_cache_max_age = short_cache_max_age

    def _cache_control_for_path(self, path: str) -> str:
        use_short = any(marker in path for marker in self.short_cache_paths)
        max_age = self.short_cache_max_age if use_short else self.cache_max_age
        cache_control = f"public, max-age={max_age}"
        if not use_short and self.cache_immutable:
            cache_control += ", immutable"
        return cache_control

    def _cache_control_for_scope(self, scope: Scope) -> str:
        return self._cache_control_for_path(scope.get("path", ""))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await super().__call__(scope, receive, send)
            return

        cache_control = self._cache_control_for_scope(scope)

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start" and message["status"] < 400:
                headers = list(message.get("headers", []))
                headers.append((b"cache-control", cache_control.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await super().__call__(scope, receive, send_wrapper)


class VersionedStaticFiles(CachedStaticFiles):
    def __init__(self, *args, asset_version: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.asset_version = asset_version

    def _cache_control_for_scope(self, scope: Scope) -> str:
        query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        if query.get("v") == [self.asset_version]:
            return "public, max-age=31536000, immutable"
        # 无版本 URL 必须重新验证，避免更新后图片或旧脚本长期滞留。
        return "no-cache"
