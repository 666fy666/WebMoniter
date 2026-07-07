"""
青龙 CLI 入口：python -m src.ql <task_id>

示例：
  python -m src.ql ikuuu_checkin
  python -m src.ql --list
"""

from __future__ import annotations

import sys

# 触发 _runner 中的项目根目录与 sys.path 设置
import src.ql._runner  # noqa: F401


def _print_usage() -> None:
    print("用法: python -m src.ql <task_id>")
    print("      python -m src.ql --list")
    print()
    print("示例: python -m src.ql ikuuu_checkin")
    print()
    print("说明: 原 src/ql/*_checkin.py 薄脚本已合并为本 CLI，请在青龙定时任务中改用上述命令。")


def _list_tasks() -> None:
    from src.jobs.registry import TASK_MODULES, discover_and_import_tasks_only

    discover_and_import_tasks_only()
    from src.jobs.registry import TASK_JOBS

    print("可运行的定时任务（青龙 CLI）：")
    for job in TASK_JOBS:
        if job.job_id == "demo_task":
            continue
        print(f"  {job.job_id:28}  {job.description}")
    print()
    print(f"共 {len([j for j in TASK_JOBS if j.job_id != 'demo_task'])} 个任务（不含 demo_task）")
    print(f"模块列表由 src/jobs/metadata.py 生成（兼容导出 {len(TASK_MODULES)} 项）")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        _print_usage()
        return

    if sys.argv[1] in ("--list", "-l"):
        _list_tasks()
        return

    task_id = sys.argv[1].strip()
    if not task_id:
        _print_usage()
        sys.exit(1)

    from src.jobs.registry import discover_and_import_tasks_only, get_registered_task
    from src.ql._runner import run_task

    discover_and_import_tasks_only()
    job = get_registered_task(task_id)
    if job is None:
        print(f"错误: 未找到任务 '{task_id}'")
        print("使用 python -m src.ql --list 查看可用任务")
        sys.exit(1)

    run_func = job.original_run_func
    if run_func is None:
        print(f"错误: 任务 '{task_id}' 无可用执行函数")
        sys.exit(1)

    run_task(task_id, run_func)


if __name__ == "__main__":
    main()
