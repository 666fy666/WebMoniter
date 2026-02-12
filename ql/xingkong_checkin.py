#!/usr/bin/env python3
"""青龙 - 星空代理签到。环境变量: WEBMONITER_XINGKONG_ENABLE, WEBMONITER_XINGKONG_USERNAME, WEBMONITER_XINGKONG_PASSWORD"""
from ql._runner import run_task
from tasks.xingkong_checkin import run_xingkong_checkin_once

if __name__ == "__main__":
    run_task("xingkong_checkin", run_xingkong_checkin_once)
