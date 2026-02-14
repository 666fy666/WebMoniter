#!/usr/bin/env python3
"""青龙 - 爱奇艺签到。环境变量: WEBMONITER_IQIYI_ENABLE, WEBMONITER_IQIYI_COOKIE"""
import os
import sys

_ql_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_ql_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

from ql._runner import run_task
from tasks.iqiyi_checkin import run_iqiyi_checkin_once

if __name__ == "__main__":
    run_task("iqiyi_checkin", run_iqiyi_checkin_once)
