"""Configuration API routes."""

import asyncio
import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from src.web.auth import check_login
from src.web.config_io import (
    RUAMEL_AVAILABLE,
    RUAMEL_YAML,
    _merge_and_dump_config,
    _merge_push_channel_list,
    _validate_and_save_config,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/config")
async def get_config_api(request: Request, format: str = "json"):
    """获取配置文件内容"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

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
    """保存配置文件"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        try:
            json_data = await request.json()

            if "content" in json_data:
                yaml_content = json_data["content"]
                try:
                    yaml.safe_load(yaml_content)
                except yaml.YAMLError as e:
                    return JSONResponse({"error": f"YAML格式错误: {str(e)}"}, status_code=400)
            else:
                config_data = json_data.get("config")
                if config_data is None:
                    config_data = json_data

                if not config_data:
                    return JSONResponse({"error": "配置数据为空"}, status_code=400)

                config_path = Path("config.yml")
                if RUAMEL_AVAILABLE and config_path.exists():
                    try:
                        ruamel_yaml = RUAMEL_YAML()
                        ruamel_yaml.preserve_quotes = True
                        ruamel_yaml.width = 4096
                        ruamel_yaml.indent(mapping=2, sequence=4, offset=2)
                        ruamel_yaml.default_flow_style = False
                        ruamel_yaml.allow_unicode = True

                        with open(config_path, encoding="utf-8") as f:
                            original_yaml = ruamel_yaml.load(f)

                        if original_yaml is None:
                            original_yaml = {}

                        def update_dict(target, source):
                            """递归更新字典，保留原始结构。空列表 cookies/accounts 不写入，避免污染 YAML。"""
                            from ruamel.yaml.comments import CommentedSeq

                            for key, value in source.items():
                                if (
                                    key in ("cookies", "accounts")
                                    and isinstance(value, list)
                                    and len(value) == 0
                                ):
                                    if key in target and isinstance(target[key], list):
                                        del target[key]
                                    continue
                                if key == "push_channels":
                                    new_list = CommentedSeq(value if value else [])
                                    new_list.fa.set_flow_style()
                                    target[key] = new_list
                                    continue
                                if key not in target:
                                    target[key] = value
                                elif isinstance(target[key], dict) and isinstance(value, dict):
                                    update_dict(target[key], value)
                                elif isinstance(target[key], list) and isinstance(value, list):
                                    if (
                                        key == "push_channel"
                                        and len(target[key]) > 0
                                        and len(value) > 0
                                    ):
                                        _merge_push_channel_list(target[key], value)
                                    else:
                                        target[key] = value
                                else:
                                    target[key] = value

                        update_dict(original_yaml, config_data)

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
                    try:
                        yaml_content = _merge_and_dump_config(config_path, config_data)
                    except Exception as ex:
                        return JSONResponse(
                            {"error": f"合并并转换YAML失败: {str(ex)}"}, status_code=400
                        )
        except Exception:
            form_data = await request.form()
            content = form_data.get("content")
            if content:
                yaml_content = content
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
