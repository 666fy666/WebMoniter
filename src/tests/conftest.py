"""测试辅助：安全重载任务模块（跳过缺少可选依赖的模块）。"""

from __future__ import annotations

import importlib
import logging
import sys

logger = logging.getLogger(__name__)

# 依赖 rainyun extra（Selenium、ddddocr 等），dev 环境未安装时应跳过
OPTIONAL_IMPORT_MODULES: frozenset[str] = frozenset({"src.tasks.rainyun_checkin"})


def _reload_or_import(mod_name: str):
    if mod_name in sys.modules:
        return importlib.reload(sys.modules[mod_name])
    return importlib.import_module(mod_name)


def safe_reload_modules(module_paths: list[str]) -> list[str]:
    """重载模块以重新执行 register_*；返回导入/重载失败的模块路径。"""
    failed: list[str] = []
    for mod_name in module_paths:
        if mod_name in OPTIONAL_IMPORT_MODULES:
            try:
                _reload_or_import(mod_name)
            except Exception as exc:
                logger.debug("跳过可选依赖模块 %s: %s", mod_name, exc)
                failed.append(mod_name)
            continue
        try:
            _reload_or_import(mod_name)
        except Exception as exc:
            logger.debug("重载模块失败 %s: %s", mod_name, exc)
            failed.append(mod_name)
    return failed
