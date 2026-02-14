"""RAG 检索 - 文档/配置/日志；当前状态走 tools 直接查库"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Chroma 可选，未安装时使用简单文本检索
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

DOCS_DIR = Path("docs")
README_PATH = Path("README.md")
CONFIG_SAMPLE_PATH = Path("config.yml.sample")
CONFIG_PATH = Path("config.yml")
LOGS_DIR = Path("logs")

# 中文洞察类问题的关键词扩展：query 包含左词时，用右列表做检索匹配（不含 emoji 以兼容终端）
_INSIGHT_KEYWORDS = {
    "开播": ["开播", "开播啦", "开播了"],
    "下播": ["下播", "下播了"],
    "发博": ["发博", "发布", "微博", "新微博"],
    "发动态": ["动态", "发动态", "新动态"],
    "发笔记": ["笔记", "发布"],
}


def _read_docs_as_chunks() -> list[tuple[str, str]]:
    """将 docs/*.md 和 README 按简单分块读入，返回 (content, source)"""
    chunks: list[tuple[str, str]] = []
    for path in [README_PATH] + list(DOCS_DIR.glob("*.md")) + list(DOCS_DIR.glob("**/*.md")):
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
            # 简单按段落分块，每块约 600 字符
            size = 600
            overlap = 100
            for i in range(0, len(text), size - overlap):
                block = text[i : i + size]
                if block.strip():
                    chunks.append((block.strip(), str(path)))
        except Exception as e:
            logger.debug("读取 %s 失败: %s", path, e)
    return chunks


def retrieve_docs(query: str, top_k: int = 5) -> list[str]:
    """
    从文档库检索与 query 最相关的片段。
    有 Chroma 时用向量检索；否则用简单关键词匹配返回前 top_k 块。
    """
    chunks = _read_docs_as_chunks()
    if not chunks:
        return []

    if HAS_CHROMADB:
        return _chroma_retrieve(query, chunks, top_k)
    # 退化：简单包含关键词的块
    q_lower = query.lower()
    scored = []
    for content, _ in chunks:
        score = sum(1 for w in q_lower.split() if len(w) > 1 and w in content.lower())
        scored.append((score, content))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:top_k]]


def _get_chroma_client_and_collection(cfg=None):
    """获取 Chroma 客户端与文档集合，供检索与索引共用"""
    if cfg is None:
        try:
            from src.ai_assistant.config import get_ai_config

            cfg = get_ai_config()
        except Exception:
            pass
    persist_dir = (
        getattr(cfg, "chroma_persist_dir", "data/ai_assistant_chroma")
        if cfg
        else "data/ai_assistant_chroma"
    )
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    # allow_reset=True 供 rebuild 时清空所有集合，确保只保留最新向量库
    client = chromadb.PersistentClient(
        path=persist_dir,
        settings=ChromaSettings(allow_reset=True),
    )
    coll_name = "webmoniter_docs"
    collection = client.get_or_create_collection(coll_name, metadata={"hnsw:space": "cosine"})
    return client, collection


def rebuild_chroma_docs() -> None:
    """
    全量重建 Chroma 文档向量库。
    清空现有所有集合，确保只保留最新向量库，再重新添加 docs/ 与 README 的分块。
    供定时任务或手动触发。
    """
    if not HAS_CHROMADB:
        logger.debug("未安装 chromadb，跳过向量库重建")
        return
    cfg = None
    try:
        from src.ai_assistant.config import get_ai_config

        cfg = get_ai_config()
    except Exception:
        pass
    client, _ = _get_chroma_client_and_collection(cfg)
    try:
        client.reset()
    except Exception as e:
        logger.debug("reset 向量库时忽略: %s", e)
        try:
            client.delete_collection("webmoniter_docs")
        except Exception:
            pass
    collection = client.get_or_create_collection(
        "webmoniter_docs", metadata={"hnsw:space": "cosine"}
    )
    chunks = _read_docs_as_chunks()
    if chunks:
        ids = [f"c{i}" for i in range(len(chunks))]
        contents = [c[0] for c in chunks]
        collection.add(ids=ids, documents=contents)
        logger.info("RAG 向量库已重建，共 %d 个文档块", len(chunks))
    else:
        logger.debug("无文档可索引，跳过 Chroma 写入")


def _chroma_retrieve(query: str, chunks: list[tuple[str, str]], top_k: int) -> list[str]:
    """使用 Chroma 做向量检索"""
    cfg = None
    try:
        from src.ai_assistant.config import get_ai_config

        cfg = get_ai_config()
    except Exception:
        pass
    _, collection = _get_chroma_client_and_collection(cfg)
    # 若集合为空则添加
    if collection.count() == 0:
        ids = [f"c{i}" for i in range(len(chunks))]
        contents = [c[0] for c in chunks]
        collection.add(ids=ids, documents=contents)
    results = collection.query(query_texts=[query], n_results=min(top_k, collection.count()))
    if results and results.get("documents") and results["documents"][0]:
        return results["documents"][0]
    return []


def _redact_sensitive(text: str) -> str:
    """脱敏：将 cookie、api_key、token 等敏感值替换为占位符"""
    import re

    lines = []
    sensitive_pattern = re.compile(
        r"^\s*(cookie|cookies|api_key|apikey|api_secret|password|token|secret"
        r"|bili_ticket|SESSDATA|bili_jct|payload)\s*:\s*",
        re.IGNORECASE,
    )
    for line in text.split("\n"):
        if sensitive_pattern.search(line):
            parts = line.split(":", 1)
            if len(parts) >= 2:
                lines.append(parts[0] + ": '<已脱敏>'")
            else:
                lines.append(line)
        else:
            lines.append(line)
    return "\n".join(lines)


def _read_config_chunks() -> list[tuple[str, str]]:
    """将 config.yml.sample 与 config.yml（脱敏）按顶级 key 分块"""
    chunks: list[tuple[str, str]] = []
    for path, label in [(CONFIG_SAMPLE_PATH, "sample"), (CONFIG_PATH, "actual")]:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
            if label == "actual":
                text = _redact_sensitive(text)
            current = []
            current_key = ""
            for line in text.split("\n"):
                if line and not line[0].isspace() and not line.startswith("#") and ":" in line:
                    if current and current_key:
                        chunks.append(("\n".join(current), f"config:{current_key}({label})"))
                    key = line.split(":")[0].strip()
                    current_key = key
                    current = [line]
                elif current:
                    current.append(line)
            if current and current_key:
                chunks.append(("\n".join(current), f"config:{current_key}({label})"))
        except Exception as e:
            logger.debug("读取配置 %s 失败: %s", path, e)
    return chunks


def retrieve_config(query: str, top_k: int = 3) -> list[str]:
    """从配置模板检索相关片段"""
    chunks = _read_config_chunks()
    if not chunks:
        return []
    q_lower = query.lower()
    scored = []
    for content, _ in chunks:
        score = sum(1 for w in q_lower.split() if len(w) > 1 and w in content.lower())
        scored.append((score, content))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:top_k]]


def _read_recent_logs(limit_lines: int = 500) -> list[tuple[str, str]]:
    """读取最近的主日志，按时间倒序，返回 (line, source)"""
    if not LOGS_DIR.exists():
        return []
    main_logs = sorted(LOGS_DIR.glob("main_*.log"), reverse=True)
    lines: list[tuple[str, str]] = []
    for log_path in main_logs[:3]:  # 最近 3 个主日志
        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
            for line in content.strip().split("\n")[-limit_lines:]:
                line = line.strip()
                if line:
                    lines.append((line, str(log_path.name)))
        except Exception as e:
            logger.debug("读取日志 %s 失败: %s", log_path, e)
    return lines


def _extract_search_terms(query: str) -> list[str]:
    """提取检索词，支持中文：空格分词 + 洞察类关键词扩展"""
    q_lower = query.lower()
    terms = [w for w in q_lower.split() if len(w) > 1]
    for key, expansions in _INSIGHT_KEYWORDS.items():
        if key in query or key in q_lower:
            terms.extend(expansions)
    return list(dict.fromkeys(terms)) or [q_lower[:20]]  # 去重，至少保留截断的 query


def retrieve_logs(query: str, top_k: int = 30, prefer_errors: bool = True) -> list[str]:
    """
    从日志检索。prefer_errors 时优先返回 ERROR/WARNING 行。
    洞察类问题（开播/发博等）使用关键词扩展以匹配中文。
    """
    lines = _read_recent_logs(limit_lines=500)
    if not lines:
        return []
    terms = _extract_search_terms(query)
    err_lines = [line[0] for line in lines if "ERROR" in line[0] or "WARNING" in line[0]]
    info_lines = [line[0] for line in lines if "INFO" in line[0]]
    # 倒序使最近日志优先（lines 按时间正序，末尾为最近）
    err_lines = list(reversed(err_lines))
    info_lines = list(reversed(info_lines))
    is_error_query = prefer_errors and (
        any(k in query for k in ("失败", "错误", "诊断")) or "log" in query.lower()
    )
    if is_error_query:
        scored = [
            (sum(1 for t in terms if t in line.lower()), line) for line in err_lines
        ]
    else:
        all_lines = info_lines + err_lines  # 洞察类优先 INFO
        scored = [
            (sum(1 for t in terms if t in line.lower()), line) for line in all_lines
        ]
    scored.sort(key=lambda x: (-x[0], x[1]))  # 分高优先
    return [line for _, line in scored[:top_k]]


def retrieve_all(query: str, context: str = "all") -> str:
    """
    统一检索入口，根据 context 决定检索范围，返回拼接后的上下文文本。
    context: config | logs | insights | current | all
    """
    parts = []
    if context in ("config", "all"):
        config_chunks = retrieve_config(query, top_k=3)
        if config_chunks:
            parts.append("【配置参考】\n" + "\n\n---\n\n".join(config_chunks))
    if context in ("logs", "insights", "all"):
        log_lines = retrieve_logs(query, top_k=25)
        if log_lines:
            parts.append("【日志参考】\n" + "\n".join(log_lines))
    if context in ("all",) or not parts:
        docs = retrieve_docs(query, top_k=5)
        if docs:
            parts.append("【文档参考】\n" + "\n\n---\n\n".join(docs))
    return "\n\n".join(parts) if parts else ""
