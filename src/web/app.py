"""FastAPI application assembly for the Web UI and API."""

import secrets

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src.core.paths import SESSION_SECRET_FILE, WEB_UI_STATIC_DIR, WEIBO_IMG_DIR
from src.web.routers import auth, config, data, logs, pages, tasks
from src.web.static_files import CachedStaticFiles


def _get_or_create_session_secret() -> str:
    """持久化 Session 密钥，避免重启后全员掉线。"""
    if SESSION_SECRET_FILE.is_file():
        stored = SESSION_SECRET_FILE.read_text(encoding="utf-8").strip()
        if stored:
            return stored
    secret = secrets.token_urlsafe(32)
    SESSION_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_SECRET_FILE.write_text(secret, encoding="utf-8")
    return secret


SECRET_KEY = _get_or_create_session_secret()


def create_web_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Web任务系统", description="Web任务系统管理界面")
    app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

    app.mount("/static", StaticFiles(directory=str(WEB_UI_STATIC_DIR)), name="static")

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

    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(tasks.router)
    app.include_router(config.router)
    app.include_router(data.router)
    app.include_router(logs.router)
    return app
