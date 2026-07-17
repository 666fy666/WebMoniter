"""Web 配置文件合并、补丁与保存校验。"""

import logging
from io import StringIO
from pathlib import Path

import yaml
from fastapi.responses import JSONResponse

from src.settings.config_writer import ConfigWriteError, run_write_transaction

logger = logging.getLogger(__name__)

try:
    from ruamel.yaml import YAML as RUAMEL_YAML

    RUAMEL_AVAILABLE = True
except ImportError:
    RUAMEL_AVAILABLE = False
    RUAMEL_YAML = None


_OPTIONAL_LIST_KEYS = frozenset({"cookies", "accounts"})


def _should_remove_empty_optional_list(key: str, value) -> bool:
    return key in _OPTIONAL_LIST_KEYS and isinstance(value, list) and len(value) == 0


def _merge_push_channel_list(target: list, source: list) -> None:
    """按 name 合并推送通道：整项替换而非递归合并，以便清空 user_id 等可选字段。"""
    if not source:
        return
    existing_map = {
        item.get("name"): idx
        for idx, item in enumerate(target)
        if isinstance(item, dict) and "name" in item
    }
    new_names = {item.get("name") for item in source if isinstance(item, dict) and "name" in item}
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
        if _should_remove_empty_optional_list(key, value):
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


def _update_ruamel_dict(target, source: dict) -> None:
    """Merge config while preserving ruamel comments/style where possible."""
    from ruamel.yaml.comments import CommentedSeq

    for key, value in source.items():
        if _should_remove_empty_optional_list(key, value):
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
            _update_ruamel_dict(target[key], value)
        elif isinstance(target[key], list) and isinstance(value, list):
            if key == "push_channel" and len(target[key]) > 0 and len(value) > 0:
                _merge_push_channel_list(target[key], value)
            else:
                target[key] = value
        else:
            target[key] = value


def _merge_and_dump_config_ruamel(config_path: Path, config_data: dict) -> str:
    """Merge config with ruamel.yaml so existing comments and quotes are preserved."""
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

    _update_ruamel_dict(original_yaml, config_data)

    output = StringIO()
    ruamel_yaml.dump(original_yaml, output)
    return output.getvalue()


def merge_config_to_yaml(config_path: Path, config_data: dict) -> str:
    """Merge frontend config into the existing YAML file and return YAML text."""
    if RUAMEL_AVAILABLE and config_path.exists():
        try:
            return _merge_and_dump_config_ruamel(config_path, config_data)
        except Exception as e:
            logger.warning("ruamel.yaml merge failed, falling back to PyYAML: %s", e)
    return _merge_and_dump_config(config_path, config_data)


async def _validate_and_save_config(yaml_content: str, config_path: Path) -> JSONResponse | None:
    """在共享配置锁内校验并保存完整 YAML。"""
    try:
        await run_write_transaction(config_path, lambda: yaml_content)
    except ConfigWriteError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"保存配置失败: {exc}"}, status_code=400)

    return None


async def _merge_and_validate_and_save_config(
    config_path: Path,
    config_data: dict,
) -> JSONResponse | None:
    """在同一事务中读取最新配置、合并前端补丁、校验并保存。"""
    try:
        await run_write_transaction(
            config_path,
            lambda: merge_config_to_yaml(config_path, config_data),
        )
    except ConfigWriteError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"合并并转换YAML失败: {exc}"}, status_code=400)
    return None
