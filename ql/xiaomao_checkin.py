#!/usr/bin/env python3
"""青龙 - 小茅预约（i茅台）。环境变量: WEBMONITER_XIAOMAO_ENABLE, WEBMONITER_XIAOMAO_TOKEN"""
from ql._runner import run_task
from tasks.xiaomao_checkin import run_xiaomao_checkin_once
if __name__ == "__main__":
    run_task("xiaomao_checkin", run_xiaomao_checkin_once)
