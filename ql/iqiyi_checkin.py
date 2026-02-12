#!/usr/bin/env python3
"""青龙 - 爱奇艺签到。环境变量: WEBMONITER_IQIYI_ENABLE, WEBMONITER_IQIYI_COOKIE"""
from ql._runner import run_task
from tasks.iqiyi_checkin import run_iqiyi_checkin_once

if __name__ == "__main__":
    run_task("iqiyi_checkin", run_iqiyi_checkin_once)
