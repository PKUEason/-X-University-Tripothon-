# -*- coding: utf-8 -*-
"""arXiv 实时检索测试：XML 解析、缓存、librarian 集成与失败降级。"""
import pytest

from app.agents import librarian
from app.config import settings
from app.rag import arxiv as arxiv_client

SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>ArXiv Query Results</title>
  <entry>
    <id>http://arxiv.org/abs/2006.11239v2</id>
    <updated>2020-06-19T17:51:21Z</updated>
    <published>2020-06-19T17:51:21Z</published>
    <title>Denoising Diffusion Probabilistic Models</title>
    <summary>We present high quality image synthesis results using diffusion probabilistic models, a class of latent variable models inspired by nonequilibrium thermodynamics.</summary>
    <author><name>Jonathan Ho</name></author>
    <author><name>Ajay Jain</name></author>
    <author><name>Pieter Abbeel</name></author>
    <link title="pdf" href="http://arxiv.org/pdf/2006.11239v2" rel="related"/>
    <link title="html" href="http://arxiv.org/abs/2006.11239v2" rel="alternate" type="text/html"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2112.10752v2</id>
    <published>2021-12-20T00:00:00Z</published>
    <title>High-Resolution Image Synthesis with Latent Diffusion Models</title>
    <summary>We propose latent diffusion models which operate in the latent space of a pretrained autoencoder.</summary>
    <author><name>Robin Rombach</name></author>
  </entry>
</feed>
"""

EMPTY_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Empty</title></feed>
"""


# ---------- XML 解析 ----------
def test_parse_atom_basic():
    papers = arxiv_client._parse_atom(SAMPLE_ATOM)
    assert len(papers) == 2
    p = papers[0]
    assert p["title"] == "Denoising Diffusion Probabilistic Models"
    assert p["authors"] == ["Jonathan Ho", "Ajay Jain", "Pieter Abbeel"]
    assert p["year"] == "2020"
    assert p["url"] == "http://arxiv.org/abs/2006.11239v2"
    assert "diffusion probabilistic models" in p["snippet"].lower()


def test_parse_atom_empty():
    assert arxiv_client._parse_atom(EMPTY_ATOM) == []


def test_parse_atom_collapses_whitespace():
    xml = (
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
        "<title>  Multi\n  Line  Title  </title>"
        "<published>2021-01-01T00:00:00Z</published>"
        "<summary>  spaced   abstract  </summary>"
        "</entry></feed>"
    )
    p = arxiv_client._parse_atom(xml)[0]
    assert p["title"] == "Multi Line Title"
    assert p["snippet"] == "spaced abstract"


# ---------- 缓存 / 空查询 ----------
def test_search_arxiv_empty_query():
    assert arxiv_client.search_arxiv("   ") == []


def test_search_arxiv_uses_cache(monkeypatch):
    arxiv_client.clear_cache()
    calls = []

    class FakeResp:
        status_code = 200
        text = SAMPLE_ATOM

        def raise_for_status(self):
            pass

    def fake_get(url, **kw):
        calls.append(url)
        return FakeResp()

    monkeypatch.setattr(arxiv_client.httpx, "get", fake_get)
    r1 = arxiv_client.search_arxiv("diffusion model", top_k=1)
    r2 = arxiv_client.search_arxiv("diffusion model", top_k=1)
    assert len(calls) == 1  # 第二次命中缓存，不发请求
    assert r1 == r2
    assert len(r1) == 1  # top_k 生效
    arxiv_client.clear_cache()


# ---------- librarian 集成（conftest 注入 MOCK_MODE=true） ----------
def test_librarian_retrieve_includes_arxiv_mock():
    result = librarian.retrieve("diffusion model", top_k=3)
    assert set(librarian.CONTRACT_KEYS).issubset(result.keys())
    assert result["arxiv_status"] == "ok"
    assert len(result["arxiv_papers"]) > 0
    paper = result["arxiv_papers"][0]
    assert {"title", "authors", "year", "url", "snippet"}.issubset(paper.keys())
    # 本地资料与 arXiv 分区共存
    assert len(result["documents"]) > 0


def test_librarian_arxiv_failure_degrades(monkeypatch):
    """arXiv 失败时本地资料不受影响，arxiv_papers 为空。"""
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "arxiv_enabled", True)

    def boom(query, top_k=3, timeout=5.0):
        raise RuntimeError("network down")

    monkeypatch.setattr(arxiv_client, "search_arxiv", boom)
    result = librarian.retrieve("diffusion", top_k=3)
    assert result["arxiv_papers"] == []
    assert result["arxiv_status"] == "failed"
    assert len(result["documents"]) > 0  # 本地 hybrid 正常
    assert "arXiv 检索不可用" in result["notice"]


def test_librarian_arxiv_disabled(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "arxiv_enabled", False)
    result = librarian.retrieve("diffusion", top_k=3)
    assert result["arxiv_status"] == "disabled"
    assert result["arxiv_papers"] == []


def test_search_documents_excludes_arxiv():
    """Professor 复用的检索归口不混入外部论文。"""
    docs = librarian.search_documents("diffusion", top_k=3)
    assert isinstance(docs, list)
    # 本地文档字段是 title/type/url/snippet，不含 authors/year
    assert all("authors" not in d for d in docs)
