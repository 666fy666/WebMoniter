#!/usr/bin/env python3
"""青龙 - 科技玩家签到。环境变量: WEBMONITER_KJWJ_ENABLE, WEBMONITER_KJWJ_ACCOUNTS (JSON)"""
from ql._runner import run_task
from tasks.kjwj_checkin import run_kjwj_checkin_once
if __name__ == "__main__":
    run_task("kjwj_checkin", run_kjwj_checkin_once)
