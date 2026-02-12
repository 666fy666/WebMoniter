#!/usr/bin/env python3
"""青龙 - 千图网签到。环境变量: WEBMONITER_QTW_ENABLE, WEBMONITER_QTW_COOKIE"""
from ql._runner import run_task
from tasks.qtw_checkin import run_qtw_checkin_once

if __name__ == "__main__":
    run_task("qtw_checkin", run_qtw_checkin_once)
