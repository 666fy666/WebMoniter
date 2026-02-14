#!/usr/bin/env python3
"""青龙 - 天翼云盘签到。环境变量: WEBMONITER_TYYUN_ENABLE, WEBMONITER_TYYUN_USERNAME, WEBMONITER_TYYUN_PASSWORD"""
import os
import sys

_ql_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_ql_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

from ql._runner import run_task
from tasks.tyyun_checkin import run_tyyun_checkin_once

if __name__ == "__main__":
    run_task("tyyun_checkin", run_tyyun_checkin_once)
