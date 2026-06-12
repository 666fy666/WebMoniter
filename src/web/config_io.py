"""Web 配置文件合并、补丁与保存校验。"""

import asyncio
import logging
import tempfile
from pathlib import Path

import yaml
from fastapi.responses import JSONResponse

from src.settings.config import AppConfig, get_config, load_config_from_yml

logger = logging.getLogger(__name__)

try:
    from ruamel.yaml import YAML as RUAMEL_YAML

    RUAMEL_AVAILABLE = True
except ImportError:
    RUAMEL_AVAILABLE = False
    RUAMEL_YAML = None


def _merge_push_channel_list(target: list, source: list) -> None:
    """按 name 合并推送通道：整项替换而非递归合并，以便清空 user_id 等可选字段。"""
    if not source:
        return
    existing_map = {
        item.get("name"): idx
        for idx, item in enumerate(target)
        if isinstance(item, dict) and "name" in item
    }
    new_names = {
        item.get("name") for item in source if isinstance(item, dict) and "name" in item
    }
    for new_item in source:
        if not isinstance(new_item, dict) or "name" not in new_item:
            continue
        name = new_item["name"]
        if name in existing_map:
            target[existing_map[name]] = new_item
        else:
            target.append(new_item)
    target[:] = [
        item
        for item in target
        if not isinstance(item, dict) or "name" not in item or item["name"] in new_names
    ]


def _simple_merge_dict(target: dict, source: dict) -> None:
    """递归合并 source 到 target，避免前端未收集的配置丢失。"""
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
                _merge_push_channel_list(target[key], value)
            else:
                target[key] = value
        else:
            target[key] = value


def _merge_and_dump_config(config_path: Path, config_data: dict) -> str:
    """合并前端提交配置到现有 config.yml，并导出 YAML 字符串。"""
    original = {}
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                original = yaml.safe_load(f)
            if original is None:
                original = {}
        except Exception as e:
            logger.warning("读取现有配置失败，将使用前端数据: %s", e)
    _simple_merge_dict(original, config_data)
    return yaml.dump(
        original,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )


def _apply_config_patch(
    config_path: Path, platform_key: str, list_key: str, operation: str, value: str
) -> str:
    """对 config.yml 中的列表字段执行 add/remove，返回新的 YAML 内容。"""
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


async def _validate_and_save_config(yaml_content: str, config_path: Path) -> JSONResponse | None:
    """
    验证 YAML 内容并保存到 config.yml。

    成功返回 None；失败返回错误 JSONResponse。验证流程：
    写入临时文件 -> load_config_from_yml -> AppConfig 校验 -> 写入正式文件 -> 热重载。
    """
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(yaml_content)
            temp_file = tmp.name

        try:
            test_config_dict = load_config_from_yml(temp_file)
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

    await asyncio.to_thread(config_path.write_text, yaml_content, encoding="utf-8")

    try:
        get_config(reload=True)
    except Exception as e:
        logger.warning("热重载失败: %s", e)

    return None
