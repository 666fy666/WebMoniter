"""FastAPI application assembly for the Web UI and API."""

import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from src.core.paths import SESSION_SECRET_FILE, WEB_UI_STATIC_DIR, WEIBO_IMG_DIR
from src.jobs.execution import get_execution_service
from src.jobs.registry import discover_and_import
from src.web.auth import WEB_SESSION_MAX_AGE_SECONDS
from src.web.middleware import WebGZipMiddleware, WebPerformanceMiddleware
from src.web.routers import config, data, v1
from src.web.security import RequestSecurityMiddleware, require_login
from src.web.static_files import (
    STATIC_ASSET_VERSION,
    CachedStaticFiles,
    VersionedStaticFiles,
)


def _get_or_create_session_secret() -> str:
    """持久化 Session 密钥，避免重启后全员掉线。"""
    if SESSION_SECRET_FILE.is_file():
        stored = SESSION_SECRET_FILE.read_text(encoding="utf-8").strip()
        if stored:
            return stored
    secret = secrets.token_urlsafe(32)
    SESSION_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_SECRET_FILE.write_text(secret, encoding="utf-8")
    SESSION_SECRET_FILE.chmod(0o600)
    return secret


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    from src.web.auth import load_auth

    await asyncio.to_thread(load_auth)
    service = get_execution_service()
    await service.start()
    discover_and_import()
    try:
        yield
    finally:
        await service.stop()


FRONTEND_DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_web_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Web任务系统", description="Web任务系统管理界面", lifespan=lifespan)
    app.add_middleware(WebGZipMiddleware, minimum_size=1024, compresslevel=5)
    app.add_middleware(WebPerformanceMiddleware)
    app.add_middleware(RequestSecurityMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=_get_or_create_session_secret(),
        https_only=os.environ.get("WEBMONITER_SECURE_COOKIE", "0") == "1",
        max_age=WEB_SESSION_MAX_AGE_SECONDS,
        same_site="lax",
    )

    app.mount(
        "/static",
        VersionedStaticFiles(directory=str(WEB_UI_STATIC_DIR), asset_version=STATIC_ASSET_VERSION),
        name="static",
    )

    WEIBO_IMG_DIR.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/weibo_img",
        CachedStaticFiles(
            directory=str(WEIBO_IMG_DIR),
            short_cache_paths=(
                "profile_image.jpg",
                "avatar_large.jpg",
                "avatar_hd.jpg",
                "cover_image_phone.jpg",
            ),
        ),
        name="weibo_img",
    )

    app.include_router(v1.router)
    # Reuse platform behavior behind the authenticated, versioned API.
    for route in data.router.routes:
        if not route.path.startswith("/api/data/"):
            continue
        app.add_api_route(
            route.path.replace("/api/", "/api/v1/", 1),
            route.endpoint,
            methods=list(route.methods),
            dependencies=[Depends(require_login)],
        )
    app.add_api_route(
        "/api/v1/database/status",
        config.get_database_status_api,
        dependencies=[Depends(require_login)],
    )
    app.add_api_route(
        "/api/v1/database/test",
        config.test_database_connection_api,
        methods=["POST"],
        dependencies=[Depends(require_login)],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            {
                "error": "请求参数无效",
                "fields": [
                    {"path": ".".join(map(str, error["loc"])), "message": error["msg"]}
                    for error in exc.errors()
                ],
            },
            status_code=422,
        )

    @app.get("/health/live")
    async def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready():
        try:
            import asyncio

            from src.storage.database import _ensure_shared_connection

            async def check():
                if not await get_execution_service().healthy():
                    return False
                connection = await _ensure_shared_connection()
                await connection.execute("SELECT 1")
                return True

            healthy = await asyncio.wait_for(check(), timeout=2)
        except Exception:
            healthy = False
        return JSONResponse(
            {"status": "ready" if healthy else "starting"}, status_code=200 if healthy else 503
        )

    frontend = FRONTEND_DIST_DIR
    if (frontend / "assets").is_dir():
        app.mount("/assets", CachedStaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path == "favicon.svg" and (frontend / "favicon.svg").is_file():
            return FileResponse(frontend / "favicon.svg")
        if path.startswith(("api/", "assets/", "health/")):
            return JSONResponse({"error": "资源不存在"}, status_code=404)
        if (frontend / "index.html").is_file():
            return FileResponse(frontend / "index.html", headers={"Cache-Control": "no-cache"})
        return JSONResponse(
            {"error": "请先运行 npm ci --prefix frontend 和 npm run build --prefix frontend"},
            status_code=503,
        )

    return app
