#!/usr/bin/env python3
"""青龙 - 夸克网盘签到。环境变量: WEBMONITER_KUAKE_ENABLE, WEBMONITER_KUAKE_COOKIE"""
from ql._runner import run_task
from tasks.kuake_checkin import run_kuake_checkin_once

if __name__ == "__main__":
    run_task("kuake_checkin", run_kuake_checkin_once)
