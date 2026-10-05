"""Librarian：统一检索契约（本地 + arXiv + 联网三路合并，v4）。"""

import pytest

from app.agents import librarian
from app.config import settings


@pytest.fixture(autouse=True)
def _stub_web_search(monkeypatch):
    """默认 mock 联网搜索，避免单元测试真实发网络请求。"""
    monkeypatch.setattr(
        librarian.web_search, "search",
        lambda q, max_results=8: ([], "bingrss"),
    )
    yield


def _sources(result):
    return result["sources"]


def _by_source(result, source):
    return [r for r in result["results"] if r["source"] == source]


def test_rag_enabled_by_default():
    assert librarian.RAG_ENABLED is True


def test_retrieve_returns_contract_shape():
    result = librarian.retrieve("DDPM", top_k=3)
    assert set(result) == set(librarian.CONTRACT_KEYS)
    assert result["notice"]
    assert "results" in result
    assert "sources" in result
    # 每条结果有统一字段
    for item in result["results"]:
        assert {"title", "url", "snippet", "source", "type"} <= set(item)


def test_retrieve_returns_local_results():
    result = librarian.retrieve("DDPM", top_k=3)
    local = _by_source(result, "local")
    assert 0 < len(local) <= 3
    for doc in local:
        assert doc["source"] == "local"
        assert set(doc) == {"title", "url", "snippet", "source", "type"}


def test_retrieve_respects_top_k():
    result = librarian.retrieve("扩散模型 采样", top_k=2)
    assert len(_by_source(result, "local")) <= 2


def test_mock_mode_forces_curated(monkeypatch):
    """MOCK_MODE=true（路演保险）→ 走精选语料，结果完全确定。"""
    monkeypatch.setattr(settings, "mock_mode", True)
    monkeypatch.setattr(settings, "arxiv_enabled", True)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    result = librarian.retrieve("DDPM")
    assert result["engine"] == "curated-v1"
    assert _sources(result)["arxiv"] == "mock"
    assert _sources(result)["web"] == "mock"


def test_live_mode_routes_to_rag(monkeypatch):
    """真实模式 + RAG_ENABLED → hybrid 检索（证明开关不是摆设）。"""
    monkeypatch.setattr(settings, "mock_mode", False)
    result = librarian.retrieve("DDPM 噪声训练")
    assert result["engine"].startswith("hybrid-v2")
    assert _by_source(result, "local")


def test_rag_returns_relevant_documents(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    local = _by_source(librarian.retrieve("LoRA 低秩适配微调", top_k=3), "local")
    assert local
    assert any("LoRA" in d["title"] for d in local)


def test_rag_unknown_topic_returns_no_unrelated_documents(monkeypatch):
    """Unsupported projects must not receive the diffusion demo collection."""
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(librarian._hybrid, "mode", "bm25")
    for q in ("", "量子场论烹饪火星菜谱"):
        result = librarian.retrieve(q)
        assert _by_source(result, "local") == []
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
    body = r.json()
    assert body["engine"] == "curated-v1"
    assert "results" in body
    assert "sources" in body


def test_library_endpoint_in_live_mode(client, session, monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    r = client.post(
        "/api/library/retrieve",
        json={"session_id": session, "query": "Stable Diffusion 潜空间", "top_k": 3},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["engine"].startswith("hybrid-v2")
    assert _by_source(body, "local")


# ---------------- 统一合并 / 去重 ----------------

def test_results_merged_from_all_sources(monkeypatch):
    """四路结果合并到单一 results 列表，各自标注 source。"""
    monkeypatch.setattr(settings, "mock_mode", False)
    fake_arxiv = [{"title": "ArXiv Paper", "url": "https://arxiv.org/abs/1234.5678",
                    "snippet": "arxiv abstract", "authors": ["A"], "year": "2024"}]
    fake_web = [{"title": "Web Tutorial", "url": "https://example.com/tut", "content": "web content"}]
    fake_resources = [{"title": "B站课程", "url": "https://www.bilibili.com/video/BV1xx", "snippet": "video course", "type": "course", "source": "course"}]
    monkeypatch.setattr(librarian, "_fetch_arxiv", lambda q: (fake_arxiv, "ok"))
    monkeypatch.setattr(librarian, "_fetch_web", lambda q: (fake_web, "ok"))
    monkeypatch.setattr(librarian, "_fetch_resources", lambda q: (fake_resources, "ok"))
    result = librarian.retrieve("diffusion model", top_k=2)
    sources = {r["source"] for r in result["results"]}
    assert "local" in sources
    assert "arxiv" in sources
    assert "web" in sources
    assert "course" in sources
    # arxiv 条目带 authors/year
    arxiv_item = _by_source(result, "arxiv")[0]
    assert arxiv_item["authors"] == ["A"]
    assert arxiv_item["year"] == "2024"
    assert arxiv_item["type"] == "paper"
    # web 条目
    web_item = _by_source(result, "web")[0]
    assert web_item["type"] == "webpage"
    assert web_item["snippet"] == "web content"
    # course 条目
    course_item = _by_source(result, "course")[0]
    assert course_item["type"] == "course"
    assert result["sources"]["resource"] == "ok"


def test_duplicate_urls_deduplicated(monkeypatch):
    """同一 url 出现在多路时只保留第一条（本地优先）。"""
    monkeypatch.setattr(settings, "mock_mode", False)
    # 让本地返回一个已知 url
    monkeypatch.setattr(
        librarian, "_retrieve_local",
        lambda q, top_k=5, force_search=False: {
            "query": q, "retrieval_version": 4, "coverage": ["diffusion"],
            "documents": [{"title": "Local", "url": "https://example.com/x",
                           "type": "paper", "snippet": "local"}],
            "engine": "curated-v1", "notice": "test",
        },
    )
    fake_web = [{"title": "Web Dup", "url": "https://example.com/x", "content": "web dup"}]
    monkeypatch.setattr(librarian, "_fetch_web", lambda q: (fake_web, "ok"))
    monkeypatch.setattr(librarian, "_fetch_arxiv", lambda q: ([], "ok"))
    result = librarian.retrieve("test")
    urls = [r["url"] for r in result["results"]]
    assert urls.count("https://example.com/x") == 1
    assert result["results"][0]["source"] == "local"  # 本地优先


def test_sources_records_each_channel_status(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(librarian, "_fetch_arxiv", lambda q: ([], "failed"))
    monkeypatch.setattr(librarian, "_fetch_web", lambda q: ([], "disabled"))
    monkeypatch.setattr(librarian, "_fetch_resources", lambda q: ([], "ok"))
    result = librarian.retrieve("DDPM")
    assert result["sources"]["local"] == "ok"
    assert result["sources"]["arxiv"] == "failed"
    assert result["sources"]["web"] == "disabled"
    assert result["sources"]["resource"] == "ok"
    assert "arXiv 检索不可用" in result["notice"]


# ---------------- Web 搜索（Bing RSS） ----------------

def test_web_search_returns_results(monkeypatch):
    """联网搜索成功时，results 中包含 source=web 的条目。"""
    monkeypatch.setattr(settings, "mock_mode", False)
    fake_results = [
        {"title": "Tutorial A", "url": "https://a.com", "content": "A"},
        {"title": "Tutorial B", "url": "https://b.com", "content": "B"},
    ]
    monkeypatch.setattr(
        librarian.web_search, "search",
        lambda q, max_results=8: (fake_results, "bingrss"),
    )
    result = librarian.retrieve("diffusion model", top_k=2)
    web = _by_source(result, "web")
    assert _sources(result)["web"] == "ok"
    assert len(web) == 2
    assert web[0]["title"] == "Tutorial A"


def test_web_search_disabled(monkeypatch):
    monkeypatch.setattr(settings, "web_search_enabled", False)
    result = librarian.retrieve("DDPM")
    assert _sources(result)["web"] == "disabled"
    assert _by_source(result, "web") == []


def test_web_search_mock_mode(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", True)
    result = librarian.retrieve("DDPM")
    assert _sources(result)["web"] == "mock"
    assert _by_source(result, "web") == []


def test_web_search_failure_does_not_block(monkeypatch):
    """联网搜索失败时，sources.web=failed，Library 整体仍正常返回。"""
    monkeypatch.setattr(settings, "mock_mode", False)
    def boom(q, max_results=8):
        raise RuntimeError("network down")
    monkeypatch.setattr(librarian.web_search, "search", boom)
    result = librarian.retrieve("DDPM", top_k=2)
    assert _sources(result)["web"] == "failed"
    assert _by_source(result, "web") == []
    # 不阻塞本地检索
    assert _by_source(result, "local")
    assert "联网搜索不可用" in result["notice"]


def test_web_search_empty_query(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(
        librarian.web_search, "search",
        lambda q, max_results=8: ([], "bingrss"),
    )
    result = librarian.retrieve("")
    assert _sources(result)["web"] == "needs_query"
    assert _by_source(result, "web") == []
