"""config.yml 的校验、并发保护与定点更新。"""

from __future__ import annotations

import asyncio
import copy
import errno
import os
import stat
import tempfile
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import ScalarString

from src.core.paths import CONFIG_YAML_FILE
from src.settings.config import AppConfig, config_file_lock, get_config, load_config_from_yml


class ConfigWriteError(RuntimeError):
    """配置校验或写入失败。"""


@dataclass(frozen=True)
class ConfigValueUpdate:
    """仅当 path 当前值仍等于 expected 时，将其替换为 value。"""

    path: tuple[str, ...]
    expected: Any
    value: Any


@dataclass(frozen=True)
class ConfigUpdateResult:
    applied_paths: tuple[str, ...]
    changed_paths: tuple[str, ...]
    conflict_paths: tuple[str, ...]
    wrote_file: bool


def _validate_yaml_content(yaml_content: str) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yml",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(yaml_content)
            temp_path = Path(tmp.name)
        AppConfig(**load_config_from_yml(str(temp_path)))
    except Exception as exc:  # noqa: BLE001
        raise ConfigWriteError(f"配置验证失败: {exc}") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _write_text_with_bind_mount_fallback(config_path: Path, yaml_content: str) -> None:
    """优先原子替换；Docker 单文件 bind mount 不允许替换时安全回退为原位写入。"""
    config_path = config_path.resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    original_text = config_path.read_text(encoding="utf-8") if config_path.exists() else None
    original_mode = (
        stat.S_IMODE(config_path.stat().st_mode) if config_path.exists() else 0o600
    )

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{config_path.name}.",
        suffix=".tmp",
        dir=config_path.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(yaml_content)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.chmod(temp_path, original_mode)

        try:
            os.replace(temp_path, config_path)
            return
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EBUSY, errno.EPERM, errno.EXDEV}:
                raise

        try:
            with open(config_path, "w", encoding="utf-8") as target:
                target.write(yaml_content)
                target.flush()
                os.fsync(target.fileno())
            os.chmod(config_path, original_mode)
        except Exception:
            if original_text is not None:
                with open(config_path, "w", encoding="utf-8") as target:
                    target.write(original_text)
                    target.flush()
                    os.fsync(target.fileno())
                os.chmod(config_path, original_mode)
            raise
    except Exception as exc:  # noqa: BLE001
        raise ConfigWriteError(f"写入配置文件失败: {type(exc).__name__}: {exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)


def _reload_runtime_config(config_path: Path) -> None:
    if config_path.resolve() == CONFIG_YAML_FILE.resolve():
        get_config(reload=True)


def _validate_and_write_locked(yaml_content: str, config_path: Path) -> None:
    _validate_yaml_content(yaml_content)
    _write_text_with_bind_mount_fallback(config_path, yaml_content)
    _reload_runtime_config(config_path)


def _run_write_transaction_sync(
    config_path: Path,
    content_builder: Callable[[], str],
) -> None:
    with config_file_lock():
        yaml_content = content_builder()
        _validate_and_write_locked(yaml_content, config_path)


async def run_write_transaction(
    config_path: Path,
    content_builder: Callable[[], str],
) -> None:
    """在共享锁内构建、校验并写入完整 YAML。"""
    await asyncio.to_thread(_run_write_transaction_sync, config_path, content_builder)


def _round_trip_yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    return yaml


def _get_path_value(root: Any, path: tuple[str, ...]) -> tuple[bool, Any]:
    current = root
    for key in path:
        if not isinstance(current, MutableMapping) or key not in current:
            return False, None
        current = current[key]
    return True, current


def _styled_scalar(old_value: Any, new_value: Any) -> Any:
    if isinstance(old_value, ScalarString) and isinstance(new_value, str):
        return type(old_value)(new_value)
    return copy.deepcopy(new_value)


def _set_path_value(root: Any, path: tuple[str, ...], value: Any) -> None:
    parent = root
    for key in path[:-1]:
        parent = parent[key]
    key = path[-1]
    old_value = parent[key]
    if isinstance(old_value, list) and isinstance(value, list):
        old_value[:] = [
            _styled_scalar(old_value[idx] if idx < len(old_value) else None, item)
            for idx, item in enumerate(value)
        ]
        return
    parent[key] = _styled_scalar(old_value, value)


def _apply_config_updates_sync(
    config_path: Path,
    updates: list[ConfigValueUpdate],
) -> ConfigUpdateResult:
    config_path = config_path.resolve()
    with config_file_lock():
        if not config_path.exists():
            raise ConfigWriteError(f"配置文件不存在: {config_path}")

        yaml = _round_trip_yaml()
        try:
            with open(config_path, encoding="utf-8") as source:
                document = yaml.load(source)
        except Exception as exc:  # noqa: BLE001
            raise ConfigWriteError(f"读取配置文件失败: {type(exc).__name__}: {exc}") from exc
        if not isinstance(document, MutableMapping):
            raise ConfigWriteError("配置文件根节点必须是映射")

        applied: list[str] = []
        changed: list[str] = []
        conflicts: list[str] = []
        for update in updates:
            path_text = ".".join(update.path)
            found, current = _get_path_value(document, update.path)
            if not found or current != update.expected:
                conflicts.append(path_text)
                continue
            applied.append(path_text)
            if current == update.value:
                continue
            _set_path_value(document, update.path, update.value)
            changed.append(path_text)

        if not changed:
            return ConfigUpdateResult(
                applied_paths=tuple(applied),
                changed_paths=(),
                conflict_paths=tuple(conflicts),
                wrote_file=False,
            )

        output = StringIO()
        yaml.dump(document, output)
        _validate_and_write_locked(output.getvalue(), config_path)
        return ConfigUpdateResult(
            applied_paths=tuple(applied),
            changed_paths=tuple(changed),
            conflict_paths=tuple(conflicts),
            wrote_file=True,
        )


async def apply_config_updates(
    config_path: Path,
    updates: list[ConfigValueUpdate],
) -> ConfigUpdateResult:
    """按 compare-and-swap 语义更新若干配置字段。"""
    return await asyncio.to_thread(_apply_config_updates_sync, config_path, updates)
