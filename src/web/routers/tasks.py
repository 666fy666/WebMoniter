"""Task management API routes."""

import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from src.jobs.registry import (
    MONITOR_JOBS,
    TASK_JOBS,
    discover_and_import,
    run_task_with_logging,
)
from src.web.auth import check_login

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/tasks")
async def get_tasks_api(request: Request):
    """获取所有注册的任务列表"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        discover_and_import()

        tasks = []
        for job in MONITOR_JOBS:
            tasks.append(
                {
                    "job_id": job.job_id,
                    "trigger": job.trigger,
                    "type": "monitor",
                    "type_label": "监控任务",
                    "description": job.description,
                }
            )

        for job in TASK_JOBS:
            tasks.append(
                {
                    "job_id": job.job_id,
                    "trigger": job.trigger,
                    "type": "task",
                    "type_label": "定时任务",
                    "description": job.description,
                }
            )

        return JSONResponse({"success": True, "tasks": tasks})
    except Exception as e:
        logger.error("获取任务列表失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/tasks/{task_id}/run")
async def run_task_api(request: Request, task_id: str):
    """手动触发执行指定任务"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        discover_and_import()

        all_jobs = MONITOR_JOBS + TASK_JOBS
        target_job = None
        for job in all_jobs:
            if job.job_id == task_id:
                target_job = job
                break

        if target_job is None:
            return JSONResponse({"error": f"任务 {task_id} 不存在"}, status_code=404)

        logger.info("手动触发任务: %s", task_id)
        try:
            run_func = target_job.original_run_func or target_job.run_func
            await run_task_with_logging(task_id, run_func)
            logger.info("任务 %s 手动执行完成", task_id)
            return JSONResponse(
                {
                    "success": True,
                    "message": f"任务 {task_id} 执行成功",
                }
            )
        except Exception as e:
            logger.error("任务 %s 执行失败: %s", task_id, e, exc_info=True)
            return JSONResponse(
                {
                    "success": False,
                    "message": f"任务执行失败: {str(e)}",
                },
                status_code=500,
            )
    except Exception as e:
        logger.error("触发任务失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)
