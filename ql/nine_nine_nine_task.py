#!/usr/bin/env python3
"""青龙 - 999 会员中心任务。环境变量: WEBMONITER_NINE_NINE_NINE_ENABLE, WEBMONITER_NINE_NINE_NINE_TOKENS"""
import os
import sys

_ql_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_ql_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

from ql._runner import run_task
from tasks.nine_nine_nine_task import run_nine_nine_nine_task_once

if __name__ == "__main__":
    run_task("nine_nine_nine_task", run_nine_nine_nine_task_once)
