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
from src.job_registry import (
    MONITOR_JOBS,
    TASK_JOBS,
    discover_and_import,
    run_task_with_logging,
)

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

# 微博相关静态资源目录（用于暴露 data/weibo 下的图片，如封面图）
# 只负责将本地文件映射为 HTTP 访问路径，不做权限控制
WEIBO_IMG_DIR = Path("data/weibo")
WEIBO_IMG_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/weibo_img", StaticFiles(directory=str(WEIBO_IMG_DIR)), name="weibo_img")

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


def _simple_merge_dict(target: dict, source: dict) -> None:
    """递归合并 source 到 target，保留 target 中未被 source 覆盖的键（避免前端未收集的配置丢失）"""
    for key, value in source.items():
        if key in ("cookies", "accounts") and isinstance(value, list) and len(value) == 0:
            if key in target and isinstance(target[key], list):
                del target[key]
            continue
        if key not in target:
            target[key] = value
        elif isinstance(target[key], dict) and isinstance(value, dict):
            _simple_merge_dict(target[key], value)
        elif isinstance(target[key], list) and isinstance(value, list):
            if key == "push_channel" and len(target[key]) > 0 and len(value) > 0:
                existing_map = {
                    item.get("name"): idx
                    for idx, item in enumerate(target[key])
                    if isinstance(item, dict) and "name" in item
                }
                new_names = {
                    item.get("name") for item in value if isinstance(item, dict) and "name" in item
                }
                for new_item in value:
                    if isinstance(new_item, dict) and "name" in new_item:
                        name = new_item["name"]
                        if name in existing_map:
                            _simple_merge_dict(target[key][existing_map[name]], new_item)
                        else:
                            target[key].append(new_item)
                target[key][:] = [
                    item
                    for item in target[key]
                    if not isinstance(item, dict) or "name" not in item or item["name"] in new_names
                ]
            else:
                target[key] = value
        else:
            target[key] = value


def _merge_and_dump_config(config_path: Path, config_data: dict) -> str:
    """将前端提交的 config_data 合并到现有 config.yml，再导出为 YAML 字符串，避免未收集的配置丢失"""
    original = {}
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                original = yaml.safe_load(f)
            if original is None:
                original = {}
        except Exception as e:
            logger.warning(f"读取现有配置失败，将使用前端数据: {e}")
    _simple_merge_dict(original, config_data)
    return yaml.dump(
        original,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )


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
        logger.error(f"获取任务列表失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


def _get_job_description(job_id: str) -> str:
    """根据任务ID获取任务描述"""
    descriptions = {
        "huya_monitor": "虎牙直播状态监控",
        "weibo_monitor": "微博动态监控",
        "bilibili_monitor": "哔哩哔哩动态+直播监控",
        "douyin_monitor": "抖音直播状态监控",
        "douyu_monitor": "斗鱼直播状态监控",
        "xhs_monitor": "小红书动态监控",
        "log_cleanup": "日志文件清理",
        "ikuuu_checkin": "ikuuu 每日签到",
        "tieba_checkin": "百度贴吧签到",
        "weibo_chaohua_checkin": "微博超话签到",
        "rainyun_checkin": "雨云签到",
        "enshan_checkin": "恩山论坛签到",
        "fg_checkin": "富贵论坛签到",
        "aliyun_checkin": "阿里云盘签到",
        "smzdm_checkin": "什么值得买签到",
        "zdm_draw": "值得买每日抽奖",
        "tyyun_checkin": "天翼云盘签到",
        "miui_checkin": "小米社区签到",
        "iqiyi_checkin": "爱奇艺签到",
        "lenovo_checkin": "联想乐豆签到",
        "lbly_checkin": "丽宝乐园签到",
        "pinzan_checkin": "品赞代理签到",
        "dml_checkin": "达美乐任务",
        "xiaomao_checkin": "小茅预约（i茅台）",
        "ydwx_checkin": "一点万象签到",
        "xingkong_checkin": "星空代理签到",
        "qtw_checkin": "千图网签到",
        "freenom_checkin": "Freenom 免费域名续期",
        "weather_push": "天气每日推送",
        "kuake_checkin": "夸克网盘签到",
        "kjwj_checkin": "科技玩家签到",
        "fr_checkin": "帆软社区签到 + 摇摇乐",
        "nine_nine_nine_task": "999 会员中心健康打卡任务",
        "zgfc_draw": "中国福彩抽奖活动",
        "ssq_500w_notice": "双色球开奖通知（守号+冷号机选）",
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
            await run_task_with_logging(task_id, run_func)
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

        # 使 AI 助手配置缓存失效，以便 /api/assistant/status 返回最新状态
        try:
            from src.ai_assistant.config import get_ai_config

            get_ai_config(reload=True)
        except ImportError:
            pass

        return JSONResponse({"success": True, "message": "配置已保存并应用"})
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# 平台配置：table_name, primary_key, filter_query_param
PLATFORM_CONFIG = {
    "weibo": ("weibo", "UID", "uid"),
    "huya": ("huya", "room", "room"),
    "bilibili_live": ("bilibili_live", "uid", "uid"),
    "bilibili_dynamic": ("bilibili_dynamic", "uid", "uid"),
    "douyin": ("douyin", "douyin_id", "id"),
    "douyu": ("douyu", "room", "room"),
    "xhs": ("xhs", "profile_id", "id"),
}
PLATFORM_PRIMARY_KEY = {k: v[1] for k, v in PLATFORM_CONFIG.items()}
VALID_PLATFORMS = frozenset(PLATFORM_CONFIG)


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
        # 兼容旧数据：如果数据库中尚无这些列，SQL 会返回 NULL，这里用空字符串兜底
        "room_pic": row[3] if len(row) > 3 else "",
        "avatar_url": row[4] if len(row) > 4 else "",
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


def _bilibili_live_row_to_item(row: tuple) -> dict:
    return {
        "uid": row[0],
        "uname": row[1],
        "room_id": row[2],
        "is_live": row[3],
        "url": f"https://live.bilibili.com/{row[2]}" if row[2] else "",
    }


def _bilibili_dynamic_row_to_item(row: tuple) -> dict:
    return {
        "uid": row[0],
        "uname": row[1],
        "dynamic_id": row[2],
        "dynamic_text": row[3] or "",
        "url": (
            f"https://www.bilibili.com/opus/{row[2]}"
            if row[2]
            else f"https://space.bilibili.com/{row[0]}"
        ),
    }


def _douyin_row_to_item(row: tuple) -> dict:
    return {
        "douyin_id": row[0],
        "name": row[1],
        "is_live": row[2],
        "url": f"https://live.douyin.com/{row[0]}",
    }


def _douyu_row_to_item(row: tuple) -> dict:
    return {
        "room": row[0],
        "name": row[1],
        "is_live": row[2],
        "url": f"https://www.douyu.com/{row[0]}",
    }


def _xhs_row_to_item(row: tuple) -> dict:
    return {
        "profile_id": row[0],
        "user_name": row[1],
        "latest_note_title": row[2] or "",
        "url": f"https://www.xiaohongshu.com/user/profile/{row[0]}",
    }


def _row_to_item(platform: str, row: tuple) -> dict:
    """根据平台将行转为 API 返回项。"""
    converters = {
        "weibo": _weibo_row_to_item,
        "huya": _huya_row_to_item,
        "bilibili_live": _bilibili_live_row_to_item,
        "bilibili_dynamic": _bilibili_dynamic_row_to_item,
        "douyin": _douyin_row_to_item,
        "douyu": _douyu_row_to_item,
        "xhs": _xhs_row_to_item,
    }
    return converters.get(platform, lambda r: dict(zip(range(len(r)), r)))(row)


# 各平台 SELECT 列与表名
_PLATFORM_SELECT = {
    "weibo": (
        "weibo",
        "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid FROM weibo WHERE UID = :pk",
    ),
    "huya": ("huya", "SELECT room, name, is_live FROM huya WHERE room = :pk"),
    "bilibili_live": (
        "bilibili_live",
        "SELECT uid, uname, room_id, is_live FROM bilibili_live WHERE uid = :pk",
    ),
    "bilibili_dynamic": (
        "bilibili_dynamic",
        "SELECT uid, uname, dynamic_id, dynamic_text FROM bilibili_dynamic WHERE uid = :pk",
    ),
    "douyin": ("douyin", "SELECT douyin_id, name, is_live FROM douyin WHERE douyin_id = :pk"),
    "douyu": ("douyu", "SELECT room, name, is_live FROM douyu WHERE room = :pk"),
    "xhs": (
        "xhs",
        "SELECT profile_id, user_name, latest_note_title FROM xhs WHERE profile_id = :pk",
    ),
}


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
        db = AsyncDatabase()
        await db.initialize()
        _, sql = _PLATFORM_SELECT[platform]
        rows = await db.execute_query(sql, {"pk": item_id})
        await db.close()

        if not rows:
            return JSONResponse({"error": "未找到该资源"}, status_code=404)

        data = _row_to_item(platform, rows[0])
        return JSONResponse({"data": data})
    except Exception as e:
        logger.error(f"获取单条数据失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# 各平台列表查询 SQL（不含 WHERE，含占位符）
_PLATFORM_LIST_SQL = {
    "weibo": "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid FROM weibo",
    # 新增 room_pic / avatar_url 字段，便于前端展示头像和封面图
    "huya": "SELECT room, name, is_live, room_pic, avatar_url FROM huya",
    "bilibili_live": "SELECT uid, uname, room_id, is_live FROM bilibili_live",
    "bilibili_dynamic": "SELECT uid, uname, dynamic_id, dynamic_text FROM bilibili_dynamic",
    "douyin": "SELECT douyin_id, name, is_live FROM douyin",
    "douyu": "SELECT room, name, is_live FROM douyu",
    "xhs": "SELECT profile_id, user_name, latest_note_title FROM xhs",
}


@app.get("/api/data/{platform}")
async def get_table_data(
    request: Request,
    platform: str,
    page: int = 1,
    page_size: int = 100,
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
        db = AsyncDatabase()
        await db.initialize()

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

        base_sql = _PLATFORM_LIST_SQL[platform]
        sql = f"{base_sql}{where_clause} LIMIT :limit OFFSET :offset"
        rows = await db.execute_query(sql, params)

        data = [_row_to_item(platform, row) for row in rows]
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
        except (OSError, PermissionError) as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            try:
                return _do_read_binary()
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
            logger.error(f"读取日志文件超时: {log_file}")
            return JSONResponse({"error": "读取日志超时，请稍后重试"}, status_code=504)

        return JSONResponse({"logs": recent_lines, "total_lines": total_lines})
    except Exception as e:
        logger.error(f"读取日志失败: {e}", exc_info=True)
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
        logger.error(f"获取任务日志列表失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/monitor-status/{platform}/{item_id}")
async def get_monitor_status_item(request: Request, platform: str, item_id: str):
    """按平台与主键 ID 获取单条监控状态（无需登录）。支持所有已持久化的平台。"""
    if platform not in VALID_PLATFORMS:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    try:
        db = AsyncDatabase()
        await db.initialize()

        if platform not in _PLATFORM_SELECT:
            return JSONResponse({"error": "无效的平台"}, status_code=400)

        _, sql = _PLATFORM_SELECT[platform]
        rows = await db.execute_query(sql, {"pk": item_id})

        await db.close()

        if not rows:
            return JSONResponse({"error": "未找到该资源"}, status_code=404)

        # 复用 data 接口的字段定义，monitor-status 只是不需要登录
        data = _row_to_item(platform, rows[0])
        # 对于状态接口，通常不强制返回 url 字段，若有则一并返回，便于前端直接跳转

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


@app.get("/api/monitor-status/{platform}")
async def get_monitor_status_by_platform(request: Request, platform: str):
    """按平台获取监控状态列表（无需登录）。支持所有已持久化的平台。"""
    if platform not in VALID_PLATFORMS:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    try:
        db = AsyncDatabase()
        await db.initialize()

        if platform not in _PLATFORM_LIST_SQL:
            return JSONResponse({"error": "无效的平台"}, status_code=400)

        base_sql = _PLATFORM_LIST_SQL[platform]
        rows = await db.execute_query(base_sql)

        await db.close()

        data = [_row_to_item(platform, row) for row in rows]

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
    """获取全部监控任务状态（无需登录）。返回所有已持久化平台的聚合结果。"""

    try:
        db = AsyncDatabase()
        await db.initialize()

        all_data: dict[str, list[dict]] = {}

        for platform, base_sql in _PLATFORM_LIST_SQL.items():
            try:
                rows = await db.execute_query(base_sql)
                all_data[platform] = [_row_to_item(platform, row) for row in rows]
            except Exception as e:  # 单个平台出错不影响整体
                logger.error(f"获取平台 {platform} 监控状态失败: {e}", exc_info=True)
                all_data[platform] = []

        await db.close()

        return JSONResponse(
            {
                "success": True,
                "data": all_data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"获取监控状态失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# =============================================================================
# AI 助手 API（需登录，ai_assistant.enable 且已安装 ai 依赖时可用）
# =============================================================================


def _assistant_require_auth(request: Request) -> JSONResponse | None:
    """检查登录与 AI 启用，未通过时返回 JSONResponse"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)
    try:
        from src.ai_assistant import is_ai_enabled
        if not is_ai_enabled():
            return JSONResponse(
                {"error": "AI 助手未启用", "hint": "请在 config.yml 中配置 ai_assistant.enable 并安装 uv sync --extra ai"},
                status_code=503,
            )
    except ImportError:
        return JSONResponse(
            {"error": "AI 助手模块不可用", "hint": "请安装 uv sync --extra ai"},
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
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
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


def _parse_executable_intent_and_reply(message: str):
    """
    解析可执行意图（开关监控、配置列表增删）。
    若识别到可执行意图，返回 (reply, suggested_action)；否则返回 (None, None)。
    """
    from src.ai_assistant.intent_parser import parse_toggle_monitor_intent, parse_config_patch_intent

    # 1. 开关监控
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
            + ("关闭后将停止轮询并不再推送相关通知。" if not intent.enable else "开启后将恢复轮询并推送通知。"),
        }
        return reply, suggested_action

    # 2. 配置列表增删（删除虎牙主播100、添加虎牙房间200 等）
    patch = parse_config_patch_intent(message)
    if patch is not None:
        op_text = "添加" if patch.operation == "add" else "移除"
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
    from src.ai_assistant.tools_current_state import parse_platforms_from_message, query_current_state

    cfg = get_ai_config()
    user_id = request.session.get("username", "default")

    if not conversation_id:
        conversation_id = create_conversation(user_id=user_id, title="新对话")

    # 语义理解：优先识别可执行意图（开关监控、配置列表增删）
    reply, suggested_action = _parse_executable_intent_and_reply(message)
    if reply is not None:
        append_messages(conversation_id, user_content=message, assistant_content=reply, user_id=user_id)
        return JSONResponse({
            "reply": reply,
            "conversation_id": conversation_id,
            "suggested_action": suggested_action,
        })

    history = get_messages(conversation_id, max_rounds=cfg.max_history_rounds)

    system_content = SYSTEM_PROMPT
    rag_ctx = retrieve_all(message, context=context)
    if rag_ctx:
        system_content += "\n\n【本次检索到的参考】\n" + rag_ctx
    need_current = (
        "当前" in message or "现在" in message or "谁在直播" in message
        or "最新" in message or "开播" in message or "谁开播" in message or "直播" in message
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

    # 解析回复：优先 config_patch（可执行操作），其次 YAML 代码块（复制配置）
    import json
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
                # 从展示给用户的回复中移除 JSON 块，保持界面简洁
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

    return JSONResponse({
        "reply": reply,
        "conversation_id": conversation_id,
        "suggested_action": suggested_action,
    })


# 允许通过 AI 助手 apply-action 修改的监控平台
TOGGLE_MONITOR_PLATFORMS = frozenset({"weibo", "huya", "bilibili", "douyin", "douyu", "xhs"})

# config_patch 支持的 platform -> list_key 映射
CONFIG_PATCH_PLATFORMS = {
    "weibo": "uids",
    "huya": "rooms",
    "bilibili": "uids",
    "douyin": "douyin_ids",
    "douyu": "rooms",
    "xhs": "profile_ids",
}


def _apply_config_patch(config_path: Path, platform_key: str, list_key: str, operation: str, value: str) -> str:
    """对 config.yml 中的列表字段执行 add/remove，返回新的 YAML 内容（保留其他配置）"""
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    section = data.get(platform_key) or {}
    raw = section.get(list_key) or ""
    items = [x.strip() for x in raw.split(",") if x.strip()]
    val = value.strip()
    if operation == "remove":
        items = [x for x in items if x != val]
    elif operation == "add":
        if val not in items:
            items.append(val)
    else:
        raise ValueError(f"不支持的 operation: {operation}")
    new_value = ",".join(items) if items else ""
    config_data = {platform_key: {list_key: new_value}}
    return _merge_and_dump_config(config_path, config_data)


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

        try:
            config_path = Path("config.yml")
            if not config_path.exists():
                return JSONResponse({"error": "配置文件不存在"}, status_code=404)
            yaml_content = _apply_config_patch(config_path, platform_key, list_key, operation, value)

            import tempfile
            temp_file = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yml", delete=False, encoding="utf-8"
                ) as tmp:
                    tmp.write(yaml_content)
                    temp_file = tmp.name
                try:
                    test_config_dict = load_config_from_yml(temp_file)
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

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(yaml_content)

            get_config(reload=True)
            try:
                from src.ai_assistant.config import get_ai_config
                get_ai_config(reload=True)
            except ImportError:
                pass

            op_text = "添加" if operation == "add" else "移除"
            display = {"weibo": "微博", "huya": "虎牙", "bilibili": "哔哩哔哩", "douyin": "抖音", "douyu": "斗鱼", "xhs": "小红书"}.get(platform_key, platform_key)
            return JSONResponse({"success": True, "message": f"已从{display}监控列表{op_text}「{value}」，配置已热重载"})
        except Exception as e:
            logger.error("apply-action config_patch 执行失败: %s", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    if action != "toggle_monitor":
        return JSONResponse({"error": f"不支持的操作: {action}"}, status_code=400)

    platform_key = body.get("platform_key")
    if platform_key not in TOGGLE_MONITOR_PLATFORMS:
        return JSONResponse({"error": f"不支持的平台: {platform_key}"}, status_code=400)

    enable = body.get("enable")
    if not isinstance(enable, bool):
        return JSONResponse({"error": "enable 须为布尔值"}, status_code=400)

    try:
        config_path = Path("config.yml")
        if not config_path.exists():
            return JSONResponse({"error": "配置文件不存在"}, status_code=404)

        config_data = {platform_key: {"enable": enable}}
        yaml_content = _merge_and_dump_config(config_path, config_data)

        import tempfile
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(yaml_content)
                temp_file = tmp.name
            try:
                test_config_dict = load_config_from_yml(temp_file)
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

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        get_config(reload=True)
        try:
            from src.ai_assistant.config import get_ai_config
            get_ai_config(reload=True)
        except ImportError:
            pass

        action_text = "开启" if enable else "关闭"
        display = {"weibo": "微博", "huya": "虎牙", "bilibili": "哔哩哔哩", "douyin": "抖音", "douyu": "斗鱼", "xhs": "小红书"}.get(platform_key, platform_key)
        return JSONResponse({"success": True, "message": f"已{action_text}{display}监控，配置已热重载"})
    except Exception as e:
        logger.error("apply-action 执行失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/assistant/reindex")
async def assistant_reindex(request: Request):
    """重建 RAG 索引"""
    err = _assistant_require_auth(request)
    if err:
        return err
    from src.ai_assistant.indexer import build_docs_index
    try:
        build_docs_index()
        return JSONResponse({"status": "ok", "message": "索引已重建"})
    except Exception as e:
        logger.error("AI 助手索引重建失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


def create_web_app():
    """创建Web应用实例"""
    return app
