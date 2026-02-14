#!/usr/bin/env python3
"""
青龙面板 - 雨云签到脚本

环境变量：
  WEBMONITER_RAINYUN_ENABLE=true
  单账号：WEBMONITER_RAINYUN_USERNAME=用户名  WEBMONITER_RAINYUN_PASSWORD=密码
  多账号：WEBMONITER_RAINYUN_ACCOUNTS=[{"username":"u1","password":"p1","api_key":"可选"}]
  WEBMONITER_RAINYUN_API_KEY=可选，用于续费（单账号时）
  WEBMONITER_RAINYUN_TIME=08:30（可选）

定时规则建议：30 8 * * *
"""
import os
import sys

# 确保项目根在 path 中，便于青龙任意目录执行时能 import ql
_ql_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_ql_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

from ql._runner import run_task
from tasks.rainyun_checkin import run_rainyun_checkin_once

if __name__ == "__main__":
    run_task("rainyun_checkin", run_rainyun_checkin_once)
