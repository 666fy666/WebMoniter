#!/usr/bin/env python3
"""
青龙面板 - 阿里云盘签到脚本

环境变量：
  WEBMONITER_ALIYUN_ENABLE=true
  WEBMONITER_ALIYUN_REFRESH_TOKEN=你的refresh_token
  WEBMONITER_ALIYUN_REFRESH_TOKENS=多个用,分隔（可选）

定时规则建议：30 5 * * *
"""
import os
import sys

_ql_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_ql_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

from ql._runner import run_task
from tasks.aliyun_checkin import run_aliyun_checkin_once

if __name__ == "__main__":
    run_task("aliyun_checkin", run_aliyun_checkin_once)
