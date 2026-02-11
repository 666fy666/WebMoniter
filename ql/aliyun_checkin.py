#!/usr/bin/env python3
"""
青龙面板 - 阿里云盘签到脚本

环境变量：
  WEBMONITER_ALIYUN_ENABLE=true
  WEBMONITER_ALIYUN_REFRESH_TOKEN=你的refresh_token
  WEBMONITER_ALIYUN_REFRESH_TOKENS=多个用,分隔（可选）

定时规则建议：30 5 * * *
"""

from ql._runner import run_task
from tasks.aliyun_checkin import run_aliyun_checkin_once

if __name__ == "__main__":
    run_task("aliyun_checkin", run_aliyun_checkin_once)
