#!/usr/bin/env python3
"""青龙 - 帆软签到。环境变量: WEBMONITER_FR_ENABLE, WEBMONITER_FR_COOKIE"""
from ql._runner import run_task
from tasks.fr_checkin import run_fr_checkin_once

if __name__ == "__main__":
    run_task("fr_checkin", run_fr_checkin_once)
