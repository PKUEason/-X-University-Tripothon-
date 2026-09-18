"""Librarian：Library 空间的资料检索。

Phase 1（当前）：黄金路径精选语料 + 关键词匹配，保证演示稳定。
Phase 2 接入点（落在 _retrieve_via_rag）：
  1. 把精选 PDF / 论文文本切块，用 embedding 模型向量化存入 Chroma / LanceDB；
  2. 改为「向量召回 + rerank」，并补充 arXiv API 实时检索工具；
  3. 返回结构保持不变，前端无需改动。
"""
from typing import Any

from app.mock_data import golden_path as mock

# Phase 2 开关：实现完 _retrieve_via_rag 后改为 True。
#
# 这里原本写的是 `if settings.mock_mode or True:`——条件恒真，真实检索分支是死代码，
# 而且会让读代码的人误以为「检索行为会随 MOCK_MODE 变化」。实际不会：
# Library 在 Phase 1 永远走精选语料。现在改成显式常量，意图一目了然。
RAG_ENABLED = False

# 两个实现都必须返回的字段，前端按此渲染（见 README「接口契约」3.3）
CONTRACT_KEYS = ("documents", "engine", "notice")


def retrieve(query: str, top_k: int = 5) -> dict[str, Any]:
    if RAG_ENABLED:
        return _retrieve_via_rag(query, top_k)
    return _retrieve_via_curated(query, top_k)


def _retrieve_via_curated(query: str, top_k: int = 5) -> dict[str, Any]:
    """Phase 1：精选语料 + 关键词打分，不依赖网络与余额。"""
    return {
        "documents": mock.library_docs(query, top_k=top_k),
        "engine": "curated-v1",
        "notice": "Phase 1 精选语料检索；Phase 2 将升级为向量 RAG + arXiv 实时检索。",
    }


def _retrieve_via_rag(query: str, top_k: int = 5) -> dict[str, Any]:
    """Phase 2 待实现：向量召回 + rerank。

    返回值必须与 _retrieve_via_curated 同构（CONTRACT_KEYS），前端无需改动。
    未实现前保持 fail-fast，避免「以为切到了 RAG、其实还在吃精选语料」。
    """
    raise NotImplementedError(
        "RAG 检索尚未实现：请先完成本文件顶部说明的接入步骤，再打开 RAG_ENABLED。"
    )
