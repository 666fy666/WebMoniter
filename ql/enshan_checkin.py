#!/usr/bin/env python3
"""青龙 - 恩山论坛签到。环境变量: WEBMONITER_ENSHAN_ENABLE, WEBMONITER_ENSHAN_COOKIE"""
from ql._runner import run_task
from tasks.enshan_checkin import run_enshan_checkin_once

if __name__ == "__main__":
    run_task("enshan_checkin", run_enshan_checkin_once)
