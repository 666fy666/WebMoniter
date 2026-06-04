"""Shared Jinja template environment for Web routes."""

from fastapi.templating import Jinja2Templates

from src.core.paths import WEB_UI_TEMPLATES_DIR

templates = Jinja2Templates(directory=str(WEB_UI_TEMPLATES_DIR))
