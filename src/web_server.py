"""Web服务器模块 - 提供Web界面和API接口"""

import asyncio
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src.config import get_config
from src.database import AsyncDatabase
from src.job_registry import (
    MONITOR_JOBS,
    TASK_JOBS,
    discover_and_import,
    run_task_with_logging,
)
from src.job_metadata import get_job_description as _get_job_description
from src.web_auth import (
    active_sessions,
    check_login,
    hash_password,
    load_auth,
    save_auth,
    verify_password,
)
from src.web_config_io import (
    RUAMEL_AVAILABLE,
    RUAMEL_YAML,
    _apply_config_patch,
    _merge_and_dump_config,
    _validate_and_save_config,
)
from src.web_data import (
    PLATFORM_CONFIG,
    PLATFORM_PRIMARY_KEY,
    VALID_PLATFORMS,
    _PLATFORM_LIST_SQL,
    _PLATFORM_LIST_SQL_HUYA_BASIC,
    _PLATFORM_SELECT,
    _parse_weibo_created_at,
    _row_to_item,
)

logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(title="Web任务系统", description="Web任务系统管理界面")

# 会话密钥
SECRET_KEY = secrets.token_urlsafe(32)


# 添加会话中间件
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# 模板目录
templates = Jinja2Templates(directory="web/templates")

# 静态文件目录
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# 微博相关静态资源目录（用于暴露 data/weibo 下的图片，如封面图）
# 只负责将本地文件映射为 HTTP 访问路径，不做权限控制
WEIBO_IMG_DIR = Path("data/weibo")
WEIBO_IMG_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/weibo_img", StaticFiles(directory=str(WEIBO_IMG_DIR)), name="weibo_img")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页：已登录则配置页，未登录则登录页"""
    session_id = request.session.get("session_id")
    if check_login(session_id):
        return templates.TemplateResponse("config.html", {"request": request})
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    session_id = request.session.get("session_id")
    if check_login(session_id):
        return templates.TemplateResponse("config.html", {"request": request})
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/api/login")
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


@app.post("/api/logout")
async def logout(request: Request):
    """登出接口"""
    session_id = request.session.get("session_id")
    if session_id:
        active_sessions.discard(session_id)
        request.session.clear()
    return JSONResponse({"success": True, "message": "已登出"})


@app.post("/api/change-password")
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

    # 验证新密码和确认密码是否一致
    if new_password != confirm_password:
        return JSONResponse(
            {"success": False, "message": "两次输入的新密码不一致"}, status_code=400
        )

    # 验证新密码长度
    if len(new_password) < 3:
        return JSONResponse(
            {"success": False, "message": "新密码长度至少为3个字符"}, status_code=400
        )

    # 验证旧密码
    auth_data = await asyncio.to_thread(load_auth)
    if not verify_password(old_password, auth_data.get("password_hash", "")):
        return JSONResponse({"success": False, "message": "当前密码错误"}, status_code=400)

    # 更新密码
    auth_data["password_hash"] = hash_password(new_password)
    if await asyncio.to_thread(save_auth, auth_data):
        logger.info("密码已成功修改")
        return JSONResponse({"success": True, "message": "密码修改成功"})
    else:
        return JSONResponse({"success": False, "message": "保存密码失败，请重试"}, status_code=500)


@app.get("/api/check-auth")
async def check_auth(request: Request):
    """检查认证状态"""
    session_id = request.session.get("session_id")
    if check_login(session_id):
        return JSONResponse({"authenticated": True})
    return JSONResponse({"authenticated": False}, status_code=status.HTTP_401_UNAUTHORIZED)


@app.get("/api/version")
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


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """配置管理页面"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("config.html", {"request": request})


@app.get("/data", response_class=HTMLResponse)
async def data_page(request: Request):
    """数据展示页面"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("data.html", {"request": request})


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """日志展示页面"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("logs.html", {"request": request})


@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    """任务管理页面"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("tasks.html", {"request": request})


@app.get("/api/tasks")
async def get_tasks_api(request: Request):
    """获取所有注册的任务列表"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        # 确保任务已被发现和导入
        discover_and_import()

        tasks = []

        # 添加监控任务
        for job in MONITOR_JOBS:
            tasks.append(
                {
                    "job_id": job.job_id,
                    "trigger": job.trigger,
                    "type": "monitor",
                    "type_label": "监控任务",
                    "description": _get_job_description(job.job_id),
                }
            )

        # 添加定时任务
        for job in TASK_JOBS:
            tasks.append(
                {
                    "job_id": job.job_id,
                    "trigger": job.trigger,
                    "type": "task",
                    "type_label": "定时任务",
                    "description": _get_job_description(job.job_id),
                }
            )

        return JSONResponse({"success": True, "tasks": tasks})
    except Exception as e:
        logger.error("获取任务列表失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/tasks/{task_id}/run")
async def run_task_api(request: Request, task_id: str):
    """手动触发执行指定任务"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        # 确保任务已被发现和导入
        discover_and_import()

        # 查找任务
        all_jobs = MONITOR_JOBS + TASK_JOBS
        target_job = None
        for job in all_jobs:
            if job.job_id == task_id:
                target_job = job
                break

        if target_job is None:
            return JSONResponse({"error": f"任务 {task_id} 不存在"}, status_code=404)

        # 异步执行任务（使用原始函数，绕过"当天已运行则跳过"检查）
        logger.info("手动触发任务: %s", task_id)
        try:
            # 优先使用原始函数（不检查当天是否已运行），如果没有则使用包装后的函数
            run_func = target_job.original_run_func or target_job.run_func
            await run_task_with_logging(task_id, run_func)
            logger.info("任务 %s 手动执行完成", task_id)
            return JSONResponse(
                {
                    "success": True,
                    "message": f"任务 {task_id} 执行成功",
                }
            )
        except Exception as e:
            logger.error("任务 %s 执行失败: %s", task_id, e, exc_info=True)
            return JSONResponse(
                {
                    "success": False,
                    "message": f"任务执行失败: {str(e)}",
                },
                status_code=500,
            )
    except Exception as e:
        logger.error("触发任务失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/config")
async def get_config_api(request: Request, format: str = "json"):
    """获取配置文件内容"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        config_path = Path("config.yml")
        if not config_path.exists():
            return JSONResponse({"error": "配置文件不存在"}, status_code=404)

        # 如果请求YAML格式，直接返回文本
        if format == "yaml":
            content = await asyncio.to_thread(lambda: config_path.read_text(encoding="utf-8"))
            return JSONResponse({"content": content})

        # 否则返回JSON格式
        def _read_config_json():
            with open(config_path, encoding="utf-8") as f:
                return yaml.safe_load(f)

        yaml_data = await asyncio.to_thread(_read_config_json)
        return JSONResponse({"config": yaml_data})
    except Exception as e:
        logger.error("读取配置文件失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/config")
async def save_config_api(request: Request):
    """保存配置文件"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        # 尝试获取JSON格式的配置数据
        try:
            json_data = await request.json()

            # 如果提供了content字段（YAML文本），直接使用
            if "content" in json_data:
                yaml_content = json_data["content"]
                # 验证YAML格式
                try:
                    yaml.safe_load(yaml_content)
                except yaml.YAMLError as e:
                    return JSONResponse({"error": f"YAML格式错误: {str(e)}"}, status_code=400)
            else:
                config_data = json_data.get("config")
                if config_data is None:
                    # 如果没有config字段，尝试直接使用请求体
                    config_data = json_data

                if not config_data:
                    return JSONResponse({"error": "配置数据为空"}, status_code=400)

                # 尝试保留原始YAML文件的注释
                config_path = Path("config.yml")
                if RUAMEL_AVAILABLE and config_path.exists():
                    try:
                        # 使用 ruamel.yaml 读取原始文件（保留注释）
                        ruamel_yaml = RUAMEL_YAML()
                        ruamel_yaml.preserve_quotes = True
                        ruamel_yaml.width = 4096  # 设置宽度以避免换行
                        ruamel_yaml.indent(mapping=2, sequence=4, offset=2)  # 设置缩进
                        ruamel_yaml.default_flow_style = False  # 不使用流式风格
                        ruamel_yaml.allow_unicode = True  # 允许Unicode

                        with open(config_path, encoding="utf-8") as f:
                            original_yaml = ruamel_yaml.load(f)

                        if original_yaml is None:
                            # 如果文件为空，使用新配置
                            original_yaml = {}

                        # 更新配置数据
                        def update_dict(target, source):
                            """递归更新字典，保留原始结构。空列表 cookies/accounts 不写入，避免污染 YAML。"""
                            from ruamel.yaml.comments import CommentedSeq

                            for key, value in source.items():
                                # 不写入空的 cookies 或 accounts，避免在错误位置产生 cookies: [] / accounts: []
                                if (
                                    key in ("cookies", "accounts")
                                    and isinstance(value, list)
                                    and len(value) == 0
                                ):
                                    if key in target and isinstance(target[key], list):
                                        del target[key]
                                    continue
                                # push_channels 是字符串列表，直接替换（包括空列表）
                                # 使用 flow style（["a", "b"]）避免 block style 缩进问题
                                if key == "push_channels":
                                    new_list = CommentedSeq(value if value else [])
                                    new_list.fa.set_flow_style()  # 强制使用 flow style
                                    target[key] = new_list
                                    continue
                                if key not in target:
                                    # 新键，直接添加
                                    target[key] = value
                                elif isinstance(target[key], dict) and isinstance(value, dict):
                                    # 都是字典，递归更新
                                    update_dict(target[key], value)
                                elif isinstance(target[key], list) and isinstance(value, list):
                                    # 对于列表，尝试智能合并以保留注释
                                    # 对于 push_channel，使用 name 字段匹配
                                    if (
                                        key == "push_channel"
                                        and len(target[key]) > 0
                                        and len(value) > 0
                                    ):
                                        # 创建以 name 为键的映射，记录原始位置
                                        existing_map = {}
                                        for idx, item in enumerate(target[key]):
                                            if isinstance(item, dict) and "name" in item:
                                                existing_map[item["name"]] = idx

                                        # 收集新列表中的所有 name
                                        new_names = {
                                            item.get("name")
                                            for item in value
                                            if isinstance(item, dict) and "name" in item
                                        }

                                        # 更新或添加通道
                                        for new_item in value:
                                            if isinstance(new_item, dict) and "name" in new_item:
                                                name = new_item["name"]
                                                if name in existing_map:
                                                    # 更新现有通道（保留原始位置和注释）
                                                    idx = existing_map[name]
                                                    update_dict(target[key][idx], new_item)
                                                else:
                                                    # 添加新通道到末尾
                                                    target[key].append(new_item)

                                        # 移除已删除的通道（保留顺序和注释）
                                        target[key][:] = [
                                            item
                                            for item in target[key]
                                            if not isinstance(item, dict)
                                            or "name" not in item
                                            or item["name"] in new_names
                                        ]
                                    else:
                                        # 其他列表，直接替换
                                        target[key] = value
                                else:
                                    # 其他情况，直接替换
                                    target[key] = value

                        update_dict(original_yaml, config_data)

                        # 将更新后的配置写回字符串（保留注释）
                        from io import StringIO

                        output = StringIO()
                        ruamel_yaml.dump(original_yaml, output)
                        yaml_content = output.getvalue()
                    except Exception as e:
                        logger.warning("使用 ruamel.yaml 保留注释失败，回退到标准方式: %s", e)
                        try:
                            yaml_content = _merge_and_dump_config(config_path, config_data)
                        except Exception as ex:
                            return JSONResponse(
                                {"error": f"合并并转换YAML失败: {str(ex)}"}, status_code=400
                            )
                else:
                    # 使用标准方式（没有 ruamel.yaml 或文件不存在）：先合并再保存，避免覆盖未收集的配置
                    try:
                        yaml_content = _merge_and_dump_config(config_path, config_data)
                    except Exception as ex:
                        return JSONResponse(
                            {"error": f"合并并转换YAML失败: {str(ex)}"}, status_code=400
                        )
        except Exception:
            # 如果不是JSON，尝试获取Form数据（兼容旧版本）
            form_data = await request.form()
            content = form_data.get("content")
            if content:
                yaml_content = content
                # 验证YAML格式
                try:
                    yaml.safe_load(yaml_content)
                except yaml.YAMLError as e:
                    return JSONResponse({"error": f"YAML格式错误: {str(e)}"}, status_code=400)
            else:
                return JSONResponse({"error": "未提供配置数据"}, status_code=400)

        config_path = Path("config.yml")
        err = await _validate_and_save_config(yaml_content, config_path)
        if err:
            return err

        return JSONResponse({"success": True, "message": "配置已保存并应用"})
    except Exception as e:
        logger.error("保存配置文件失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/data/huya/images")
async def get_huya_images(request: Request, rooms: str = ""):
    """获取虎牙房间封面和头像 URL（需登录）。用于数据展示页异步加载图片。"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    room_ids = [r.strip() for r in rooms.split(",") if r.strip()]
    if not room_ids:
        return JSONResponse({"data": {}})

    try:
        async with AsyncDatabase() as db:
            placeholders = ", ".join([f":r{i}" for i in range(len(room_ids))])
            params = {f"r{i}": rid for i, rid in enumerate(room_ids)}
            sql = f"SELECT room, room_pic, avatar_url FROM huya WHERE room IN ({placeholders})"
            rows = await db.execute_query(sql, params)

        data = {
            row[0]: {
                "room_pic": (row[1] or "").strip(),
                "avatar_url": (row[2] or "").strip(),
            }
            for row in rows
        }
        return JSONResponse({"data": data})
    except Exception as e:
        logger.error("获取虎牙图片 URL 失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/data/{platform}/{item_id}")
async def get_data_item(request: Request, platform: str, item_id: str):
    """按平台与主键 ID 获取单条监控数据（需登录）。"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    if platform not in VALID_PLATFORMS:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    if platform not in _PLATFORM_SELECT:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    try:
        async with AsyncDatabase() as db:
            _, sql = _PLATFORM_SELECT[platform]
            rows = await db.execute_query(sql, {"pk": item_id})

        if not rows:
            return JSONResponse({"error": "未找到该资源"}, status_code=404)

        data = _row_to_item(platform, rows[0])
        return JSONResponse({"data": data})
    except Exception as e:
        logger.error("获取单条数据失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/data/{platform}")
async def get_table_data(
    request: Request,
    platform: str,
    page: int = 1,
    page_size: int = 100,
    include_media: bool = True,
    uid: str | None = None,
    room: str | None = None,
    id: str | None = None,
):
    """获取监控数据列表（需登录）。支持分页与按主键过滤。"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    if platform not in VALID_PLATFORMS or platform not in _PLATFORM_LIST_SQL:
        logger.warning("请求了无效的数据平台: %r，有效平台: %s", platform, sorted(VALID_PLATFORMS))
        return JSONResponse(
            {
                "error": "无效的平台",
                "platform": platform,
                "valid_platforms": sorted(VALID_PLATFORMS),
            },
            status_code=400,
        )

    _, _, filter_param_name = PLATFORM_CONFIG[platform]
    filter_param = (
        uid if filter_param_name == "uid" else (room if filter_param_name == "room" else id)
    )

    try:
        async with AsyncDatabase() as db:
            where_clause = ""
            params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
            if filter_param:
                pk_col = PLATFORM_PRIMARY_KEY[platform]
                where_clause = f" WHERE {pk_col} = :filter_val"
                params["filter_val"] = filter_param

            table_name = PLATFORM_CONFIG[platform][0]
            count_sql = f"SELECT COUNT(*) FROM {table_name}{where_clause}"
            count_params = {k: v for k, v in params.items() if k in ("filter_val",)}
            count_result = await db.execute_query(count_sql, count_params if count_params else None)
            total = count_result[0][0] if count_result else 0

            base_sql = (
                _PLATFORM_LIST_SQL_HUYA_BASIC
                if platform == "huya" and not include_media
                else _PLATFORM_LIST_SQL[platform]
            )
            if platform == "weibo":
                sql = f"{_PLATFORM_LIST_SQL[platform]}{where_clause}"
                fetch_params = {k: v for k, v in params.items() if k == "filter_val"}
                rows = await db.execute_query(sql, fetch_params if fetch_params else None)
            else:
                sql = f"{base_sql}{where_clause} LIMIT :limit OFFSET :offset"
                rows = await db.execute_query(sql, params)

        data = [_row_to_item(platform, row) for row in rows]

        if platform == "weibo" and data:
            def sort_key(item: dict):
                dt = _parse_weibo_created_at(item.get("文本"))
                if dt is None:
                    return 0.0
                return dt.timestamp()

            data.sort(key=sort_key, reverse=True)
            offset = (page - 1) * page_size
            data = data[offset : offset + page_size]

        return JSONResponse(
            {
                "data": data,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total else 0,
            }
        )
    except Exception as e:
        logger.error("获取表数据失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


def _read_log_file_sync(file_path: Path, num_lines: int) -> tuple[list, int]:
    """同步读取日志文件最后 N 行。处理文件写入时的读取冲突，带重试。返回 (最近行列表, 总行数)。"""

    def _do_read() -> tuple[list, int]:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()

            if file_size < 1024 * 1024:  # 小于1MB
                f.seek(0)
                all_lines = f.readlines()
            else:
                estimated_bytes = num_lines * 200
                read_start = max(0, file_size - estimated_bytes)
                f.seek(read_start)
                if read_start > 0:
                    f.readline()
                all_lines = f.readlines()

            if len(all_lines) > num_lines:
                recent_lines = all_lines[-num_lines:]
            else:
                recent_lines = all_lines
            return recent_lines, len(all_lines)

    def _do_read_binary() -> tuple[list, int]:
        with open(file_path, "rb") as f:
            content = f.read()
        text = content.decode("utf-8", errors="ignore")
        all_lines = text.splitlines(keepends=True)
        recent_lines = all_lines[-num_lines:] if len(all_lines) > num_lines else all_lines
        return recent_lines, len(all_lines)

    max_retries = 5
    retry_delay = 0.2

    for attempt in range(max_retries):
        try:
            return _do_read()
        except (OSError, PermissionError):
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            try:
                return _do_read_binary()
            except Exception as final_e:
                logger.error("读取日志文件失败（所有方法都失败）: %s", final_e)
                raise
        except Exception as e:
            logger.error("读取日志文件时发生未知错误: %s", e)
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise
    return [], 0  # 不应到达，满足类型与返回值约定


@app.get("/api/logs")
async def get_logs(request: Request, lines: int = 100, task: str | None = None):
    """获取日志内容。不传 task 时返回今日总日志，传 task 时返回指定任务的今日日志"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        from src.log_manager import LogManager

        log_manager = LogManager()

        if task:
            log_file = log_manager.get_task_log_file(task, date_format="%Y%m%d")
        else:
            log_file = log_manager.get_log_file("main", date_format="%Y%m%d")

        if not log_file.exists():
            return JSONResponse(
                {"logs": [], "message": "今日暂无日志" if not task else f"任务 {task} 今日暂无日志"}
            )

        try:
            recent_lines, total_lines = await asyncio.wait_for(
                asyncio.to_thread(_read_log_file_sync, log_file, lines),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            logger.error("读取日志文件超时: %s", log_file)
            return JSONResponse({"error": "读取日志超时，请稍后重试"}, status_code=504)

        return JSONResponse({"logs": recent_lines, "total_lines": total_lines})
    except Exception as e:
        logger.error("读取日志失败: %s", e, exc_info=True)
        return JSONResponse({"error": f"读取日志失败: {str(e)}"}, status_code=500)


@app.get("/api/logs/tasks")
async def get_log_tasks_list(request: Request):
    """获取今日有日志文件的任务 ID 列表，以及全部任务列表（用于前端下拉选择）"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        from src.log_manager import LogManager

        discover_and_import()
        log_manager = LogManager()
        date_str = datetime.now().strftime("%Y%m%d")
        tasks_with_logs = log_manager.list_task_log_files_for_date(date_str)

        all_tasks = []
        for job in MONITOR_JOBS + TASK_JOBS:
            all_tasks.append({"job_id": job.job_id, "has_log_today": job.job_id in tasks_with_logs})

        return JSONResponse(
            {
                "all_tasks": all_tasks,
                "tasks_with_logs": tasks_with_logs,
            }
        )
    except Exception as e:
        logger.error("获取任务日志列表失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/monitor-status/{platform}/{item_id}")
async def get_monitor_status_item(request: Request, platform: str, item_id: str):
    """按平台与主键 ID 获取单条监控状态（无需登录）。支持所有已持久化的平台。"""
    if platform not in VALID_PLATFORMS:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    try:
        if platform not in _PLATFORM_SELECT:
            return JSONResponse({"error": "无效的平台"}, status_code=400)

        async with AsyncDatabase() as db:
            _, sql = _PLATFORM_SELECT[platform]
            rows = await db.execute_query(sql, {"pk": item_id})

        if not rows:
            return JSONResponse({"error": "未找到该资源"}, status_code=404)

        data = _row_to_item(platform, rows[0])

        return JSONResponse(
            {
                "success": True,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error("获取监控状态失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/monitor-status/{platform}")
async def get_monitor_status_by_platform(request: Request, platform: str):
    """按平台获取监控状态列表（无需登录）。支持所有已持久化的平台。"""
    if platform not in VALID_PLATFORMS:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    try:
        if platform not in _PLATFORM_LIST_SQL:
            return JSONResponse({"error": "无效的平台"}, status_code=400)

        async with AsyncDatabase() as db:
            rows = await db.execute_query(_PLATFORM_LIST_SQL[platform])

        data = [_row_to_item(platform, row) for row in rows]

        return JSONResponse(
            {
                "success": True,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error("获取监控状态失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/monitor-status")
async def get_monitor_status(request: Request):
    """获取全部监控任务状态（无需登录）。返回所有已持久化平台的聚合结果。"""

    try:
        async with AsyncDatabase() as db:
            all_data: dict[str, list[dict]] = {}

            for platform, base_sql in _PLATFORM_LIST_SQL.items():
                try:
                    rows = await db.execute_query(base_sql)
                    all_data[platform] = [_row_to_item(platform, row) for row in rows]
                except Exception as e:
                    logger.error("获取平台 %s 监控状态失败: %s", platform, e, exc_info=True)
                    all_data[platform] = []

        return JSONResponse(
            {
                "success": True,
                "data": all_data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error("获取监控状态失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


# ==========================================================================
# AI 助手 API（需登录，ai_assistant.enable 且已安装 ai 依赖时可用）
# ==========================================================================


def _assistant_require_auth(request: Request) -> JSONResponse | None:
    """检查登录与 AI 启用，未通过时返回 JSONResponse"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)
    try:
        from src.ai_assistant import is_ai_enabled

        if not is_ai_enabled():
            return JSONResponse(
                {
                    "error": "AI 助手未启用",
                    "hint": "请在 config.yml 中配置 ai_assistant.enable 并执行 uv sync 安装依赖",
                },
                status_code=503,
            )
    except ImportError:
        return JSONResponse(
            {"error": "AI 助手模块不可用", "hint": "请执行 uv sync 安装依赖"},
            status_code=503,
        )
    return None


@app.get("/api/assistant/status")
async def assistant_status(request: Request):
    """获取 AI 助手可用状态（无需 AI 依赖也可调用）"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"enabled": False, "reason": "未登录"})
    try:
        from src.ai_assistant import is_ai_enabled

        return JSONResponse({"enabled": is_ai_enabled()})
    except ImportError:
        return JSONResponse({"enabled": False, "reason": "未安装 ai 依赖"})


@app.get("/api/assistant/conversations")
async def get_assistant_conversations(request: Request):
    """获取当前用户会话列表"""
    err = _assistant_require_auth(request)
    if err:
        return err
    from src.ai_assistant.conversation import list_conversations

    user_id = request.session.get("username", "default")
    convos = list_conversations(user_id)
    return JSONResponse({"conversations": convos})


@app.post("/api/assistant/conversations")
async def create_assistant_conversation(request: Request):
    """新建会话"""
    err = _assistant_require_auth(request)
    if err:
        return err
    body = (
        await request.json()
        if request.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    title = str(body.get("title", "新对话")).strip() or "新对话"
    from src.ai_assistant.conversation import create_conversation

    user_id = request.session.get("username", "default")
    conv_id = create_conversation(user_id=user_id, title=title)
    return JSONResponse({"conversation_id": conv_id})


@app.get("/api/assistant/conversations/{conv_id}/messages")
async def get_assistant_messages(request: Request, conv_id: str):
    """获取指定会话的消息列表"""
    err = _assistant_require_auth(request)
    if err:
        return err
    from src.ai_assistant.config import get_ai_config
    from src.ai_assistant.conversation import get_messages

    cfg = get_ai_config()
    msgs = get_messages(conv_id, max_rounds=cfg.max_history_rounds)
    return JSONResponse({"messages": msgs})


@app.delete("/api/assistant/conversations/{conv_id}")
async def delete_assistant_conversation(request: Request, conv_id: str):
    """删除指定会话"""
    err = _assistant_require_auth(request)
    if err:
        return err
    from src.ai_assistant.conversation import delete_conversation

    delete_conversation(conv_id)
    return JSONResponse({"success": True})


async def _parse_executable_intent_and_reply(message: str):
    """
    解析可执行意图（开关监控、配置列表增删、执行任务）。
    若识别到可执行意图，返回 (reply, suggested_action)；否则返回 (None, None)。
    """
    from src.ai_assistant.intent_parser import (
        parse_config_field_intent,
        parse_config_patch_intent,
        parse_run_task_intent,
        parse_toggle_monitor_intent,
    )
    from src.weibo_search import is_numeric_uid, search_weibo_users

    # 1. 执行任务（执行超话签到、运行ikuuu 等）
    run_intent = parse_run_task_intent(message)
    if run_intent is not None:
        reply = f"好的，将立即执行「{run_intent.display_name}」任务。请确认执行："
        suggested_action = {
            "type": "confirm_execute",
            "action": "run_task",
            "task_id": run_intent.task_id,
            "title": f"执行 {run_intent.display_name}",
            "description": f"确认后将在后台运行任务「{run_intent.display_name}」，与「任务管理」中手动触发的效果相同。",
        }
        return reply, suggested_action

    # 2. 开关监控
    intent = parse_toggle_monitor_intent(message)
    if intent is not None:
        action_text = "关闭" if not intent.enable else "开启"
        reply = f"好的，{action_text}{intent.display_name}监控。请确认执行："
        suggested_action = {
            "type": "confirm_execute",
            "action": "toggle_monitor",
            "platform_key": intent.platform_key,
            "enable": intent.enable,
            "title": f"{action_text}{intent.display_name}监控",
            "description": f"确认{action_text}{intent.display_name}监控？"
            + (
                "关闭后将停止轮询并不再推送相关通知。"
                if not intent.enable
                else "开启后将恢复轮询并推送通知。"
            ),
        }
        return reply, suggested_action

    # 3. 配置列表增删（删除虎牙主播100、添加虎牙房间200 等）
    patch = parse_config_patch_intent(message)
    if patch is not None:
        op_text = "添加" if patch.operation == "add" else "移除"

        # 微博添加：若 value 非数字 UID，先搜索用户并让用户选择
        if (
            patch.platform_key == "weibo"
            and patch.operation == "add"
            and not is_numeric_uid(patch.value)
        ):
            config = get_config()
            cookie = config.weibo_cookie or ""
            candidates = await search_weibo_users(patch.value, cookie)

            if not candidates:
                from urllib.parse import quote

                search_link = f"https://s.weibo.com/user?q={quote(patch.value)}"
                reply = (
                    f"未找到与「{patch.value}」相关的微博用户。\n\n"
                    f"请尝试：\n"
                    f"1. 在浏览器打开 {search_link} 搜索\n"
                    f"2. 从结果中点击目标用户，进入主页后 URL 中的数字即为 UID\n"
                    f"3. 对我说「添加微博用户 <UID>」或在配置页直接输入 UID"
                )
                return reply, None

            if len(candidates) == 1:
                c = candidates[0]
                reply = f"找到 1 个匹配账号：**{c['nick']}**（UID: {c['uid']}）"
                suggested_action = {
                    "type": "confirm_execute",
                    "action": "config_patch",
                    "platform_key": "weibo",
                    "list_key": "uids",
                    "operation": "add",
                    "value": c["uid"],
                    "title": "添加微博监控",
                    "description": f"将添加「{c['nick']}」到微博监控列表",
                }
                return reply, suggested_action

            # 多个候选：让用户选择
            lines = [
                f"{i + 1}. **{c['nick']}**（UID: {c['uid']}，粉丝: {c.get('followers_count_str', '')}）"
                for i, c in enumerate(candidates)
            ]
            reply = f"找到 {len(candidates)} 个相关账号，请选择要添加的：\n\n" + "\n".join(lines)
            suggested_action = {
                "type": "weibo_choose",
                "title": "选择要添加的微博账号",
                "description": "请选择要添加到监控的账号：",
                "candidates": candidates,
            }
            return reply, suggested_action

        # 普通增删（包括微博添加纯数字 UID）
        reply = f"好的，将从{patch.display_name}监控列表中{op_text}「{patch.value}」。请确认执行："
        suggested_action = {
            "type": "confirm_execute",
            "action": "config_patch",
            "platform_key": patch.platform_key,
            "list_key": patch.list_key,
            "operation": patch.operation,
            "value": patch.value,
            "title": f"{op_text}配置项",
            "description": f"将从 {patch.platform_key} 的 {patch.list_key} 中{op_text}「{patch.value}」",
        }
        return reply, suggested_action

    # 4. 修改标量配置（监控间隔、并发、执行时间、日志保留、免打扰等）
    field_intent = parse_config_field_intent(message)
    if field_intent is not None:
        if field_intent.field_key == "monitor_interval_seconds":
            desc = f"将 {field_intent.display_name} 的 {field_intent.field_key} 修改为 {field_intent.value} 秒"
        elif field_intent.field_key == "concurrency":
            desc = f"将 {field_intent.display_name} 并发数修改为 {field_intent.value}"
        elif field_intent.field_key == "time":
            desc = f"将 {field_intent.display_name} 执行时间修改为 {field_intent.value}"
        elif field_intent.field_key == "retention_days":
            desc = f"将日志保留天数修改为 {field_intent.value} 天"
        elif field_intent.field_key in ("start", "end"):
            desc = f"将免打扰{ '开始' if field_intent.field_key == 'start' else '结束'}时间修改为 {field_intent.value}"
        elif field_intent.field_key == "start_end":
            s, e = str(field_intent.value).split(",", 1)
            desc = f"将免打扰时段设为 {s} 至 {e}"
        else:
            desc = f"将 {field_intent.display_name} 的 {field_intent.field_key} 修改为 {field_intent.value}"
        reply = f"好的，{desc}。请确认执行："
        suggested_action = {
            "type": "confirm_execute",
            "action": "config_field_update",
            "section_key": field_intent.section_key,
            "field_key": field_intent.field_key,
            "value": field_intent.value,
            "title": "修改配置",
            "description": desc,
        }
        return reply, suggested_action

    return None, None


@app.post("/api/assistant/chat")
async def assistant_chat(request: Request):
    """对话接口，支持多轮记忆"""
    err = _assistant_require_auth(request)
    if err:
        return err
    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "message 不能为空"}, status_code=400)
    conversation_id = body.get("conversation_id") or ""
    context = body.get("context", "all")

    from src.ai_assistant.config import get_ai_config
    from src.ai_assistant.conversation import (
        append_messages,
        create_conversation,
        get_messages,
    )
    from src.ai_assistant.llm_client import chat_completion
    from src.ai_assistant.prompts import SYSTEM_PROMPT
    from src.ai_assistant.rag import retrieve_all
    from src.ai_assistant.tools_current_state import (
        parse_platforms_from_message,
        query_current_state,
    )

    cfg = get_ai_config()
    user_id = request.session.get("username", "default")

    if not conversation_id:
        conversation_id = create_conversation(user_id=user_id, title="新对话")

    # 语义理解：优先识别可执行意图（开关监控、配置列表增删）
    reply, suggested_action = await _parse_executable_intent_and_reply(message)
    if reply is not None:
        append_messages(
            conversation_id, user_content=message, assistant_content=reply, user_id=user_id
        )
        return JSONResponse(
            {
                "reply": reply,
                "conversation_id": conversation_id,
                "suggested_action": suggested_action,
            }
        )

    history = get_messages(conversation_id, max_rounds=cfg.max_history_rounds)

    system_content = SYSTEM_PROMPT
    rag_ctx = await asyncio.to_thread(retrieve_all, message, context)
    if rag_ctx:
        system_content += "\n\n【本次检索到的参考】\n" + rag_ctx
    need_current = (
        "当前" in message
        or "现在" in message
        or "谁在直播" in message
        or "最新" in message
        or "开播" in message
        or "谁开播" in message
        or "直播" in message
    )
    if need_current:
        try:
            platforms = parse_platforms_from_message(message)
            current_data = await query_current_state(platforms=platforms)
            if current_data:
                system_content += "\n\n【当前监控数据】\n" + current_data
        except Exception as e:
            logger.debug("query_current_state 失败: %s", e)

    messages = [{"role": "system", "content": system_content}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    try:
        reply = await chat_completion(messages=messages)
    except Exception as e:
        logger.error("AI 助手调用失败: %s", e)
        return JSONResponse(
            {"error": f"LLM 调用失败: {e}", "conversation_id": conversation_id},
            status_code=500,
        )

    append_messages(conversation_id, user_content=message, assistant_content=reply, user_id=user_id)

    reply, suggested_action = _parse_suggested_action_from_reply(reply)

    return JSONResponse(
        {
            "reply": reply,
            "conversation_id": conversation_id,
            "suggested_action": suggested_action,
        }
    )


def _parse_suggested_action_from_reply(reply: str) -> tuple[str, dict | None]:
    """从完整回复文本中解析 suggested_action，返回 (清洗后的 reply, suggested_action)。"""
    import re

    suggested_action = None
    json_match = re.search(r"```json\s*\n(.*?)```", reply, re.DOTALL)
    if json_match:
        try:
            patch = json.loads(json_match.group(1).strip())
            if patch.get("type") == "config_patch" and all(
                k in patch for k in ("platform_key", "list_key", "operation", "value")
            ):
                suggested_action = {
                    "type": "confirm_execute",
                    "action": "config_patch",
                    "platform_key": patch["platform_key"],
                    "list_key": patch["list_key"],
                    "operation": patch["operation"],
                    "value": str(patch["value"]),
                    "title": f"{'添加' if patch['operation'] == 'add' else '移除'}配置项",
                    "description": f"将从 {patch['platform_key']} 的 {patch['list_key']} 中{'添加' if patch['operation'] == 'add' else '移除'}「{patch['value']}」",
                }
                reply = re.sub(r"\n*```json\s*\n.*?```\s*", "\n", reply, flags=re.DOTALL).strip()
        except (json.JSONDecodeError, KeyError):
            pass
    if suggested_action is None:
        yaml_match = re.search(r"```yaml\s*\n(.*?)```", reply, re.DOTALL)
        if yaml_match:
            suggested_action = {
                "type": "config_diff",
                "diff": yaml_match.group(1).strip(),
                "description": "配置片段（可复制到 config.yml 或配置页）",
            }
    return reply, suggested_action


@app.post("/api/assistant/chat/stream")
async def assistant_chat_stream(request: Request):
    """对话接口（流式），使用 Server-Sent Events 逐块返回 AI 回复。"""
    err = _assistant_require_auth(request)
    if err:
        return err
    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "message 不能为空"}, status_code=400)
    conversation_id = body.get("conversation_id") or ""
    context = body.get("context", "all")

    from src.ai_assistant.config import get_ai_config
    from src.ai_assistant.conversation import (
        append_messages,
        create_conversation,
        get_messages,
    )
    from src.ai_assistant.llm_client import chat_completion_stream
    from src.ai_assistant.prompts import SYSTEM_PROMPT
    from src.ai_assistant.rag import retrieve_all
    from src.ai_assistant.tools_current_state import (
        parse_platforms_from_message,
        query_current_state,
    )

    cfg = get_ai_config()
    user_id = request.session.get("username", "default")

    if not conversation_id:
        conversation_id = create_conversation(user_id=user_id, title="新对话")

    reply, suggested_action = await _parse_executable_intent_and_reply(message)
    if reply is not None:

        async def _intent_stream():
            yield f"data: {json.dumps({'chunk': reply}, ensure_ascii=False)}\n\n".encode()
            yield f"data: {json.dumps({'done': True, 'reply': reply, 'suggested_action': suggested_action, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n".encode()

        append_messages(
            conversation_id, user_content=message, assistant_content=reply, user_id=user_id
        )
        return StreamingResponse(
            _intent_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    history = get_messages(conversation_id, max_rounds=cfg.max_history_rounds)
    system_content = SYSTEM_PROMPT
    rag_ctx = await asyncio.to_thread(retrieve_all, message, context)
    if rag_ctx:
        system_content += "\n\n【本次检索到的参考】\n" + rag_ctx
    need_current = (
        "当前" in message
        or "现在" in message
        or "谁在直播" in message
        or "最新" in message
        or "开播" in message
        or "谁开播" in message
        or "直播" in message
    )
    if need_current:
        try:
            platforms = parse_platforms_from_message(message)
            current_data = await query_current_state(platforms=platforms)
            if current_data:
                system_content += "\n\n【当前监控数据】\n" + current_data
        except Exception as e:
            logger.debug("query_current_state 失败: %s", e)

    messages = [{"role": "system", "content": system_content}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    async def _stream_body():
        full_reply_parts = []
        try:
            async for chunk in chat_completion_stream(messages=messages):
                full_reply_parts.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n".encode()
        except Exception as e:
            logger.error("AI 助手流式调用失败: %s", e)
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n".encode()
            return
        reply = "".join(full_reply_parts).strip()
        append_messages(
            conversation_id, user_content=message, assistant_content=reply, user_id=user_id
        )
        reply, suggested_action = _parse_suggested_action_from_reply(reply)
        yield f"data: {json.dumps({'done': True, 'reply': reply, 'suggested_action': suggested_action, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n".encode()

    return StreamingResponse(
        _stream_body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# 允许通过 AI 助手 apply-action 开关的配置节（监控 + 定时任务等）
TOGGLE_SECTIONS = frozenset(
    {
        "weibo",
        "huya",
        "bilibili",
        "douyin",
        "douyu",
        "xhs",
        "weibo_chaohua",
        "checkin",
        "tieba",
        "rainyun",
        "aliyun",
        "smzdm",
        "kuake",
        "weather",
        "log_cleanup",
        "quiet_hours",
    }
)

# config_patch 支持的 platform -> list_key 映射
CONFIG_PATCH_PLATFORMS = {
    "weibo": "uids",
    "huya": "rooms",
    "bilibili": "uids",
    "douyin": "douyin_ids",
    "douyu": "rooms",
    "xhs": "profile_ids",
}


@app.post("/api/assistant/apply-action")
async def assistant_apply_action(request: Request):
    """执行 AI 助手识别的可确认操作（如开关监控、增删列表项）"""
    err = _assistant_require_auth(request)
    if err:
        return err

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "请求体格式错误"}, status_code=400)

    action = body.get("action")
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    if action == "config_patch":
        platform_key = body.get("platform_key")
        list_key = body.get("list_key")
        operation = body.get("operation")
        value = body.get("value")
        if platform_key not in CONFIG_PATCH_PLATFORMS:
            return JSONResponse({"error": f"不支持的平台: {platform_key}"}, status_code=400)
        if CONFIG_PATCH_PLATFORMS.get(platform_key) != list_key:
            return JSONResponse({"error": f"无效的 list_key: {list_key}"}, status_code=400)
        if operation not in ("add", "remove"):
            return JSONResponse({"error": "operation 须为 add 或 remove"}, status_code=400)
        if not isinstance(value, str) or not value.strip():
            return JSONResponse({"error": "value 不能为空"}, status_code=400)

        # 微博添加时 value 须为数字 UID，昵称需通过「关注XX的微博」由系统搜索选择
        if platform_key == "weibo" and operation == "add":
            from src.weibo_search import is_numeric_uid

            if not is_numeric_uid(value):
                return JSONResponse(
                    {
                        "error": "微博添加请使用 UID（纯数字）。可通过对话说「关注XX的微博」由系统搜索并选择后写入。"
                    },
                    status_code=400,
                )

        try:
            config_path = Path("config.yml")
            if not config_path.exists():
                return JSONResponse({"error": "配置文件不存在"}, status_code=404)
            yaml_content = _apply_config_patch(
                config_path, platform_key, list_key, operation, value
            )

            err = await _validate_and_save_config(yaml_content, config_path)
            if err:
                return err

            op_text = "添加" if operation == "add" else "移除"
            display = {
                "weibo": "微博",
                "huya": "虎牙",
                "bilibili": "哔哩哔哩",
                "douyin": "抖音",
                "douyu": "斗鱼",
                "xhs": "小红书",
            }.get(platform_key, platform_key)
            return JSONResponse(
                {
                    "success": True,
                    "message": f"已从{display}监控列表{op_text}「{value}」，配置已热重载",
                }
            )
        except Exception as e:
            logger.error("apply-action config_patch 执行失败: %s", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    if action == "config_field_update":
        section_key = body.get("section_key") or body.get("platform_key")  # 兼容旧字段名
        field_key = body.get("field_key")
        value = body.get("value")
        config_field_allowed = {
            ("weibo", "monitor_interval_seconds"),
            ("huya", "monitor_interval_seconds"),
            ("bilibili", "monitor_interval_seconds"),
            ("douyin", "monitor_interval_seconds"),
            ("douyu", "monitor_interval_seconds"),
            ("xhs", "monitor_interval_seconds"),
            ("weibo", "concurrency"),
            ("huya", "concurrency"),
            ("bilibili", "concurrency"),
            ("douyin", "concurrency"),
            ("douyu", "concurrency"),
            ("xhs", "concurrency"),
            ("weibo_chaohua", "time"),
            ("checkin", "time"),
            ("tieba", "time"),
            ("rainyun", "time"),
            ("log_cleanup", "time"),
            ("log_cleanup", "retention_days"),
            ("quiet_hours", "start"),
            ("quiet_hours", "end"),
            ("quiet_hours", "start_end"),
        }
        if (section_key, field_key) not in config_field_allowed:
            return JSONResponse(
                {"error": f"不支持的配置: {section_key}.{field_key}"}, status_code=400
            )
        # start_end 特殊处理：拆分为 start 和 end
        config_updates = {}
        if field_key == "start_end" and section_key == "quiet_hours":
            parts = str(value).split(",", 1)
            if len(parts) == 2:
                config_updates = {
                    "quiet_hours": {"start": parts[0].strip(), "end": parts[1].strip()}
                }
        else:
            if field_key in ("monitor_interval_seconds", "concurrency", "retention_days"):
                try:
                    value = int(value) if value is not None else 0
                except (TypeError, ValueError):
                    return JSONResponse({"error": "value 须为整数"}, status_code=400)
                if field_key == "monitor_interval_seconds" and (value < 1 or value > 86400):
                    return JSONResponse({"error": "监控间隔须为 1–86400 秒"}, status_code=400)
                if field_key == "concurrency" and (value < 1 or value > 20):
                    return JSONResponse({"error": "并发数须为 1–20"}, status_code=400)
                if field_key == "retention_days" and (value < 1 or value > 90):
                    return JSONResponse({"error": "日志保留天数须为 1–90"}, status_code=400)
            config_updates = {section_key: {field_key: value}}
        try:
            config_path = Path("config.yml")
            if not config_path.exists():
                return JSONResponse({"error": "配置文件不存在"}, status_code=404)
            yaml_content = _merge_and_dump_config(config_path, config_updates)
            err = await _validate_and_save_config(yaml_content, config_path)
            if err:
                return err
            _display_map = {
                "weibo": "微博",
                "huya": "虎牙",
                "bilibili": "哔哩哔哩",
                "douyin": "抖音",
                "douyu": "斗鱼",
                "xhs": "小红书",
                "weibo_chaohua": "超话签到",
                "checkin": "iKuuu",
                "tieba": "贴吧",
                "rainyun": "雨云",
                "log_cleanup": "日志清理",
                "quiet_hours": "免打扰",
            }
            display = _display_map.get(section_key, section_key)
            if field_key == "monitor_interval_seconds":
                msg = f"已将{display}监控间隔修改为 {value} 秒"
            elif field_key == "concurrency":
                msg = f"已将{display}并发数修改为 {value}"
            elif field_key == "time":
                msg = f"已将{display}执行时间修改为 {value}"
            elif field_key == "retention_days":
                msg = f"已将日志保留天数修改为 {value} 天"
            elif field_key in ("start", "end"):
                msg = f"已将免打扰{ '开始' if field_key == 'start' else '结束'}时间修改为 {value}"
            elif field_key == "start_end":
                s, e = str(value).split(",", 1)
                msg = f"已将免打扰时段设为 {s} 至 {e}"
            else:
                msg = f"已修改 {section_key}.{field_key}"
            return JSONResponse({"success": True, "message": f"{msg}，配置已热重载"})
        except Exception as e:
            logger.error("apply-action config_field_update 执行失败: %s", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    if action == "run_task":
        task_id = body.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            return JSONResponse({"error": "task_id 不能为空"}, status_code=400)
        task_id = task_id.strip()
        try:
            discover_and_import()
            all_jobs = MONITOR_JOBS + TASK_JOBS
            target_job = None
            for job in all_jobs:
                if job.job_id == task_id:
                    target_job = job
                    break
            if target_job is None:
                return JSONResponse({"error": f"任务 {task_id} 不存在"}, status_code=404)
            run_func = target_job.original_run_func or target_job.run_func
            await run_task_with_logging(task_id, run_func)
            logger.info("AI 助手触发任务: %s", task_id)
            display = _get_job_description(task_id)
            return JSONResponse({"success": True, "message": f"已执行「{display}」"})
        except Exception as e:
            logger.error("apply-action run_task 执行失败: %s", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    if action != "toggle_monitor":
        return JSONResponse({"error": f"不支持的操作: {action}"}, status_code=400)

    platform_key = body.get("platform_key")
    if platform_key not in TOGGLE_SECTIONS:
        return JSONResponse({"error": f"不支持的配置节: {platform_key}"}, status_code=400)

    enable = body.get("enable")
    if not isinstance(enable, bool):
        return JSONResponse({"error": "enable 须为布尔值"}, status_code=400)

    try:
        config_path = Path("config.yml")
        if not config_path.exists():
            return JSONResponse({"error": "配置文件不存在"}, status_code=404)

        config_data = {platform_key: {"enable": enable}}
        yaml_content = _merge_and_dump_config(config_path, config_data)

        err = await _validate_and_save_config(yaml_content, config_path)
        if err:
            return err

        action_text = "开启" if enable else "关闭"
        _disp = {
            "weibo": "微博",
            "huya": "虎牙",
            "bilibili": "哔哩哔哩",
            "douyin": "抖音",
            "douyu": "斗鱼",
            "xhs": "小红书",
            "weibo_chaohua": "微博超话签到",
            "checkin": "iKuuu 签到",
            "tieba": "贴吧签到",
            "rainyun": "雨云签到",
            "aliyun": "阿里云盘签到",
            "smzdm": "值得买签到",
            "kuake": "夸克签到",
            "weather": "天气推送",
            "log_cleanup": "日志清理",
            "quiet_hours": "免打扰",
        }
        display = _disp.get(platform_key, platform_key)
        suffix = (
            "监控"
            if platform_key in ("weibo", "huya", "bilibili", "douyin", "douyu", "xhs")
            else ""
        )
        return JSONResponse(
            {"success": True, "message": f"已{action_text}{display}{suffix}，配置已热重载"}
        )
    except Exception as e:
        logger.error("apply-action 执行失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


# ==========================================================================
# AI 助手 - 平台 Webhook（企业微信、Telegram 等支持交互的推送渠道）
# ==========================================================================


def _get_wecom_channels_with_callback() -> list[tuple[str, dict]]:
    """获取配置了 callback_token + encoding_aes_key 的 wecom_apps 通道"""
    try:
        config = get_config()
        channels = config.push_channel_list or []
        result = []
        for ch in channels:
            if ch.get("type") != "wecom_apps":
                continue
            token = str(ch.get("callback_token", "")).strip()
            key = str(ch.get("encoding_aes_key", "")).strip()
            if token and key and ch.get("corp_id"):
                result.append((ch.get("name", ""), ch))
        return result
    except Exception:
        return []


def _get_telegram_channels() -> list[tuple[str, dict]]:
    """获取配置了 api_token 的 telegram_bot 通道"""
    try:
        config = get_config()
        channels = config.push_channel_list or []
        result = []
        for ch in channels:
            if ch.get("type") != "telegram_bot":
                continue
            token = str(ch.get("api_token", "")).strip()
            if token:
                result.append((ch.get("name", ""), ch))
        return result
    except Exception:
        return []


@app.api_route("/api/webhooks/wecom", methods=["GET", "POST"])
async def webhook_wecom(request: Request):
    """
    企业微信自建应用 - 接收消息回调。
    需在 push_channel 的 wecom_apps 中配置 callback_token、encoding_aes_key，
    并在企业微信后台设置「接收消息」URL 为本接口（如 https://xxx/api/webhooks/wecom）。
    支持多应用：依次尝试各通道解密，第一个成功的即为目标应用。
    """
    channels = _get_wecom_channels_with_callback()
    if not channels:
        return JSONResponse({"error": "未配置企业微信 AI 回调"}, status_code=503)

    from src.ai_assistant.platform_handlers.wecom import handle_wecom_callback

    # POST 时请求体只能读一次，先缓存
    post_body: bytes | None = None
    if request.method == "POST":
        post_body = await request.body()

    last_error = None
    for _name, ch in channels:
        try:
            resp = await handle_wecom_callback(
                request, ch, post_body=post_body if request.method == "POST" else None
            )
            # 非 4xx 表示处理成功
            if hasattr(resp, "status_code") and 400 <= resp.status_code < 500:
                last_error = resp
                continue
            return resp
        except ValueError as e:
            last_error = e
            continue
        except Exception as e:
            logger.debug("企业微信通道 %s 处理异常: %s", _name, e)
            last_error = e
            continue

    if isinstance(last_error, JSONResponse):
        return last_error
    return JSONResponse({"error": "签名或解密失败"}, status_code=400)


@app.post("/api/webhooks/telegram/{channel_name:path}")
async def webhook_telegram(request: Request, channel_name: str):
    """
    Telegram 机器人 - 接收消息 Webhook。
    需在 push_channel 的 telegram_bot 中配置 api_token，
    并调用 setWebhook 设置 URL 为 https://xxx/api/webhooks/telegram/{通道名}。
    """
    channels = _get_telegram_channels()
    channel_config = None
    for name, ch in channels:
        if name == channel_name:
            channel_config = ch
            break
    if not channel_config:
        return JSONResponse({"error": "未找到该 Telegram 通道"}, status_code=404)

    from src.ai_assistant.platform_handlers.telegram import (
        handle_telegram_webhook,
        send_telegram_message,
    )

    result = await handle_telegram_webhook(request, channel_config)
    if result is None:
        return JSONResponse({"ok": True})  # 非消息类 update，直接返回

    # 异步发送回复，避免 Webhook 超时
    chat_id = result.get("chat_id")
    text = result.get("text", "")
    api_token = channel_config.get("api_token", "")

    if chat_id and text and api_token:
        import asyncio

        asyncio.create_task(send_telegram_message(api_token, chat_id, text))

    return JSONResponse({"ok": True})


def create_web_app():
    """创建Web应用实例"""
    return app
