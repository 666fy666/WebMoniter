#!/usr/bin/env python3
"""青龙 - 小米社区签到。环境变量: WEBMONITER_MIUI_ENABLE, WEBMONITER_MIUI_ACCOUNT, WEBMONITER_MIUI_PASSWORD"""
from ql._runner import run_task
from tasks.miui_checkin import run_miui_checkin_once
if __name__ == "__main__":
    run_task("miui_checkin", run_miui_checkin_once)
