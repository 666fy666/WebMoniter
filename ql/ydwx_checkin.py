#!/usr/bin/env python3
"""青龙 - 一点万象签到。环境变量: WEBMONITER_YDWX_ENABLE, WEBMONITER_YDWX_DEVICE_PARAMS, WEBMONITER_YDWX_TOKEN"""
from ql._runner import run_task
from tasks.ydwx_checkin import run_ydwx_checkin_once

if __name__ == "__main__":
    run_task("ydwx_checkin", run_ydwx_checkin_once)
