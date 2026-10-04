"""Librarian：检索契约（第二阶段：BM25 RAG 已实现，curated 作为 MOCK / 兜底）。"""

from app.agents import librarian
from app.config import settings


def test_rag_enabled_by_default():
    assert librarian.RAG_ENABLED is True


def test_retrieve_returns_contract_shape():
    result = librarian.retrieve("DDPM", top_k=3)
    assert set(result) == set(librarian.CONTRACT_KEYS)
    assert result["notice"]
    assert 0 < len(result["documents"]) <= 3
    for doc in result["documents"]:
        assert set(doc) == {"title", "type", "url", "snippet"}


def test_retrieve_respects_top_k():
    assert len(librarian.retrieve("扩散模型 采样", top_k=2)["documents"]) <= 2


def test_mock_mode_forces_curated(monkeypatch):
    """MOCK_MODE=true（路演保险）→ 走精选语料，结果完全确定。"""
    monkeypatch.setattr(settings, "mock_mode", True)
    result = librarian.retrieve("DDPM")
    assert result["engine"] == "curated-v1"


def test_live_mode_routes_to_rag(monkeypatch):
    """真实模式 + RAG_ENABLED → hybrid 检索（证明开关不是摆设）。"""
    monkeypatch.setattr(settings, "mock_mode", False)
    result = librarian.retrieve("DDPM 噪声训练")
    assert result["engine"].startswith("hybrid-v2")
    assert result["documents"]


def test_rag_returns_relevant_documents(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    docs = librarian.retrieve("LoRA 低秩适配微调", top_k=3)["documents"]
    assert docs
    assert any("LoRA" in d["title"] for d in docs)
    for doc in docs:
        assert set(doc) == {"title", "type", "url", "snippet"}


def test_rag_unknown_topic_returns_no_unrelated_documents(monkeypatch):
    """Unsupported projects must not receive the diffusion demo collection."""
    monkeypatch.setattr(settings, "mock_mode", False)
    # 切 bm25 模式：生僻 query 无共同 token 必然零命中（hash 向量兜底可能假阳性）
    monkeypatch.setattr(librarian._hybrid, "mode", "bm25")
    for q in ("", "量子场论烹饪火星菜谱"):
        result = librarian.retrieve(q)
        assert result["documents"] == []
        assert "尚未覆盖" in result["notice"]


def test_rag_disabled_routes_to_curated(monkeypatch):
    """RAG 开关关闭时，即使真实模式也走 curated。"""
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(librarian, "RAG_ENABLED", False)
    assert librarian.retrieve("DDPM")["engine"] == "curated-v1"


def test_library_endpoint_in_mock_mode(client, session):
    r = client.post(
        "/api/library/retrieve", json={"session_id": session, "query": "DDPM", "top_k": 3}
    )
    assert r.status_code == 200
    assert r.json()["engine"] == "curated-v1"


def test_library_endpoint_in_live_mode(client, session, monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    r = client.post(
        "/api/library/retrieve",
        json={"session_id": session, "query": "Stable Diffusion 潜空间", "top_k": 3},
    )
    assert r.status_code == 200
    assert r.json()["engine"].startswith("hybrid-v2")
    assert r.json()["documents"]
