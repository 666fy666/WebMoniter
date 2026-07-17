"""HTML page routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.core.paths import WEB_UI_STATIC_DIR
from src.web.auth import check_login
from src.web.templating import templates

router = APIRouter()
_CONFIG_JS_PATH = WEB_UI_STATIC_DIR / "js" / "config.js"


def _config_js_version() -> str:
    """以文件版本生成缓存键，前端脚本更新后 URL 必然变化。"""
    try:
        return str(_CONFIG_JS_PATH.stat().st_mtime_ns)
    except OSError:
        return "1"


def _page_context(request: Request, page_title: str, active_nav: str) -> dict:
    return {
        "request": request,
        "page_title": page_title,
        "active_nav": active_nav,
        "config_js_version": _config_js_version(),
    }


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页：已登录则配置页，未登录则登录页"""
    session_id = request.session.get("session_id")
    if check_login(session_id):
        return templates.TemplateResponse(
            "config.html", _page_context(request, "配置管理", "config")
        )
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    session_id = request.session.get("session_id")
    if check_login(session_id):
        return templates.TemplateResponse(
            "config.html", _page_context(request, "配置管理", "config")
        )
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """配置管理页面"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("config.html", _page_context(request, "配置管理", "config"))


@router.get("/data", response_class=HTMLResponse)
async def data_page(request: Request):
    """数据展示页面"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("data.html", _page_context(request, "数据展示", "data"))


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """日志展示页面"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("logs.html", _page_context(request, "日志查看", "logs"))


@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    """任务管理页面"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("tasks.html", _page_context(request, "任务管理", "tasks"))
