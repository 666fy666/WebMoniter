#!/usr/bin/env python3
"""
青龙面板 - 百度贴吧签到脚本

环境变量：
  WEBMONITER_TIEBA_ENABLE=true
  WEBMONITER_TIEBA_COOKIE=你的BDUSScookie
  WEBMONITER_TIEBA_COOKIES=多个cookie用|分隔（可选）

定时规则建议：10 8 * * *
"""
import os
import sys

_ql_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_ql_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

from ql._runner import run_task
from tasks.tieba_checkin import run_tieba_checkin_once

if __name__ == "__main__":
    run_task("tieba_checkin", run_tieba_checkin_once)
