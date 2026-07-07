"""Configuration API routes."""

import asyncio
import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from src.jobs.metadata import (
    CONFIG_SECTION_ORDER,
    MONITOR_SPECS,
    PUSH_CHANNEL_SPECS,
    TASK_SPECS,
)
from src.web.auth import check_login
from src.web.config_io import _validate_and_save_config, merge_config_to_yaml

logger = logging.getLogger(__name__)
router = APIRouter()


def _unauthorized_response() -> JSONResponse:
    return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)


def _validate_yaml_content(yaml_content: str) -> JSONResponse | None:
    try:
        yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        return JSONResponse({"error": f"YAML格式错误: {str(e)}"}, status_code=400)
    return None


@router.get("/api/config/metadata")
async def get_config_metadata_api(request: Request):
    """获取配置页所需的只读元数据。"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return _unauthorized_response()

    def _task_to_json(spec):
        return {
            "job_id": spec.job_id,
            "kind": spec.kind,
            "module_path": spec.module,
            "description": spec.description,
            "config_section": spec.config_section,
            "enable_field": spec.enable_field,
            "time_field": spec.time_field,
            "default_time": spec.default_time,
            "interval_field": spec.interval_field,
            "push_field": spec.push_field,
            "push_container_id": spec.push_container_id,
            "env_prefix": spec.ql_prefix,
            "env_extra_fields": dict(spec.ql_extra_env),
            "plugin_only": spec.plugin_only,
        }

    return JSONResponse(
        {
            "sections": list(CONFIG_SECTION_ORDER),
            "tasks": [_task_to_json(spec) for spec in (*MONITOR_SPECS, *TASK_SPECS)],
            "push_channel_types": {
                spec.type: {"name": spec.name, "fields": list(spec.fields)}
                for spec in PUSH_CHANNEL_SPECS
            },
        }
    )


@router.get("/api/config")
async def get_config_api(request: Request, format: str = "json"):
    """获取配置文件内容。"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return _unauthorized_response()

    try:
        config_path = Path("config.yml")
        if not config_path.exists():
            return JSONResponse({"error": "配置文件不存在"}, status_code=404)

        if format == "yaml":
            content = await asyncio.to_thread(lambda: config_path.read_text(encoding="utf-8"))
            return JSONResponse({"content": content})

        def _read_config_json():
            with open(config_path, encoding="utf-8") as f:
                return yaml.safe_load(f)

        yaml_data = await asyncio.to_thread(_read_config_json)
        return JSONResponse({"config": yaml_data})
    except Exception as e:
        logger.error("读取配置文件失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/config")
async def save_config_api(request: Request):
    """保存配置文件。"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return _unauthorized_response()

    try:
        try:
            json_data = await request.json()

            if "content" in json_data:
                yaml_content = json_data["content"]
                err = _validate_yaml_content(yaml_content)
                if err:
                    return err
            else:
                config_data = json_data.get("config")
                if config_data is None:
                    config_data = json_data

                if not config_data:
                    return JSONResponse({"error": "配置数据为空"}, status_code=400)

                config_path = Path("config.yml")
                try:
                    yaml_content = merge_config_to_yaml(config_path, config_data)
                except Exception as ex:
                    return JSONResponse(
                        {"error": f"合并并转换YAML失败: {str(ex)}"}, status_code=400
                    )
        except Exception:
            form_data = await request.form()
            content = form_data.get("content")
            if content:
                yaml_content = content
                err = _validate_yaml_content(yaml_content)
                if err:
                    return err
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
