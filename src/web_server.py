"""Web服务器模块 - 提供Web界面和API接口"""

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src.config import get_config, load_config_from_yml
from src.database import AsyncDatabase
from src.job_registry import MONITOR_JOBS, TASK_JOBS, discover_and_import

# 尝试导入 ruamel.yaml 以保留注释
try:
    from ruamel.yaml import YAML as RUAMEL_YAML

    RUAMEL_AVAILABLE = True
except ImportError:
    RUAMEL_AVAILABLE = False
    RUAMEL_YAML = None

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

# 凭据文件路径
AUTH_FILE = Path("data/auth.json")

# 默认凭据
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "123"

# 存储登录会话
active_sessions: set[str] = set()


def hash_password(password: str) -> str:
    """使用 SHA-256 哈希密码"""
    return hashlib.sha256(password.encode()).hexdigest()


def load_auth() -> dict:
    """加载认证信息，如果文件不存在则返回默认值"""
    if AUTH_FILE.exists():
        try:
            with open(AUTH_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载认证文件失败: {e}")
    # 返回默认凭据（哈希后的密码）
    return {
        "username": DEFAULT_USERNAME,
        "password_hash": hash_password(DEFAULT_PASSWORD),
    }


def save_auth(auth_data: dict) -> bool:
    """保存认证信息到文件"""
    try:
        # 确保 data 目录存在
        AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(auth_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存认证文件失败: {e}")
        return False


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    return hash_password(password) == password_hash


def check_login(session_id: str | None) -> bool:
    """检查用户是否已登录"""
    return session_id is not None and session_id in active_sessions


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
    auth_data = load_auth()
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
    auth_data = load_auth()
    if not verify_password(old_password, auth_data.get("password_hash", "")):
        return JSONResponse({"success": False, "message": "当前密码错误"}, status_code=400)

    # 更新密码
    auth_data["password_hash"] = hash_password(new_password)
    if save_auth(auth_data):
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
        GITHUB_API_LATEST_RELEASE,
        GITHUB_RELEASES_URL,
        __version__,
    )

    return JSONResponse(
        {
            "version": __version__,
            "github_api_url": GITHUB_API_LATEST_RELEASE,
            "releases_url": GITHUB_RELEASES_URL,
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
        logger.error(f"获取任务列表失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


def _get_job_description(job_id: str) -> str:
    """根据任务ID获取任务描述"""
    descriptions = {
        "huya_monitor": "虎牙直播状态监控",
        "weibo_monitor": "微博动态监控",
        "log_cleanup": "日志文件清理",
        "ikuuu_checkin": "ikuuu 每日签到",
        "tieba_checkin": "百度贴吧签到",
        "weibo_chaohua_checkin": "微博超话签到",
        "demo_task": "示例任务（二次开发演示）",
    }
    return descriptions.get(job_id, f"任务 {job_id}")


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
        logger.info(f"手动触发任务: {task_id}")
        try:
            # 优先使用原始函数（不检查当天是否已运行），如果没有则使用包装后的函数
            run_func = target_job.original_run_func or target_job.run_func
            await run_func()
            logger.info(f"任务 {task_id} 手动执行完成")
            return JSONResponse(
                {
                    "success": True,
                    "message": f"任务 {task_id} 执行成功",
                }
            )
        except Exception as e:
            logger.error(f"任务 {task_id} 执行失败: {e}", exc_info=True)
            return JSONResponse(
                {
                    "success": False,
                    "message": f"任务执行失败: {str(e)}",
                },
                status_code=500,
            )
    except Exception as e:
        logger.error(f"触发任务失败: {e}")
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
            with open(config_path, encoding="utf-8") as f:
                content = f.read()
            return JSONResponse({"content": content})

        # 否则返回JSON格式
        with open(config_path, encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)

        return JSONResponse({"config": yaml_data})
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
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
                        logger.warning(f"使用 ruamel.yaml 保留注释失败，回退到标准方式: {e}")
                        # 回退到标准方式
                        yaml_content = yaml.dump(
                            config_data,
                            allow_unicode=True,
                            default_flow_style=False,
                            sort_keys=False,
                        )
                else:
                    # 使用标准 yaml.dump（没有 ruamel.yaml 或文件不存在）
                    try:
                        yaml_content = yaml.dump(
                            config_data,
                            allow_unicode=True,
                            default_flow_style=False,
                            sort_keys=False,
                        )
                    except Exception as e:
                        return JSONResponse({"error": f"转换YAML失败: {str(e)}"}, status_code=400)
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

        # 验证配置内容（使用临时文件）
        import tempfile

        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(yaml_content)
                temp_file = tmp.name

            # 尝试加载配置验证
            try:
                test_config_dict = load_config_from_yml(temp_file)
                # 尝试创建AppConfig验证
                from src.config import AppConfig

                AppConfig(**test_config_dict)
            except Exception as e:
                return JSONResponse({"error": f"配置验证失败: {str(e)}"}, status_code=400)
            finally:
                if temp_file and Path(temp_file).exists():
                    Path(temp_file).unlink()
        except Exception as e:
            if temp_file and Path(temp_file).exists():
                Path(temp_file).unlink()
            return JSONResponse({"error": f"配置验证失败: {str(e)}"}, status_code=400)

        # 保存配置文件
        config_path = Path("config.yml")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        # 触发热重载（通过重新加载配置）
        try:
            get_config(reload=True)
            # 日志由配置监控器统一输出，这里不输出
        except Exception as e:
            logger.warning(f"热重载失败: {e}")

        return JSONResponse({"success": True, "message": "配置已保存并应用"})
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# 平台主键与查询列
PLATFORM_PRIMARY_KEY = {"weibo": "UID", "huya": "room"}
VALID_PLATFORMS = frozenset(PLATFORM_PRIMARY_KEY)


def _weibo_row_to_item(row: tuple) -> dict:
    """将 weibo 表的一行转为 API 返回项（含 url）。"""
    return {
        "UID": row[0],
        "用户名": row[1],
        "认证信息": row[2],
        "简介": row[3],
        "粉丝数": row[4],
        "微博数": row[5],
        "文本": row[6],
        "mid": row[7],
        "url": (
            f"https://m.weibo.cn/detail/{row[7]}" if row[7] else f"https://www.weibo.com/u/{row[0]}"
        ),
    }


def _huya_row_to_item(row: tuple) -> dict:
    """将 huya 表的一行转为 API 返回项（含 url）。"""
    return {
        "room": row[0],
        "name": row[1],
        "is_live": row[2],
        "url": f"https://www.huya.com/{row[0]}",
    }


def _weibo_row_to_status_item(row: tuple) -> dict:
    """将 weibo 表的一行转为 monitor-status 返回项（不含 url）。"""
    return {
        "UID": row[0],
        "用户名": row[1],
        "认证信息": row[2],
        "简介": row[3],
        "粉丝数": row[4],
        "微博数": row[5],
        "文本": row[6],
        "mid": row[7],
    }


def _huya_row_to_status_item(row: tuple) -> dict:
    """将 huya 表的一行转为 monitor-status 返回项。"""
    return {"room": row[0], "name": row[1], "is_live": row[2]}


@app.get("/api/data/{platform}/{item_id}")
async def get_data_item(request: Request, platform: str, item_id: str):
    """按平台与主键 ID 获取单条监控数据（需登录）。"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    if platform not in VALID_PLATFORMS:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    try:
        db = AsyncDatabase()
        await db.initialize()

        if platform == "weibo":
            rows = await db.execute_query(
                "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid FROM weibo WHERE UID = :uid",
                {"uid": item_id},
            )
        else:
            rows = await db.execute_query(
                "SELECT room, name, is_live FROM huya WHERE room = :room",
                {"room": item_id},
            )

        await db.close()

        if not rows:
            return JSONResponse({"error": "未找到该资源"}, status_code=404)

        row = rows[0]
        if platform == "weibo":
            data = _weibo_row_to_item(row)
        else:
            data = _huya_row_to_item(row)

        return JSONResponse({"data": data})
    except Exception as e:
        logger.error(f"获取单条数据失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/data/{platform}")
async def get_table_data(
    request: Request,
    platform: str,
    page: int = 1,
    page_size: int = 100,
    uid: str | None = None,
    room: str | None = None,
):
    """获取监控数据列表（需登录）。支持分页与按用户/房间过滤。"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    if platform not in VALID_PLATFORMS:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    # 平台与过滤参数对应关系
    filter_param = uid if platform == "weibo" else room
    filter_column = PLATFORM_PRIMARY_KEY[platform]

    try:
        db = AsyncDatabase()
        await db.initialize()

        where_clause = ""
        params: dict = {}
        if filter_param:
            where_clause = f" WHERE {filter_column} = :filter_val"
            params["filter_val"] = filter_param

        count_sql = f"SELECT COUNT(*) FROM {platform}{where_clause}"
        count_result = await db.execute_query(count_sql, params if params else None)
        total = count_result[0][0] if count_result else 0

        offset = (page - 1) * page_size
        params["limit"] = page_size
        params["offset"] = offset
        if platform == "weibo":
            sql = (
                "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid "
                f"FROM weibo{where_clause} LIMIT :limit OFFSET :offset"
            )
        else:
            sql = f"SELECT room, name, is_live FROM huya{where_clause} LIMIT :limit OFFSET :offset"

        rows = await db.execute_query(sql, params)

        if platform == "weibo":
            data = [_weibo_row_to_item(row) for row in rows]
        else:
            data = [_huya_row_to_item(row) for row in rows]

        await db.close()

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
        logger.error(f"获取表数据失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


def _read_log_file_sync(file_path: Path, num_lines: int) -> tuple[list, int]:
    """同步读取日志文件最后 N 行。处理文件写入时的读取冲突，带重试。返回 (最近行列表, 总行数)。"""
    max_retries = 5
    retry_delay = 0.2

    for attempt in range(max_retries):
        try:
            try:
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

            except (OSError, PermissionError):
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                raise

        except (OSError, PermissionError):
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                    text = content.decode("utf-8", errors="ignore")
                    all_lines = text.splitlines(keepends=True)
                    if len(all_lines) > num_lines:
                        recent_lines = all_lines[-num_lines:]
                    else:
                        recent_lines = all_lines
                    return recent_lines, len(all_lines)
            except Exception as final_e:
                logger.error(f"读取日志文件失败（所有方法都失败）: {final_e}")
                raise

        except Exception as e:
            logger.error(f"读取日志文件时发生未知错误: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise
    return [], 0  # 不应到达，满足类型与返回值约定


@app.get("/api/logs")
async def get_logs(request: Request, lines: int = 100):
    """获取日志内容"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        from src.log_manager import LogManager

        log_manager = LogManager()
        log_file = log_manager.get_log_file("main", date_format="%Y%m%d")

        if not log_file.exists():
            return JSONResponse({"logs": [], "message": "今日暂无日志"})

        try:
            recent_lines, total_lines = await asyncio.wait_for(
                asyncio.to_thread(_read_log_file_sync, log_file, lines),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            logger.error(f"读取日志文件超时: {log_file}")
            return JSONResponse({"error": "读取日志超时，请稍后重试"}, status_code=504)

        return JSONResponse({"logs": recent_lines, "total_lines": total_lines})
    except Exception as e:
        logger.error(f"读取日志失败: {e}", exc_info=True)
        return JSONResponse({"error": f"读取日志失败: {str(e)}"}, status_code=500)


@app.get("/api/monitor-status/{platform}/{item_id}")
async def get_monitor_status_item(request: Request, platform: str, item_id: str):
    """按平台与主键 ID 获取单条监控状态（无需登录）。"""
    if platform not in VALID_PLATFORMS:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    try:
        db = AsyncDatabase()
        await db.initialize()

        if platform == "weibo":
            rows = await db.execute_query(
                "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid FROM weibo WHERE UID = :uid",
                {"uid": item_id},
            )
            data = [_weibo_row_to_status_item(row) for row in rows]
        else:
            rows = await db.execute_query(
                "SELECT room, name, is_live FROM huya WHERE room = :room",
                {"room": item_id},
            )
            data = [_huya_row_to_status_item(row) for row in rows]

        await db.close()

        if not data:
            return JSONResponse({"error": "未找到该资源"}, status_code=404)

        return JSONResponse(
            {
                "success": True,
                "data": data[0],
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"获取监控状态失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/monitor-status/{platform}")
async def get_monitor_status_by_platform(request: Request, platform: str):
    """按平台获取监控状态列表（无需登录）。"""
    if platform not in VALID_PLATFORMS:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    try:
        db = AsyncDatabase()
        await db.initialize()

        if platform == "weibo":
            weibo_rows = await db.execute_query(
                "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid FROM weibo"
            )
            data = [_weibo_row_to_status_item(row) for row in weibo_rows]
        else:
            huya_rows = await db.execute_query("SELECT room, name, is_live FROM huya")
            data = [_huya_row_to_status_item(row) for row in huya_rows]

        await db.close()

        return JSONResponse(
            {
                "success": True,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"获取监控状态失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/monitor-status")
async def get_monitor_status(request: Request):
    """获取全部监控任务状态（无需登录）。"""

    try:
        db = AsyncDatabase()
        await db.initialize()

        weibo_rows = await db.execute_query(
            "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid FROM weibo"
        )
        weibo_data = [_weibo_row_to_status_item(row) for row in weibo_rows]

        huya_rows = await db.execute_query("SELECT room, name, is_live FROM huya")
        huya_data = [_huya_row_to_status_item(row) for row in huya_rows]

        await db.close()

        return JSONResponse(
            {
                "success": True,
                "data": {
                    "weibo": weibo_data,
                    "huya": huya_data,
                },
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"获取监控状态失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


def create_web_app():
    """创建Web应用实例"""
    return app
