#!/usr/bin/env python3
"""青龙 - 品赞签到。环境变量: WEBMONITER_PINZAN_ENABLE, WEBMONITER_PINZAN_ACCOUNT, WEBMONITER_PINZAN_PASSWORD"""
import os
import sys

_ql_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_ql_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

from ql._runner import run_task
from tasks.pinzan_checkin import run_pinzan_checkin_once

if __name__ == "__main__":
    run_task("pinzan_checkin", run_pinzan_checkin_once)
