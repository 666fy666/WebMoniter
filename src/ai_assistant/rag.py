"""RAG 检索 - 文档/配置/日志；当前状态走 tools 直接查库

参考 datawhalechina/all-in-rag 思路：
- 数据准备：Markdown 结构感知分块、父子文本块、智能去重
- 索引检索：向量 + BM25 混合检索、RRF 重排
- 生成集成：查询路由、按 context 选择检索策略
"""

import logging
import re
import shutil
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# Chroma 可选，未安装时使用简单文本检索
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

try:
    from rank_bm25 import BM25Okapi

    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

# 文档：使用项目内所有 .md 文件（排除 .git）
DOCS_GLOB_ROOT = Path(".")
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

# 查询路由：根据关键词判断检索侧重点
_QUERY_ROUTE_CONFIG = "config"
_QUERY_ROUTE_LOGS = "logs"
_QUERY_ROUTE_DOCS = "docs"


def _route_query(query: str) -> str:
    """简单查询路由：config | logs | docs"""
    q = query.strip().lower()
    if any(k in q for k in ("配置", "config", "怎么写", "如何配置", "yaml", "推送通道", "监控")):
        return _QUERY_ROUTE_CONFIG
    if any(k in q for k in ("日志", "报错", "错误", "失败", "诊断", "log", "error")):
        return _QUERY_ROUTE_LOGS
    return _QUERY_ROUTE_DOCS


# ---------------------- Markdown 结构感知分块（父子文本块）----------------------


def _split_md_by_headers(text: str) -> list[str]:
    """按 Markdown 标题 # ## ### 分割，每块包含标题及其下属内容"""
    if not text.strip():
        return []
    header_pattern = re.compile(r"^#{1,3}\s+.+", re.MULTILINE)
    lines = text.split("\n")
    parts: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if header_pattern.match(line):
            section = [line]
            i += 1
            while i < len(lines) and not header_pattern.match(lines[i]):
                section.append(lines[i])
                i += 1
            block = "\n".join(section).strip()
            if len(block) > 30:
                parts.append(block)
        else:
            section = []
            while i < len(lines) and not header_pattern.match(lines[i]):
                section.append(lines[i])
                i += 1
            block = "\n".join(section).strip()
            if len(block) > 30:
                parts.append(block)
    return parts if parts else [text.strip()]


def _prepare_doc_chunks() -> list[tuple[str, dict]]:
    """
    将项目内 .md 文件按 Markdown 结构分块，支持父子关系。
    返回 [(content, metadata), ...]，metadata 含 source, parent_id, chunk_id
    """
    chunks: list[tuple[str, dict]] = []
    md_paths = [
        p for p in DOCS_GLOB_ROOT.rglob("*.md")
        if p.is_file() and ".git" not in str(p)
    ]
    for path in sorted(md_paths):
        try:
            text = path.read_text(encoding="utf-8")
            parent_id = str(uuid.uuid4())
            header_parts = _split_md_by_headers(text)
            if not header_parts:
                header_parts = [text.strip()] if text.strip() else []
            for i, part in enumerate(header_parts):
                if not part or len(part) < 20:
                    continue
                # 单块过长时再按固定大小切（避免超大块）
                if len(part) > 800:
                    size, overlap = 600, 100
                    for j in range(0, len(part), size - overlap):
                        block = part[j : j + size].strip()
                        if block:
                            chunks.append((
                                block,
                                {
                                    "source": str(path),
                                    "parent_id": parent_id,
                                    "chunk_id": str(uuid.uuid4()),
                                    "chunk_index": i,
                                },
                            ))
                else:
                    chunks.append((
                        part,
                        {
                            "source": str(path),
                            "parent_id": parent_id,
                            "chunk_id": str(uuid.uuid4()),
                            "chunk_index": i,
                        },
                    ))
        except Exception as e:
            logger.debug("读取 %s 失败: %s", path, e)
    return chunks


def _read_docs_as_chunks() -> list[tuple[str, str]]:
    """兼容旧接口：返回 (content, source) 列表（用于 Chroma/退化逻辑）"""
    prepared = _prepare_doc_chunks()
    return [(c, m.get("source", "")) for c, m in prepared]


def _get_parent_docs_from_chunks(
    chunk_results: list[tuple[str, dict]],
) -> list[str]:
    """
    根据子块获取对应父文档（智能去重）。
    同一 source 的多个子块合并为一次完整父文档内容。
    """
    seen_parent: dict[str, str] = {}
    for content, meta in chunk_results:
        src = meta.get("source", "")
        if not src or src in seen_parent:
            continue
        try:
            full = Path(src).read_text(encoding="utf-8")
            seen_parent[src] = full.strip()
        except Exception:
            seen_parent[src] = content
    return list(seen_parent.values())


# ---------------------- BM25 检索 ----------------------


def _tokenize_for_bm25(text: str) -> list[str]:
    """简单中文分词：按字符 + 常见分隔符切分，便于 BM25 匹配"""
    # 保留英文/数字连续，中文按字符
    tokens: list[str] = []
    for m in re.finditer(r"[\w\u4e00-\u9fff]+|[^\s\w\u4e00-\u9fff]", text):
        t = m.group()
        if len(t) == 1 and "\u4e00" <= t <= "\u9fff":
            tokens.append(t)
        elif len(t) > 1:
            tokens.append(t.lower())
    return tokens or [text[:50]]


def _bm25_retrieve(
    query: str,
    chunks: list[tuple[str, dict]],
    top_k: int,
) -> list[tuple[str, dict]]:
    """BM25 检索，返回 [(content, metadata), ...]"""
    if not HAS_BM25 or not chunks:
        return []
    corpus = [_tokenize_for_bm25(c) for c, _ in chunks]
    bm25 = BM25Okapi(corpus)
    q_tokens = _tokenize_for_bm25(query)
    scores = bm25.get_scores(q_tokens)
    indexed = list(zip(scores, chunks))
    indexed.sort(key=lambda x: -x[0])
    return [item for _, item in indexed[:top_k]]


# ---------------------- 混合检索（RRF）----------------------


def _rrf_merge(
    vector_results: list[str],
    bm25_results: list[tuple[str, dict]],
    content_to_meta: dict[str, dict],
    top_k: int,
    k: int = 60,
) -> list[tuple[str, dict]]:
    """
    RRF (Reciprocal Rank Fusion) 融合向量与 BM25 结果。
    使用 content 本身作为去重 key，返回 [(content, metadata), ...]
    """
    rrf_scores: dict[str, float] = {}

    for rank, c in enumerate(vector_results):
        rrf_scores[c] = rrf_scores.get(c, 0) + 1 / (k + rank + 1)

    for rank, (c, m) in enumerate(bm25_results):
        rrf_scores[c] = rrf_scores.get(c, 0) + 1 / (k + rank + 1)

    sorted_contents = sorted(rrf_scores.keys(), key=lambda x: -rrf_scores[x])[:top_k]
    out: list[tuple[str, dict]] = []
    for c in sorted_contents:
        meta = content_to_meta.get(c, {"source": "", "parent_id": "", "chunk_id": "", "chunk_index": 0})
        out.append((c, meta))
    return out


# ---------------------- Chroma 向量检索 ----------------------


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
    client = chromadb.PersistentClient(
        path=persist_dir,
        settings=ChromaSettings(allow_reset=True),
    )
    coll_name = "webmoniter_docs"
    collection = client.get_or_create_collection(coll_name, metadata={"hnsw:space": "cosine"})
    return client, collection


def _chroma_retrieve(query: str, chunks: list[tuple[str, str]], top_k: int) -> list[str]:
    """使用 Chroma 做向量检索"""
    cfg = None
    try:
        from src.ai_assistant.config import get_ai_config

        cfg = get_ai_config()
    except Exception:
        pass
    _, collection = _get_chroma_client_and_collection(cfg)
    if collection.count() == 0:
        ids = [f"c{i}" for i in range(len(chunks))]
        contents = [c[0] for c in chunks]
        collection.add(ids=ids, documents=contents)
    results = collection.query(query_texts=[query], n_results=min(top_k * 2, max(collection.count(), 1)))
    if results and results.get("documents") and results["documents"][0]:
        return results["documents"][0]
    return []


# ---------------------- 对外接口 ----------------------


def retrieve_docs(
    query: str,
    top_k: int = 5,
    use_hybrid: bool = True,
    use_parent_dedup: bool = True,
) -> list[str]:
    """
    从文档库检索与 query 最相关的片段。
    - use_hybrid: 有 Chroma 且安装 rank_bm25 时使用向量+BM25 RRF 混合检索
    - use_parent_dedup: 多个子块来自同一文档时，合并为完整父文档内容
    """
    prepared = _prepare_doc_chunks()
    if not prepared:
        return []

    chunks_flat = [(c, m) for c, m in prepared]

    if HAS_CHROMADB and use_hybrid and HAS_BM25:
        # 混合检索：Chroma + BM25 + RRF
        content_to_meta = {c: m for c, m in chunks_flat}
        vector_results = _chroma_retrieve(query, [(c, m["source"]) for c, m in chunks_flat], top_k * 2)
        bm25_results = _bm25_retrieve(query, chunks_flat, top_k * 2)
        merged = _rrf_merge(vector_results, bm25_results, content_to_meta, top_k * 2)
        if use_parent_dedup and merged:
            parent_texts = _get_parent_docs_from_chunks(merged)
            return parent_texts[:top_k] if parent_texts else [c for c, _ in merged[:top_k]]
        return [c for c, _ in merged[:top_k]]

    if HAS_CHROMADB:
        contents = [c for c, _ in chunks_flat]
        results = _chroma_retrieve(query, [(c, m["source"]) for c, m in chunks_flat], top_k)
        if use_parent_dedup and results:
            meta_map = {c[:200]: m for c, m in chunks_flat}
            chunk_results = [(r, meta_map.get(r[:200], {})) for r in results]
            parent_texts = _get_parent_docs_from_chunks(chunk_results)
            return parent_texts[:top_k] if parent_texts else results
        return results

    # 退化：简单关键词匹配
    q_lower = query.lower()
    scored = []
    for content, meta in chunks_flat:
        score = sum(1 for w in q_lower.split() if len(w) > 1 and w in content.lower())
        scored.append((score, content))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:top_k]]


def rebuild_chroma_docs() -> None:
    """
    全量重建 Chroma 文档向量库。
    使用 Markdown 结构感知分块；重建前会清空整个持久化目录，避免 Chroma 内部
    HNSW 段（UUID 子目录）堆积，确保只保留最新一份索引。
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
    persist_dir = (
        getattr(cfg, "chroma_persist_dir", "data/ai_assistant_chroma")
        if cfg
        else "data/ai_assistant_chroma"
    )
    persist_path = Path(persist_dir)
    if persist_path.exists():
        try:
            shutil.rmtree(persist_path)
        except OSError as e:
            logger.warning("清空向量库目录 %s 失败: %s，尝试继续重建", persist_dir, e)
    persist_path.mkdir(parents=True, exist_ok=True)

    client, collection = _get_chroma_client_and_collection(cfg)
    chunks = _read_docs_as_chunks()
    if chunks:
        ids = [f"c{i}" for i in range(len(chunks))]
        contents = [c[0] for c in chunks]
        collection.add(ids=ids, documents=contents)
        logger.info("RAG 向量库已重建，共 %d 个文档块（Markdown 结构分块）", len(chunks))
    else:
        logger.debug("无文档可索引，跳过 Chroma 写入")


def _redact_sensitive(text: str) -> str:
    """脱敏：将 cookie、api_key、token 等敏感值替换为占位符"""
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


def _read_recent_logs(limit_lines: int = 500, max_files: int = 20) -> list[tuple[str, str]]:
    """读取 logs 目录下所有 .log 文件，按修改时间倒序"""
    if not LOGS_DIR.exists():
        return []
    all_logs = sorted(
        (p for p in LOGS_DIR.glob("*.log") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    lines: list[tuple[str, str]] = []
    for log_path in all_logs[:max_files]:
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
    return list(dict.fromkeys(terms)) or [q_lower[:20]]


def retrieve_logs(query: str, top_k: int = 30, prefer_errors: bool = True) -> list[str]:
    """从日志检索，洞察类问题使用关键词扩展"""
    lines = _read_recent_logs(limit_lines=500)
    if not lines:
        return []
    terms = _extract_search_terms(query)
    err_lines = [line[0] for line in lines if "ERROR" in line[0] or "WARNING" in line[0]]
    info_lines = [line[0] for line in lines if "INFO" in line[0]]
    err_lines = list(reversed(err_lines))
    info_lines = list(reversed(info_lines))
    is_error_query = prefer_errors and (
        any(k in query for k in ("失败", "错误", "诊断")) or "log" in query.lower()
    )
    if is_error_query:
        scored = [(sum(1 for t in terms if t in line.lower()), line) for line in err_lines]
    else:
        all_lines = info_lines + err_lines
        scored = [(sum(1 for t in terms if t in line.lower()), line) for line in all_lines]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [line for _, line in scored[:top_k]]


def retrieve_all(
    query: str,
    context: str = "all",
    use_query_route: bool = True,
) -> str:
    """
    统一检索入口。根据 context 决定检索范围，返回拼接后的上下文文本。
    context: config | logs | insights | all
    use_query_route: 为 True 时按 query 关键词微调配重（配置类多检索 config，日志类多检索 logs）
    """
    route = _route_query(query) if use_query_route else _QUERY_ROUTE_DOCS

    parts = []
    if context in ("config", "all") or (use_query_route and route == _QUERY_ROUTE_CONFIG):
        config_chunks = retrieve_config(query, top_k=4 if route == _QUERY_ROUTE_CONFIG else 3)
        if config_chunks:
            parts.append("【配置参考】\n" + "\n\n---\n\n".join(config_chunks))

    if context in ("logs", "insights", "all") or (use_query_route and route == _QUERY_ROUTE_LOGS):
        log_lines = retrieve_logs(query, top_k=30 if route == _QUERY_ROUTE_LOGS else 25)
        if log_lines:
            parts.append("【日志参考】\n" + "\n".join(log_lines))

    if context in ("all",) or not parts or route == _QUERY_ROUTE_DOCS:
        docs = retrieve_docs(query, top_k=6 if route == _QUERY_ROUTE_DOCS else 5)
        if docs:
            parts.append("【文档参考】\n" + "\n\n---\n\n".join(docs))

    return "\n\n".join(parts) if parts else ""
