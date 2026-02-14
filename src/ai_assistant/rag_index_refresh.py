"""RAG 向量库定时更新任务 - 每 N 分钟重建文档索引"""

import functools
import logging

from src.ai_assistant.config import get_ai_config, is_ai_enabled
from src.job_registry import RAG_JOBS, JobDescriptor

logger = logging.getLogger(__name__)


async def run_rag_index_refresh() -> None:
    """重建 RAG 文档向量库（Chroma）"""
    if not is_ai_enabled():
        logger.debug("rag_index_refresh: AI 助手未启用，跳过")
        return
    try:
        from src.ai_assistant.indexer import build_docs_index

        build_docs_index()
    except Exception as e:
        logger.error("RAG 向量库更新失败: %s", e, exc_info=True)


def _get_trigger_kwargs(_config) -> dict:
    """从 ai_assistant 配置获取间隔秒数（忽略 AppConfig 参数）"""
    cfg = get_ai_config()
    return {"seconds": cfg.rag_index_refresh_interval_seconds}


def register() -> None:
    """注册 RAG 索引定时更新任务（幂等：已注册则跳过，避免 discover_and_import 重复调用造成多个任务）"""
    # 仅当启用 AI 且安装 chromadb 时才有意义
    try:
        import chromadb  # noqa: F401
    except ImportError:
        logger.debug("未安装 chromadb，跳过 RAG 索引任务注册")
        return

    if any(j.job_id == "rag_index_refresh" for j in RAG_JOBS):
        return

    @functools.wraps(run_rag_index_refresh)
    async def wrapped() -> None:
        if not is_ai_enabled():
            logger.debug("rag_index_refresh: AI 助手未启用，跳过")
            return
        from src.job_registry import _add_task_file_handler, _remove_task_file_handler
        from src.log_manager import _current_job_id

        handler = _add_task_file_handler("rag_index_refresh", run_rag_index_refresh)
        token = _current_job_id.set("rag_index_refresh")
        try:
            await run_rag_index_refresh()
        finally:
            _current_job_id.reset(token)
            _remove_task_file_handler(run_rag_index_refresh, handler)

    RAG_JOBS.append(
        JobDescriptor(
            job_id="rag_index_refresh",
            run_func=wrapped,
            trigger="interval",
            get_trigger_kwargs=_get_trigger_kwargs,
            original_run_func=run_rag_index_refresh,
        )
    )
    logger.debug("已注册 RAG 索引更新任务: rag_index_refresh")
