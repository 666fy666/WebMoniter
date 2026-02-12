#!/usr/bin/env python3
"""青龙 - 中国福彩抽奖。环境变量: WEBMONITER_ZGFC_ENABLE, WEBMONITER_ZGFC_TOKENS"""
from ql._runner import run_task
from tasks.zgfc_draw import run_zgfc_draw_once

if __name__ == "__main__":
    run_task("zgfc_draw", run_zgfc_draw_once)
