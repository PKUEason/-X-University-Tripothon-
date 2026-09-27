# -*- coding: utf-8 -*-
"""向量 RAG 升级测试：embedding 后端 / 向量缓存 / RRF 融合 / hybrid 检索 / 降级。"""
import math

import pytest

from app.agents import librarian
from app.config import settings
from app.memory.store import store
from app.rag import embeddings as emb
from app.rag.corpus import LIBRARY_CORPUS
from app.rag.hybrid import HybridRetriever, rrf
from app.rag.vector_index import VectorIndex, cosine


# ---------- fixtures: 可控后端 ----------
class CountingProvider:
    """计数 + 复用哈希向量：用于验证缓存命中。"""
    name = "test-counting-64"

    def __init__(self):
        self.calls = 0
        self._hash = emb.HashEmbeddingProvider(64)

    def embed(self, texts):
        self.calls += 1
        return self._hash.embed(texts)


class BrokenProvider:
    name = "test-broken"

    def embed(self, texts):
        raise RuntimeError("embedding 服务连接被拒绝")


# ---------- HashEmbeddingProvider ----------
def test_hash_provider_dim_and_norm():
    p = emb.HashEmbeddingProvider(128)
    vecs = p.embed(["扩散模型前向加噪", "LoRA 微调"])
    assert all(len(v) == 128 for v in vecs)
    for v in vecs:
        assert abs(math.sqrt(sum(x * x for x in v)) - 1.0) < 1e-6


def test_hash_provider_deterministic():
    p = emb.HashEmbeddingProvider(64)
    assert p.embed(["DDPM 训练"]) == p.embed(["DDPM 训练"])
    assert p.embed(["DDPM"]) != p.embed(["LoRA"])


def test_none_provider():
    assert emb.NoneProvider().embed(["x"]) == [[]]


# ---------- 工厂 ----------
def test_build_hash_provider():
    p = emb.build_provider("hash")
    assert isinstance(p, emb.HashEmbeddingProvider)


def test_build_none_provider():
    assert emb.build_provider("none").name == "none"


def test_build_api_without_url_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "embedding_base_url", "")
    p = emb.build_provider("api")
    assert isinstance(p, emb.HashEmbeddingProvider)


def test_build_fastembed_without_package_falls_back():
    # fastembed 未安装（主环境刻意不装）→ 哈希兜底
    p = emb.build_provider("fastembed")
    assert isinstance(p, emb.HashEmbeddingProvider)


def test_build_api_provider(monkeypatch):
    monkeypatch.setattr(settings, "embedding_base_url", "https://example.com/v1")
    monkeypatch.setattr(settings, "embedding_model", "fake-model")
    p = emb.build_provider("api")
    assert isinstance(p, emb.OpenAICompatibleEmbeddingProvider)
    assert p.name == "api:fake-model"


# ---------- VectorIndex + 缓存 ----------
def test_vector_index_builds_and_searches():
    p = CountingProvider()
    idx = VectorIndex(p, LIBRARY_CORPUS, scope="test-build")
    ranks = idx.search_chunks("DDPM 反向去噪", candidate_k=5)
    assert len(ranks) == 5
    assert all(isinstance(ci, int) and isinstance(s, float) for ci, s in ranks)


def test_vector_index_caches_in_memory():
    p = CountingProvider()
    idx = VectorIndex(p, LIBRARY_CORPUS, scope="test-memcache")
    idx.ensure_indexed()
    first_calls = p.calls
    idx.ensure_indexed()  # 第二次不应再调 embed
    assert p.calls == first_calls


def test_vector_index_persists_to_store():
    """新实例、同 model_key：段落向量全部从 SQLite 缓存恢复，provider 零调用。"""
    p1 = CountingProvider()
    idx1 = VectorIndex(p1, LIBRARY_CORPUS, scope="test-persist")
    idx1.ensure_indexed()
    assert p1.calls >= 1

    p2 = CountingProvider()
    idx2 = VectorIndex(p2, LIBRARY_CORPUS, scope="test-persist")
    idx2.ensure_indexed()
    assert p2.calls == 0  # 全部命中持久化缓存
    assert idx1.vectors == idx2.vectors


def test_cosine_basic():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([1, 0], [-1, 0]) == pytest.approx(-1.0)


# ---------- RRF ----------
def test_rrf_single_list():
    fused = rrf([[3, 1, 2]])
    assert fused == [3, 1, 2]


def test_rrf_two_lists_prefers_shared_items():
    # 项 5 在两路都靠前 → 总分最高
    fused = rrf([[5, 1, 2], [3, 5, 4]])
    assert fused[0] == 5


# ---------- HybridRetriever ----------
def test_hybrid_mode_engine():
    p = emb.HashEmbeddingProvider(64)
    h = HybridRetriever(LIBRARY_CORPUS, provider=p, mode="hybrid")
    docs = h.search("LoRA 低秩适配", top_k=3)
    assert docs and h.engine.startswith("hybrid-v2")
    assert any("LoRA" in d["title"] for d in docs)


def test_bm25_mode_engine():
    h = HybridRetriever(LIBRARY_CORPUS, provider=emb.HashEmbeddingProvider(64), mode="bm25")
    docs = h.search("DDPM 噪声", top_k=3)
    assert docs and h.engine == "bm25-v1"


def test_vector_mode_engine():
    p = emb.HashEmbeddingProvider(64)
    h = HybridRetriever(LIBRARY_CORPUS, provider=p, mode="vector")
    docs = h.search("Stable Diffusion 潜空间", top_k=3)
    assert docs and h.engine.startswith("vector-v2")


def test_hybrid_degrades_when_embedding_broken():
    h = HybridRetriever(LIBRARY_CORPUS, provider=BrokenProvider(), mode="hybrid")
    docs = h.search("DDPM 训练", top_k=3)
    assert docs  # 降级 BM25 仍有结果
    assert h.engine == "bm25-v1"
    assert h.degraded is True


def test_vector_mode_degrades_when_broken():
    h = HybridRetriever(LIBRARY_CORPUS, provider=BrokenProvider(), mode="vector")
    docs = h.search("DDPM", top_k=3)
    assert docs and h.engine == "bm25-v1"
    assert h.degraded


def test_hybrid_doc_contract():
    h = HybridRetriever(LIBRARY_CORPUS, provider=emb.HashEmbeddingProvider(64))
    for doc in h.search("CLIP 文本编码", top_k=3):
        assert set(doc) == {"title", "type", "url", "snippet"}


def test_none_provider_routes_bm25():
    h = HybridRetriever(LIBRARY_CORPUS, provider=emb.NoneProvider(), mode="hybrid")
    docs = h.search("DDPM", top_k=3)
    assert docs and h.engine == "bm25-v1"


# ---------- librarian / 端点 ----------
def test_librarian_mock_uses_curated(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", True)
    assert librarian.retrieve("DDPM")["engine"] == "curated-v1"


def test_librarian_live_uses_hybrid(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    result = librarian.retrieve("LoRA 微调", top_k=3)
    assert "bm25" in result["engine"] or "hybrid" in result["engine"]


def test_library_endpoint_mock_engine(client, session):
    r = client.post(
        "/api/library/retrieve", json={"session_id": session, "query": "DDPM"}
    )
    assert r.status_code == 200
    assert r.json()["engine"] == "curated-v1"
