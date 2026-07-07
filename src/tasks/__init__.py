"""定时任务包。

定时任务列表由 src.jobs.metadata.TASK_SPECS 生成，并通过 src.jobs.registry.TASK_MODULES
兼容导出；加载入口为 src.jobs.registry.discover_and_import()。
需要直接调用某任务时，从对应子模块导入，例如：
  from src.tasks.ikuuu_checkin import run_checkin_once
  from src.tasks.weibo_chaohua_checkin import run_weibo_chaohua_checkin_once
"""
