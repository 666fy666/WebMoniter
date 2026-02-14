#!/usr/bin/env python3
"""青龙 - 一点万象签到。环境变量: WEBMONITER_YDWX_ENABLE, WEBMONITER_YDWX_DEVICE_PARAMS, WEBMONITER_YDWX_TOKEN"""
import os
import sys

_ql_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_ql_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

from ql._runner import run_task
from tasks.ydwx_checkin import run_ydwx_checkin_once

if __name__ == "__main__":
    run_task("ydwx_checkin", run_ydwx_checkin_once)
