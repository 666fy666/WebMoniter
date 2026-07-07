"""监控模块包。

监控任务列表由 src.jobs.metadata.MONITOR_SPECS 生成，并通过 src.jobs.registry.MONITOR_MODULES
兼容导出；加载入口为 src.jobs.registry.discover_and_import()。
需要直接使用某监控类时，从对应子模块导入，例如：
  from src.monitors.huya_monitor import HuyaMonitor
  from src.monitors.weibo_monitor import WeiboMonitor
"""
