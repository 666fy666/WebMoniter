#!/usr/bin/env python3
"""青龙 - 小米社区签到。环境变量: WEBMONITER_MIUI_ENABLE, WEBMONITER_MIUI_ACCOUNT, WEBMONITER_MIUI_PASSWORD"""
import os
import sys

_ql_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_ql_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

from ql._runner import run_task
from tasks.miui_checkin import run_miui_checkin_once

if __name__ == "__main__":
    run_task("miui_checkin", run_miui_checkin_once)
