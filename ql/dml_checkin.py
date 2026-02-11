#!/usr/bin/env python3
"""青龙 - 达美乐任务。环境变量: WEBMONITER_DML_ENABLE, WEBMONITER_DML_OPENID"""
from ql._runner import run_task
from tasks.dml_checkin import run_dml_checkin_once
if __name__ == "__main__":
    run_task("dml_checkin", run_dml_checkin_once)
