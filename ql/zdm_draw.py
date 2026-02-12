#!/usr/bin/env python3
"""青龙 - 值得买每日抽奖。环境变量: WEBMONITER_ZDM_DRAW_ENABLE, WEBMONITER_ZDM_DRAW_COOKIE"""
from ql._runner import run_task
from tasks.zdm_draw import run_zdm_draw_once

if __name__ == "__main__":
    run_task("zdm_draw", run_zdm_draw_once)
