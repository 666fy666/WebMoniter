"""RAG 索引构建 - 各数据源分块与索引（Phase 2/3 扩展）"""

import logging

logger = logging.getLogger(__name__)


def build_docs_index() -> None:
    """构建/重建文档索引（Chroma 向量库全量更新）"""
    from src.ai_assistant.rag import rebuild_chroma_docs

    rebuild_chroma_docs()


def build_config_index() -> None:
    """构建配置索引（Phase 2）"""
    pass


def build_logs_index() -> None:
    """构建日志索引（Phase 3）"""
    pass
