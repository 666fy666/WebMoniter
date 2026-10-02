"""Authentication/CSRF dependencies and bounded request protection."""

import hmac
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse

from src.web.auth import check_login


def require_login(request: Request) -> str:
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        raise HTTPException(401, "请先登录")
    return session_id


class RequestSecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        if scope["path"].startswith("/api/") and scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            session = scope.get("session", {})
            token = session.get("csrf", "")
            supplied = request.headers.get("x-csrf-token", "")
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host"):
                return await JSONResponse({"error": "来源校验失败"}, status_code=403)(
                    scope, receive, send
                )
            if not token or not hmac.compare_digest(token.encode(), supplied.encode()):
                return await JSONResponse({"error": "请求校验失败，请刷新页面"}, status_code=403)(
                    scope, receive, send
                )
        length = request.headers.get("content-length", "0")
        try:
            too_large = int(length) > 2 * 1024 * 1024
        except ValueError:
            too_large = True
        if too_large:
            return await JSONResponse({"error": "请求内容过大"}, status_code=413)(
                scope, receive, send
            )
        consumed = 0

        async def limited_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get("body", b""))
            if consumed > 2 * 1024 * 1024:
                raise HTTPException(413, "请求内容过大")
            return message

        await self.app(scope, limited_receive, send)
