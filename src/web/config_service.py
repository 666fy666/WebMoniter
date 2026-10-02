"""Versioned configuration editing, schema hints and opaque secret references."""

import copy
import hashlib
import hmac
import json
import secrets
from dataclasses import asdict
from pathlib import Path

import yaml

from src.core.paths import CONFIG_YAML_FILE, PROJECT_ROOT
from src.jobs.metadata import MONITOR_SPECS, PUSH_CHANNEL_SPECS, TASK_SPECS
from src.settings.config import AppConfig, config_file_lock
from src.settings.config_writer import run_write_transaction
from src.settings.loader_specs import CONFIG_MAPPINGS, MULTI_ACCOUNT_SPECS, MULTI_STRING_SPECS
from src.web.config_io import merge_config_to_yaml

_mask_key = secrets.token_bytes(32)
_prefix = "__KEEP_SECRET__:"


class ConfigConflictError(ValueError):
    pass


def secret_field(key: str) -> bool:
    key = key.lower()
    if key.endswith(("_enable", "_enabled", "_time", "_timeout", "_interval_seconds")):
        return False
    return any(
        part in key
        for part in (
            "password",
            "passwd",
            "cookie",
            "token",
            "secret",
            "api_key",
            "authorization",
            "request_body",
            "request_bodies",
            "device_params",
            "_key",
        )
    ) or key in {
        "key",
        "sckey",
        "sendkey",
        "openid",
        "openids",
        "webhook",
        "url",
        "payload",
        "headers",
    }


def mask(value, key: str = "", references: dict | None = None):
    if isinstance(value, dict):
        return {k: mask(v, key if secret_field(key) else k, references) for k, v in value.items()}
    if isinstance(value, list):
        return [mask(v, key, references) for v in value]
    if secret_field(key) and value not in (None, ""):
        digest = hmac.new(
            _mask_key, json.dumps(value, ensure_ascii=False).encode(), hashlib.sha256
        ).hexdigest()
        token = _prefix + digest
        if references is not None:
            references[token] = value
        return token
    return value


def restore(value, references: dict):
    if isinstance(value, dict):
        return {k: restore(v, references) for k, v in value.items()}
    if isinstance(value, list):
        return [restore(v, references) for v in value]
    if isinstance(value, str) and value.startswith(_prefix):
        if value not in references:
            raise ConfigConflictError("密钥引用已过期，请重新加载配置")
        return references[value]
    return value


def read_config(path: Path = CONFIG_YAML_FILE, *, reveal: bool = False) -> dict:
    with config_file_lock():
        text = path.read_text(encoding="utf-8")
        result = {"version": hashlib.sha256(text.encode()).hexdigest()}
        result.update({"content": text} if reveal else {"config": mask(yaml.safe_load(text) or {})})
        return result


async def write_config(
    version: str,
    patch: dict | None = None,
    content: str | None = None,
    path: Path = CONFIG_YAML_FILE,
) -> None:
    def build():
        current = path.read_text(encoding="utf-8")
        if not hmac.compare_digest(hashlib.sha256(current.encode()).hexdigest(), version):
            raise ConfigConflictError("配置已被其他操作修改，请重新加载后保存")
        document = yaml.safe_load(current) or {}
        if content is not None:
            candidate = yaml.safe_load(content)
            if not isinstance(candidate, dict):
                raise ValueError("配置根节点必须为映射")
            return content
        references: dict = {}
        mask(document, references=references)
        restored = restore(patch, references)
        if not isinstance(restored, dict):
            raise ValueError("配置补丁必须为映射")
        return merge_config_to_yaml(path, restored)

    await run_write_transaction(path, build)


def metadata() -> dict:
    sample = yaml.safe_load((PROJECT_ROOT / "config/config.yml.sample").read_text())
    schema = AppConfig.model_json_schema()["properties"]
    accounts = {spec.section_key: list(spec.fields) for spec in MULTI_ACCOUNT_SPECS}
    strings = {spec.section_key: spec.yaml_key for spec in MULTI_STRING_SPECS}
    fields = {}
    for section, mapping in CONFIG_MAPPINGS.items():
        fields[section] = {}
        for key, flat in mapping.items():
            definition = schema.get(flat, {})
            fields[section][key] = {
                "label": definition.get("description", key),
                "secret": secret_field(key),
                "minimum": definition.get("minimum"),
                "maximum": definition.get("maximum"),
            }

    def empty_secrets(value):
        if isinstance(value, dict):
            return {
                k: ("" if secret_field(k) and not isinstance(v, (dict, list)) else empty_secrets(v))
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [empty_secrets(v) for v in value]
        return value

    defaults = empty_secrets(copy.deepcopy(sample))
    for value in defaults.values():
        if isinstance(value, dict):
            for key in ("enable", "enabled", "cookie_refresh_enable"):
                if key in value:
                    value[key] = False
    defaults["push_channel"] = []
    for section, keys in accounts.items():
        defaults.setdefault(section, {}).setdefault("accounts", [])
    for section, key in strings.items():
        defaults.setdefault(section, {}).setdefault(key, [])
    return {
        "defaults": defaults,
        "fields": fields,
        "accounts": accounts,
        "strings": strings,
        "tasks": [asdict(spec) for spec in (*MONITOR_SPECS, *TASK_SPECS)],
        "push_channels": [asdict(spec) for spec in PUSH_CHANNEL_SPECS],
    }
