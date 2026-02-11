#!/usr/bin/env python3
"""青龙 - Freenom 续期。环境变量: WEBMONITER_FREENOM_ENABLE, WEBMONITER_FREENOM_ACCOUNTS (JSON)"""
from ql._runner import run_task
from tasks.freenom_checkin import run_freenom_checkin_once
if __name__ == "__main__":
    run_task("freenom_checkin", run_freenom_checkin_once)
