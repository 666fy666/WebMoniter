#!/usr/bin/env python3
"""青龙 - 联想乐豆签到。环境变量: WEBMONITER_LENOVO_ENABLE, WEBMONITER_LENOVO_ACCESS_TOKEN"""
import os
import sys

_ql_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_ql_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

from ql._runner import run_task
from tasks.lenovo_checkin import run_lenovo_checkin_once

if __name__ == "__main__":
    run_task("lenovo_checkin", run_lenovo_checkin_once)
