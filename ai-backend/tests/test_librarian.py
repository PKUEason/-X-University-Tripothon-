"""Librarian：检索契约 + Phase 2 开关的显式性。

回归背景：这里原本写的是 `if settings.mock_mode or True:`——条件恒真，
真实检索分支是死代码，还让人误以为检索行为会随 MOCK_MODE 变化。
"""
import pytest

from app.agents import librarian
from app.config import settings


def test_rag_disabled_by_default():
    assert librarian.RAG_ENABLED is False


def test_retrieve_returns_contract_shape():
    result = librarian.retrieve("DDPM", top_k=3)
    assert set(result) == set(librarian.CONTRACT_KEYS)
    assert result["engine"] == "curated-v1"
    assert result["notice"]
    assert 0 < len(result["documents"]) <= 3
    for doc in result["documents"]:
        assert set(doc) == {"title", "type", "url", "snippet"}


def test_retrieve_respects_top_k():
    assert len(librarian.retrieve("扩散", top_k=2)["documents"]) <= 2


def test_empty_query_still_returns_documents():
    assert librarian.retrieve("")["documents"]


def test_curated_path_is_independent_of_mock_mode(monkeypatch):
    """不管 MOCK_MODE 是什么，Phase 1 都走精选语料——现在这是显式行为。"""
    for mode in (True, False):
        monkeypatch.setattr(settings, "mock_mode", mode)
        assert librarian.retrieve("DDPM")["engine"] == "curated-v1"


def test_rag_path_fails_fast_while_unimplemented():
    """未实现就必须响亮地失败，而不是悄悄退回精选语料。"""
    with pytest.raises(NotImplementedError):
        librarian._retrieve_via_rag("DDPM")


def test_rag_switch_actually_routes(monkeypatch):
    """把开关打开后，retrieve 必须真的走到 RAG 分支（证明不是摆设）。"""
    monkeypatch.setattr(librarian, "RAG_ENABLED", True)
    with pytest.raises(NotImplementedError):
        librarian.retrieve("DDPM")


def test_library_endpoint_uses_curated_engine(client, session):
    r = client.post(
        "/api/library/retrieve", json={"session_id": session, "query": "DDPM", "top_k": 3}
    )
    assert r.status_code == 200
    assert r.json()["engine"] == "curated-v1"
