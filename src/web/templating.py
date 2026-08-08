"""Shared Jinja template environment for Web routes."""

from fastapi.templating import Jinja2Templates

from src.core.paths import WEB_UI_TEMPLATES_DIR

STATIC_ASSET_VERSION = "1"

templates = Jinja2Templates(directory=str(WEB_UI_TEMPLATES_DIR))
templates.env.globals["static_version"] = STATIC_ASSET_VERSION
