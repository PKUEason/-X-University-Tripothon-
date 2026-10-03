"""Librarian：Library 空间的资料检索。

第二阶段（向量升级）：默认走 Hybrid RAG = BM25 + 向量（RRF 融合），
curated 精选语料作为兜底：
  - MOCK_MODE=true（路演保险）→ 走 curated，结果完全确定；
  - 真实模式且 RAG_ENABLED → hybrid 检索（向量后端不可用时自动降级 BM25）；
  - 命中为空（生僻/空泛查询）→ 回退 curated，保证空间不空；
  - 返回结构保持不变（documents/engine/notice），前端无需改动。

第三阶段（arXiv 联网）：retrieve 新增 arxiv_papers / arxiv_status 字段，
分区展示「本地资料 + arXiv 最新论文」。additive 字段，前端零改动：
  - MOCK 模式 → 预制扩散模型论文（真实存在）；
  - 真实模式 + ARXIV_ENABLED → 调 arXiv API，5 秒超时，失败降级空列表；
  - Professor 的 references 仍只用本地 search_documents，不混入 arXiv。

Embedding 后端配置见 .env（EMBEDDING_PROVIDER / EMBEDDING_BASE_URL / EMBEDDING_API_KEY）。
arXiv 配置见 .env（ARXIV_ENABLED / ARXIV_TIMEOUT / ARXIV_TOP_K）。
"""
import logging
from typing import Any

from app.config import settings
from app.mock_data import golden_path as mock
from app.rag import arxiv as arxiv_client
from app.rag.embeddings import build_provider
from app.rag.hybrid import HybridRetriever

log = logging.getLogger("librarian")

# RAG 总开关。要强制只走精选语料（排查问题/对比效果）改为 False。
RAG_ENABLED = True

# 返回字段，前端按此渲染（见 README「接口契约」3.3）
CONTRACT_KEYS = ("documents", "engine", "notice", "arxiv_papers", "arxiv_status")

# 进程内单例：构建 embedding 后端（auto 探测，失败已在工厂内降级）+ 混合检索器
_embedding_provider = build_provider()
_hybrid = HybridRetriever(provider=_embedding_provider, mode=settings.rag_mode)


def retrieve(query: str, top_k: int = 5) -> dict[str, Any]:
    # 1. 本地 hybrid / curated（原有逻辑）
    if settings.mock_mode or not RAG_ENABLED:
        result = _retrieve_via_curated(query, top_k)
    else:
        documents = _hybrid.search(query, top_k=top_k)
        if documents:
            result = {
                "documents": documents,
                "engine": _hybrid.engine,
                "notice": _build_notice(),
            }
        else:
            # 零命中（生僻/空泛查询）：回退精选语料，保证空间不空
            result = _retrieve_via_curated(query, top_k)
            result["notice"] = "Hybrid RAG 未命中，已回退精选语料。"

    # 2. arXiv 最新论文（分区展示，失败不影响本地资料）
    papers, status = _fetch_arxiv(query)
    result["arxiv_papers"] = papers
    result["arxiv_status"] = status
    if status == "ok" and papers:
        result["notice"] += f" 另附 {len(papers)} 篇 arXiv 最新论文。"
    elif status == "failed":
        result["notice"] += " arXiv 检索不可用，已跳过。"
    return result


def search_documents(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """检索归口，返回纯 documents 列表（供 Professor 等其他 Agent 复用，
    产品语义 = 教授答疑前先让图书管理员取资料）。

    检索是本地确定性计算（hybrid 的向量路在断网时自动降级 BM25），
    因此不受 MOCK_MODE 影响——mock 只切换 LLM 生成，不切换检索。
    RAG 关闭 / hybrid 零命中 → curated 兜底，保证总有结果。
    注意：不包含 arXiv 外部论文（避免外部内容进入 Professor prompt）。"""
    if not RAG_ENABLED:
        return mock.library_docs(query, top_k=top_k)
    documents = _hybrid.search(query, top_k=top_k)
    return documents if documents else mock.library_docs(query, top_k=top_k)


def _fetch_arxiv(query: str) -> tuple[list[dict[str, Any]], str]:
    """获取 arXiv 最新论文，返回 (papers, status)。
    status: ok | failed | disabled。任何异常都降级为空列表。"""
    if settings.mock_mode:
        return mock.arxiv_papers(query, top_k=settings.arxiv_top_k), "ok"
    if not settings.arxiv_enabled:
        return [], "disabled"
    try:
        papers = arxiv_client.search_arxiv(
            query, top_k=settings.arxiv_top_k, timeout=settings.arxiv_timeout
        )
        return papers, "ok"
    except Exception as exc:
        log.warning("arXiv 检索失败：%s", exc)
        return [], "failed"


def _build_notice() -> str:
    if _hybrid.degraded:
        return f"向量检索不可用，已降级 BM25（{_hybrid.degraded_reason[:60]}）。"
    if _hybrid.mode == "bm25":
        return "BM25 关键词检索（RAG_MODE=bm25）。"
    return f"Hybrid RAG：BM25 + 向量 RRF 融合（{_embedding_provider.name}）。"


def _retrieve_via_curated(query: str, top_k: int = 5) -> dict[str, Any]:
    """精选语料 + 关键词打分，不依赖网络与余额。"""
    return {
        "documents": mock.library_docs(query, top_k=top_k),
        "engine": "curated-v1",
        "notice": "精选语料检索（MOCK / 兜底模式）。",
    }
