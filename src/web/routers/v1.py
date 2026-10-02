"""Typed management API. External side effects only execute in the job service."""

import asyncio
import base64
import importlib.util
import json
import secrets
import time
from collections import OrderedDict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from src.jobs.execution import QueueFullError, get_execution_service
from src.jobs.log_manager import LogManager
from src.jobs.metadata import MONITOR_SPECS, TASK_SPECS
from src.jobs.registry import MONITOR_JOBS, TASK_JOBS, run_task_with_logging
from src.settings.config import get_config
from src.web import auth, config_service
from src.web.security import require_login

router = APIRouter(prefix="/api/v1")
protected = APIRouter(dependencies=[Depends(require_login)])
_attempts: OrderedDict[str, list[float]] = OrderedDict()
_login_slot = asyncio.Semaphore(2)


def task_dependencies_available(job_id: str) -> bool:
    packages = {
        "rainyun_checkin": ("selenium", "ddddocr", "cv2"),
        "ikuuu_checkin": ("selenium", "onnxruntime", "cv2"),
        "weibo_cookie_refresh": ("selenium",),
    }
    return all(importlib.util.find_spec(name) is not None for name in packages.get(job_id, ()))


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class PasswordBody(BaseModel):
    old_password: str = Field(max_length=1024)
    new_password: str = Field(min_length=1, max_length=1024)


class ConfigBody(BaseModel):
    version: str = Field(pattern=r"^[0-9a-f]{64}$")
    config: dict | None = None
    content: str | None = Field(default=None, max_length=1024 * 1024)


@router.get("/session")
async def session(request: Request):
    request.session.setdefault("csrf", secrets.token_urlsafe(32))
    return {
        "authenticated": auth.check_login(request.session.get("session_id")),
        "csrf_token": request.session["csrf"],
    }


@router.post("/login")
async def login(request: Request, body: LoginBody):
    address = request.client.host if request.client else "unknown"
    now = time.monotonic()
    attempts = [stamp for stamp in _attempts.pop(address, []) if now - stamp < 300]
    _attempts[address] = attempts
    while len(_attempts) > 1024:
        _attempts.popitem(last=False)
    if len(attempts) >= 5:
        raise HTTPException(429, "尝试过于频繁，请五分钟后重试", headers={"Retry-After": "300"})
    attempts.append(now)
    async with _login_slot:
        try:
            credentials = await asyncio.to_thread(auth.load_auth)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        valid = await asyncio.to_thread(
            auth.verify_password, body.password, credentials["password_hash"]
        )
    if body.username != credentials["username"] or not valid:
        raise HTTPException(401, "用户名或密码错误")
    _attempts.pop(address, None)
    auth.revoke_session(request.session.get("session_id"))
    request.session.clear()
    request.session.update(session_id=secrets.token_urlsafe(32), csrf=secrets.token_urlsafe(32))
    auth.register_session(request.session["session_id"])
    return {"authenticated": True, "csrf_token": request.session["csrf"]}


@protected.post("/logout")
async def logout(request: Request):
    auth.revoke_session(request.session.get("session_id"))
    request.session.clear()
    return {"success": True}


@protected.post("/password")
async def password(request: Request, body: PasswordBody):
    async with _login_slot:
        credentials = await asyncio.to_thread(auth.load_auth)
        if not await asyncio.to_thread(
            auth.verify_password, body.old_password, credentials["password_hash"]
        ):
            raise HTTPException(400, "当前密码错误")
        credentials["password_hash"] = await asyncio.to_thread(
            auth.hash_password, body.new_password
        )
        if not await asyncio.to_thread(auth.save_auth, credentials):
            raise HTTPException(503, "密码保存失败")
    auth.replace_sessions_with(request.session["session_id"])
    return {"success": True}


@protected.get("/tasks")
async def tasks(request: Request):
    from src.jobs.registry import monitor_job_enabled, task_job_enabled

    config = get_config()
    registered = {job.job_id for job in MONITOR_JOBS + TASK_JOBS}
    scheduler = getattr(request.app.state, "scheduler", None)
    recent = await get_execution_service().list_runs(200, latest_per_job=True)
    latest = {}
    for run in recent:
        latest.setdefault(run["job_id"], run)
    result = []
    for spec in (*MONITOR_SPECS, *TASK_SPECS):
        job = scheduler.scheduler.get_job(spec.job_id) if scheduler else None
        next_time = getattr(job, "next_run_time", None)
        result.append(
            {
                "job_id": spec.job_id,
                "description": spec.description,
                "kind": spec.kind,
                "section": spec.config_section,
                "enabled": monitor_job_enabled(spec.job_id, config)
                if spec.kind == "monitor"
                else task_job_enabled(spec.job_id, config),
                "available": spec.job_id in registered and task_dependencies_available(spec.job_id),
                "next_run": next_time.isoformat() if next_time else None,
                "last_run": latest.get(spec.job_id),
            }
        )
    return {"tasks": result}


@protected.post("/tasks/{job_id}/runs", status_code=202)
async def run_task(job_id: str):
    job = next((j for j in MONITOR_JOBS + TASK_JOBS if j.job_id == job_id), None)
    if job is None:
        raise HTTPException(404, "任务不存在或依赖未安装")
    if not task_dependencies_available(job_id):
        raise HTTPException(503, "浏览器依赖未安装，请使用 full 镜像")

    async def run():
        from src.jobs.registry import monitor_job_enabled, task_job_enabled
        from src.jobs.task_outcome import TASK_SKIPPED

        current = get_config()
        enabled = (
            monitor_job_enabled(job_id, current)
            if job in MONITOR_JOBS
            else task_job_enabled(job_id, current)
        )
        if not enabled:
            return TASK_SKIPPED
        return await run_task_with_logging(job_id, job.original_run_func or job.run_func)

    try:
        return await get_execution_service().submit(job_id, run)
    except QueueFullError as exc:
        raise HTTPException(503, str(exc), headers={"Retry-After": "5"}) from exc


@protected.get("/runs")
async def runs(limit: int = Query(default=50, ge=1, le=200)):
    return {"runs": await get_execution_service().list_runs(limit)}


@protected.get("/runs/{run_id}")
async def run_status(run_id: str):
    records = await get_execution_service().list_runs(run_id=run_id)
    if not records:
        raise HTTPException(404, "执行记录不存在")
    return records[0]


@protected.get("/config/metadata")
async def config_metadata():
    return await asyncio.to_thread(config_service.metadata)


@protected.get("/config")
async def config():
    return await asyncio.to_thread(config_service.read_config)


@protected.post("/config/reveal")
async def reveal_config():
    return await asyncio.to_thread(config_service.read_config, reveal=True)


@protected.put("/config")
async def save_config(body: ConfigBody):
    if (body.config is None) == (body.content is None):
        raise HTTPException(422, "请提交配置补丁或 YAML 内容之一")
    try:
        await config_service.write_config(body.version, body.config, body.content)
    except config_service.ConfigConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        from src.settings.loader_specs import CONFIG_MAPPINGS

        mapping = {
            flat: f"{section}.{key}"
            for section, fields in CONFIG_MAPPINGS.items()
            for key, flat in fields.items()
        }
        cause = exc.__cause__
        fields = (
            [
                {
                    "path": mapping.get(str(error["loc"][0]), str(error["loc"][0])),
                    "message": "取值或类型不符合要求",
                }
                for error in cause.errors()
                if error["loc"]
            ]
            if isinstance(cause, ValidationError)
            else []
        )
        return JSONResponse(
            {"error": "配置校验或保存失败，请检查字段类型、取值和目录权限", "fields": fields},
            status_code=422,
        )
    return await asyncio.to_thread(config_service.read_config)


def read_log_chunk(path: Path, cursor: str | None, lines: int) -> dict:
    if not path.is_file():
        return {"lines": [], "cursor": None, "reset": True}
    stat = path.stat()
    identity = f"{path.name}:{stat.st_dev}:{stat.st_ino}"
    offset, reset = max(0, stat.st_size - 64 * 1024), True
    if cursor:
        try:
            old_id, old_offset = json.loads(base64.urlsafe_b64decode(cursor))
            if (
                old_id == identity
                and isinstance(old_offset, int)
                and 0 <= old_offset <= stat.st_size
            ):
                offset, reset = old_offset, False
        except (ValueError, TypeError, UnicodeError):
            raise HTTPException(400, "无效的日志游标") from None
    with path.open("rb") as source:
        source.seek(offset)
        if reset and offset:
            source.readline(64 * 1024)
        result, size = [], 0
        while len(result) < lines and size < 256 * 1024:
            line = source.readline(min(64 * 1024, 256 * 1024 - size))
            if not line:
                break
            # Retry a trailing partial line once the writer finishes it.
            if not line.endswith(b"\n") and len(line) < 64 * 1024:
                source.seek(-len(line), 1)
                break
            size += len(line)
            result.append(line.decode("utf-8", errors="replace"))
        next_offset = source.tell()
    token = base64.urlsafe_b64encode(json.dumps([identity, next_offset]).encode()).decode()
    return {"lines": result, "cursor": token, "reset": reset}


@protected.get("/logs")
async def logs(
    task: str | None = None,
    cursor: str | None = Query(default=None, max_length=512),
    lines: int = Query(default=200, ge=1, le=1000),
):
    if task and task not in {s.job_id for s in (*MONITOR_SPECS, *TASK_SPECS)}:
        raise HTTPException(404, "任务不存在")
    manager = LogManager()
    path = manager.get_task_log_file(task) if task else manager.get_log_file("main")
    return await asyncio.to_thread(read_log_chunk, path, cursor, lines)


router.include_router(protected)
