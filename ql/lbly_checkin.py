#!/usr/bin/env python3
"""青龙 - 丽宝乐园签到。环境变量: WEBMONITER_LBLY_ENABLE, WEBMONITER_LBLY_REQUEST_BODY"""
from ql._runner import run_task
from tasks.lbly_checkin import run_lbly_checkin_once
if __name__ == "__main__":
    run_task("lbly_checkin", run_lbly_checkin_once)
