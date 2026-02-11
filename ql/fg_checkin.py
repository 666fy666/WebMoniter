#!/usr/bin/env python3
"""青龙 - 富贵论坛签到。环境变量: WEBMONITER_FG_ENABLE, WEBMONITER_FG_COOKIE"""
from ql._runner import run_task
from tasks.fg_checkin import run_fg_checkin_once
if __name__ == "__main__":
    run_task("fg_checkin", run_fg_checkin_once)
