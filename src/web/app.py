"""FastAPI application assembly for the Web UI and API."""

import secrets
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src.core.paths import WEB_UI_STATIC_DIR
from src.web.routers import assistant, auth, config, data, logs, pages, tasks, webhooks

SECRET_KEY = secrets.token_urlsafe(32)


def create_web_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Web任务系统", description="Web任务系统管理界面")
    app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

    app.mount("/static", StaticFiles(directory=str(WEB_UI_STATIC_DIR)), name="static")

    weibo_img_dir = Path("data/weibo")
    weibo_img_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/weibo_img", StaticFiles(directory=str(weibo_img_dir)), name="weibo_img")

    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(tasks.router)
    app.include_router(config.router)
    app.include_router(data.router)
    app.include_router(logs.router)
    app.include_router(assistant.router)
    app.include_router(webhooks.router)
    return app
