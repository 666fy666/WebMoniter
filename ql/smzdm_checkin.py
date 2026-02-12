#!/usr/bin/env python3
"""青龙 - 什么值得买签到。环境变量: WEBMONITER_SMZDM_ENABLE, WEBMONITER_SMZDM_COOKIE"""
from ql._runner import run_task
from tasks.smzdm_checkin import run_smzdm_checkin_once

if __name__ == "__main__":
    run_task("smzdm_checkin", run_smzdm_checkin_once)
