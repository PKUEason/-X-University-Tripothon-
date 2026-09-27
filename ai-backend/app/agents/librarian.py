"""Librarian：Library 空间的资料检索。

第二阶段（向量升级）：默认走 Hybrid RAG = BM25 + 向量（RRF 融合），
curated 精选语料作为兜底：
  - MOCK_MODE=true（路演保险）→ 走 curated，结果完全确定；
  - 真实模式且 RAG_ENABLED → hybrid 检索（向量后端不可用时自动降级 BM25）；
  - 命中为空（生僻/空泛查询）→ 回退 curated，保证空间不空；
  - 返回结构保持不变（documents/engine/notice），前端无需改动。

Embedding 后端配置见 .env（EMBEDDING_PROVIDER / EMBEDDING_BASE_URL / EMBEDDING_API_KEY）。
"""
from typing import Any

from app.config import settings
from app.mock_data import golden_path as mock
from app.rag.embeddings import build_provider
from app.rag.hybrid import HybridRetriever

# RAG 总开关。要强制只走精选语料（排查问题/对比效果）改为 False。
RAG_ENABLED = True

# 返回字段，前端按此渲染（见 README「接口契约」3.3）
CONTRACT_KEYS = ("documents", "engine", "notice")

# 进程内单例：构建 embedding 后端（auto 探测，失败已在工厂内降级）+ 混合检索器
_embedding_provider = build_provider()
_hybrid = HybridRetriever(provider=_embedding_provider, mode=settings.rag_mode)


def retrieve(query: str, top_k: int = 5) -> dict[str, Any]:
    if settings.mock_mode or not RAG_ENABLED:
        return _retrieve_via_curated(query, top_k)

    documents = _hybrid.search(query, top_k=top_k)
    if documents:
        return {
            "documents": documents,
            "engine": _hybrid.engine,
            "notice": _build_notice(),
        }
    # 零命中（生僻/空泛查询）：回退精选语料，保证空间不空
    fallback = _retrieve_via_curated(query, top_k)
    fallback["notice"] = "Hybrid RAG 未命中，已回退精选语料。"
    return fallback


def search_documents(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """检索归口，返回纯 documents 列表（供 Professor 等其他 Agent 复用，
    产品语义 = 教授答疑前先让图书管理员取资料）。

    检索是本地确定性计算（hybrid 的向量路在断网时自动降级 BM25），
    因此不受 MOCK_MODE 影响——mock 只切换 LLM 生成，不切换检索。
    RAG 关闭 / hybrid 零命中 → curated 兜底，保证总有结果。"""
    if not RAG_ENABLED:
        return mock.library_docs(query, top_k=top_k)
    documents = _hybrid.search(query, top_k=top_k)
    return documents if documents else mock.library_docs(query, top_k=top_k)


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
