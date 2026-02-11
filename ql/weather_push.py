#!/usr/bin/env python3
"""
青龙面板 - 天气推送脚本

环境变量：
  WEBMONITER_WEATHER_ENABLE=true
  WEBMONITER_WEATHER_CITY_CODE=城市代码如101020100（上海）

定时规则建议：30 7 * * *
"""

from ql._runner import run_task
from tasks.weather_push import run_weather_push_once

if __name__ == "__main__":
    run_task("weather_push", run_weather_push_once)
