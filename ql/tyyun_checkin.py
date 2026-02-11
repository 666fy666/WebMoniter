#!/usr/bin/env python3
"""青龙 - 天翼云盘签到。环境变量: WEBMONITER_TYYUN_ENABLE, WEBMONITER_TYYUN_USERNAME, WEBMONITER_TYYUN_PASSWORD"""
from ql._runner import run_task
from tasks.tyyun_checkin import run_tyyun_checkin_once
if __name__ == "__main__":
    run_task("tyyun_checkin", run_tyyun_checkin_once)
