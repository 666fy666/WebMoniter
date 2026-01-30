"""监控模块包。

监控任务列表以 src.job_registry.MONITOR_MODULES 为准，由 job_registry.discover_and_import() 加载。
需要直接使用某监控类时，从对应子模块导入，例如：
  from monitors.huya_monitor import HuyaMonitor
  from monitors.weibo_monitor import WeiboMonitor
"""
