"""Shared Jinja template environment for Web routes."""

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="web/templates")
