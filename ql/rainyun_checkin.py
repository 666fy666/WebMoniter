#!/usr/bin/env python3
"""
青龙面板 - 雨云签到脚本

环境变量：
  WEBMONITER_RAINYUN_ENABLE=true
  WEBMONITER_RAINYUN_API_KEY=你的APIKey
  WEBMONITER_RAINYUN_API_KEYS=多个key用,分隔（可选）

定时规则建议：30 8 * * *
"""

from ql._runner import run_task
from tasks.rainyun_checkin import run_rainyun_checkin_once

if __name__ == "__main__":
    run_task("rainyun_checkin", run_rainyun_checkin_once)
