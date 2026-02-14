#!/usr/bin/env python3
"""青龙 - 中国福彩抽奖。环境变量: WEBMONITER_ZGFC_ENABLE, WEBMONITER_ZGFC_TOKENS"""
import os
import sys

_ql_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_ql_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

from ql._runner import run_task
from tasks.zgfc_draw import run_zgfc_draw_once

if __name__ == "__main__":
    run_task("zgfc_draw", run_zgfc_draw_once)
