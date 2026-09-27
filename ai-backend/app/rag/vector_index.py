# -*- coding: utf-8 -*-
"""向量索引：段落向量的构建、持久化缓存与余弦检索。

- 段落向量与 BM25 共用 build_paragraph_chunks，顺序严格对齐；
- 缓存按 provider.name 隔离：换后端/模型不会读到旧向量；
- embed 失败直接抛异常，由 hybrid 层捕获并降级 BM25（路演不中断）。
"""
import logging
import math
from typing import Any, Optional

from app.memory.store import store
from app.rag.corpus import LIBRARY_CORPUS
from app.rag.retriever import build_paragraph_chunks

log = logging.getLogger("vector-index")


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class VectorIndex:
    def __init__(
        self,
        provider,
        corpus: Optional[list[dict]] = None,
        scope: str = "library-chunk",
    ) -> None:
        self.provider = provider
        self.corpus = corpus if corpus is not None else LIBRARY_CORPUS
        self.scope = scope
        self.model_key = provider.name
        self.raw_chunks = build_paragraph_chunks(self.corpus)
        self.ref_keys = [f"{di}:{pi}" for di, pi, _, _ in self.raw_chunks]
        self.vectors: Optional[list[list[float]]] = None

    def ensure_indexed(self) -> None:
        """缓存优先构建全部段落向量；缺失部分批量 embed 后回写。"""
        if self.vectors is not None:
            return
        cached = store.get_cached_embeddings(self.scope, self.ref_keys, self.model_key)
        # 防护：同 model_key 下若混入维度不符的旧向量，剔除并重新 embed
        if cached:
            expected_dim = len(next(iter(cached.values())))
            cached = {k: v for k, v in cached.items() if len(v) == expected_dim}
        missing = [
            (key, scored)
            for key, (_, _, _, scored) in zip(self.ref_keys, self.raw_chunks)
            if key not in cached
        ]
        if missing:
            log.info("向量索引：%d/%d 段需调用 embedding（%s）",
                     len(missing), len(self.ref_keys), self.model_key)
            new_vectors = self.provider.embed([text for _, text in missing])
            store.put_cached_embeddings(
                self.scope,
                self.model_key,
                {key: vec for (key, _), vec in zip(missing, new_vectors)},
            )
            cached.update({key: vec for (key, _), vec in zip(missing, new_vectors)})
        self.vectors = [cached[key] for key in self.ref_keys]

    def search_chunks(self, query: str, candidate_k: int = 20) -> list[tuple[int, float]]:
        """chunk 级余弦排名：[(chunk_index, score)] 降序。"""
        self.ensure_indexed()
        qvec = self.provider.embed([query])[0]
        scored = [
            (ci, cosine(qvec, chunk_vec)) for ci, chunk_vec in enumerate(self.vectors or [])
        ]
        scored = [(ci, s) for ci, s in scored if s > 0]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:candidate_k]
