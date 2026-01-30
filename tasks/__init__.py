"""定时任务包。

定时任务列表以 src.job_registry.TASK_MODULES 为准，由 job_registry.discover_and_import() 加载。
需要直接调用某任务时，从对应子模块导入，例如：
  from tasks.ikuuu_checkin import run_checkin_once
  from tasks.weibo_chaohua_checkin import run_weibo_chaohua_checkin_once
"""
