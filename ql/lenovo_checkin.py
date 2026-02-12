#!/usr/bin/env python3
"""青龙 - 联想乐豆签到。环境变量: WEBMONITER_LENOVO_ENABLE, WEBMONITER_LENOVO_ACCESS_TOKEN"""
from ql._runner import run_task
from tasks.lenovo_checkin import run_lenovo_checkin_once

if __name__ == "__main__":
    run_task("lenovo_checkin", run_lenovo_checkin_once)
