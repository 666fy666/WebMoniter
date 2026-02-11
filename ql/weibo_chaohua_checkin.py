#!/usr/bin/env python3
"""
青龙面板 - 微博超话签到脚本

环境变量：
  WEBMONITER_WEIBO_CHAOHUA_ENABLE=true
  WEBMONITER_WEIBO_CHAOHUA_COOKIE=包含XSRF-TOKEN的cookie
  WEBMONITER_WEIBO_CHAOHUA_COOKIES=多个用|分隔（可选）

定时规则建议：45 23 * * *
"""

from ql._runner import run_task
from tasks.weibo_chaohua_checkin import run_weibo_chaohua_checkin_once

if __name__ == "__main__":
    run_task("weibo_chaohua_checkin", run_weibo_chaohua_checkin_once)
