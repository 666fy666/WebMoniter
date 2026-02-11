"""
青龙单任务运行器 - 供 ql/*.py 脚本调用

负责：切换到项目根目录、注入环境变量配置、执行任务。
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

# 切换到项目根目录（ql 的父目录）
_QL_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_QL_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

# 标记为青龙 cron 模式（供 ql_compat 检测）
os.environ["WEBMONITER_QL_CRON"] = "1"


def run_task(task_id: str, run_func) -> None:
    """
    在青龙环境下运行指定任务。

    Args:
        task_id: 任务 ID，如 'ikuuu_checkin'
        run_func: 任务的 async 执行函数
    """
    from src.ql_compat import inject_ql_config

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    inject_ql_config(task_id)
    asyncio.run(run_func())
