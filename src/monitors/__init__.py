"""监控模块包。

监控任务列表以 src.jobs.registry.MONITOR_MODULES 为准，由 src.jobs.registry.discover_and_import() 加载。
需要直接使用某监控类时，从对应子模块导入，例如：
  from src.monitors.huya_monitor import HuyaMonitor
  from src.monitors.weibo_monitor import WeiboMonitor
"""
