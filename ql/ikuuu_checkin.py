#!/usr/bin/env python3
"""
青龙面板 - iKuuu 签到脚本

环境变量（在青龙「环境变量」中配置）：
  WEBMONITER_CHECKIN_ENABLE=true
  WEBMONITER_CHECKIN_EMAIL=邮箱
  WEBMONITER_CHECKIN_PASSWORD=密码
  # 多账号：WEBMONITER_CHECKIN_ACCOUNTS=[{"email":"a@b.com","password":"xx"},...]

定时规则建议：0 8 * * * （每天 8:00）
"""
import os
import sys

_ql_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_ql_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

from ql._runner import run_task
from tasks.ikuuu_checkin import run_checkin_once

if __name__ == "__main__":
    run_task("ikuuu_checkin", run_checkin_once)
