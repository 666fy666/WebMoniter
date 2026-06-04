"""定时任务包。

定时任务列表以 src.jobs.registry.TASK_MODULES 为准，由 src.jobs.registry.discover_and_import() 加载。
需要直接调用某任务时，从对应子模块导入，例如：
  from src.tasks.ikuuu_checkin import run_checkin_once
  from src.tasks.weibo_chaohua_checkin import run_weibo_chaohua_checkin_once
"""
