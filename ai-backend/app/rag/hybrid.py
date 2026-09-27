# -*- coding: utf-8 -*-
"""Hybrid 检索：BM25（关键词）+ 向量（语义），RRF 融合。

RRF（Reciprocal Rank Fusion）只依赖两路排名、不依赖分数尺度，
对 BM25 与余弦分数量纲不同的情况特别稳健：
    score(d) = Σ 1 / (k + rank_i(d) + 1)

RAG_MODE：
- hybrid：两路 RRF（默认）；向量路失败自动降级纯 BM25；
- vector：仅向量；失败降级 BM25；
- bm25：仅关键词。
输出 documents 结构与 BM25 v1 完全一致，前端零改动。
"""
import logging
from typing import Any, Optional

from app.rag.corpus import LIBRARY_CORPUS
from app.rag.retriever import BM25Retriever, SNIPPET_LEN
from app.rag.vector_index import VectorIndex

log = logging.getLogger("hybrid")


def rrf(rank_lists: list[list[int]], k: int = 60) -> list[int]:
    scores: dict[int, float] = {}
    for ranks in rank_lists:
        for rank, chunk_index in enumerate(ranks):
            scores[chunk_index] = scores.get(chunk_index, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=scores.get, reverse=True)


class HybridRetriever:
    def __init__(
        self,
        corpus: Optional[list[dict]] = None,
        provider=None,
        mode: str = "hybrid",
        rrf_k: int = 60,
        candidate_k: int = 20,
    ) -> None:
        self.corpus = corpus if corpus is not None else LIBRARY_CORPUS
        self.mode = mode if mode in ("hybrid", "vector", "bm25") else "hybrid"
        self.rrf_k = rrf_k
        self.candidate_k = candidate_k
        self.bm25 = BM25Retriever(self.corpus)
        self.provider = provider
        self.vector: Optional[VectorIndex] = None
        if provider is not None and provider.name != "none":
            self.vector = VectorIndex(provider, self.corpus)
        # 每次 search 后刷新，librarian 据此填 engine / notice
        self.engine = "bm25-v1"
        self.degraded = False
        self.degraded_reason = ""

    def _vector_ranks(self, query: str) -> Optional[list[int]]:
        if self.vector is None:
            return None
        try:
            return [ci for ci, _ in self.vector.search_chunks(query, candidate_k=self.candidate_k)]
        except Exception as exc:
            self.degraded = True
            self.degraded_reason = str(exc)
            log.warning("向量检索失败，降级 BM25：%s", exc)
            return None

    def _aggregate(self, chunk_order: list[int], top_k: int) -> list[dict]:
        """chunk 排名聚合回文档：每文档取最先出现（融合分最高）的段落作 snippet。"""
        best: dict[int, str] = {}
        for ci in chunk_order:
            di, para = self.bm25.chunks[ci]
            if di not in best:
                best[di] = para
        docs = []
        for di, para in list(best.items())[:top_k]:
            src = self.corpus[di]
            snippet = para if len(para) <= SNIPPET_LEN else para[:SNIPPET_LEN] + "…"
            docs.append(
                {
                    "title": src["title"],
                    "type": src.get("type", "article"),
                    "url": src.get("url", ""),
                    "snippet": snippet,
                }
            )
        return docs

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        self.degraded, self.degraded_reason = False, ""
        bm_order = [ci for ci, _ in self.bm25.search_chunks(query, candidate_k=self.candidate_k)]

        if self.mode == "bm25":
            order = bm_order
            self.engine = "bm25-v1"
            return self._aggregate(order, top_k)

        vec_order = self._vector_ranks(query)

        if self.mode == "vector":
            if vec_order is not None and vec_order:
                order = vec_order
                self.engine = f"vector-v2({self.provider.name})"
            else:
                order = bm_order
                self.engine = "bm25-v1"
                self.degraded = True
            return self._aggregate(order, top_k)

        # hybrid
        if vec_order is None:
            order = bm_order
            self.engine = "bm25-v1"
        else:
            order = rrf([bm_order, vec_order], k=self.rrf_k)
            if self.degraded:
                self.engine = "bm25-v1"
            else:
                self.engine = f"hybrid-v2(bm25+{self.provider.name})"
        return self._aggregate(order, top_k)
