"""Authentication and version API routes."""

import asyncio
import logging
import secrets

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import JSONResponse

from src.web.auth import (
    active_sessions,
    check_login,
    hash_password,
    load_auth,
    save_auth,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """登录接口"""
    auth_data = await asyncio.to_thread(load_auth)
    if username == auth_data.get("username") and verify_password(
        password, auth_data.get("password_hash", "")
    ):
        session_id = secrets.token_urlsafe(32)
        request.session["session_id"] = session_id
        active_sessions.add(session_id)
        return JSONResponse({"success": True, "message": "登录成功"})
    return JSONResponse(
        {"success": False, "message": "用户名或密码错误"}, status_code=status.HTTP_401_UNAUTHORIZED
    )


@router.post("/api/logout")
async def logout(request: Request):
    """登出接口"""
    session_id = request.session.get("session_id")
    if session_id:
        active_sessions.discard(session_id)
        request.session.clear()
    return JSONResponse({"success": True, "message": "已登出"})


@router.post("/api/change-password")
async def change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    """修改密码接口"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse(
            {"success": False, "message": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED
        )

    if new_password != confirm_password:
        return JSONResponse(
            {"success": False, "message": "两次输入的新密码不一致"}, status_code=400
        )

    if len(new_password) < 3:
        return JSONResponse(
            {"success": False, "message": "新密码长度至少为3个字符"}, status_code=400
        )

    auth_data = await asyncio.to_thread(load_auth)
    if not verify_password(old_password, auth_data.get("password_hash", "")):
        return JSONResponse({"success": False, "message": "当前密码错误"}, status_code=400)

    auth_data["password_hash"] = hash_password(new_password)
    if await asyncio.to_thread(save_auth, auth_data):
        logger.info("密码已成功修改")
        return JSONResponse({"success": True, "message": "密码修改成功"})
    return JSONResponse({"success": False, "message": "保存密码失败，请重试"}, status_code=500)


@router.get("/api/check-auth")
async def check_auth(request: Request):
    """检查认证状态"""
    session_id = request.session.get("session_id")
    if check_login(session_id):
        return JSONResponse({"authenticated": True})
    return JSONResponse({"authenticated": False}, status_code=status.HTTP_401_UNAUTHORIZED)


@router.get("/api/version")
async def get_version_api():
    """获取当前版本信息"""
    from src.version import (
        GITHUB_API_LATEST_TAG,
        GITHUB_RELEASES_URL,
        __version__,
    )

    return JSONResponse(
        {
            "version": __version__,
            "github_api_url": GITHUB_API_LATEST_TAG,
            "tags_url": GITHUB_RELEASES_URL,
        }
    )
