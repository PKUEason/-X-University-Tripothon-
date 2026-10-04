# -*- coding: utf-8 -*-
"""arXiv 实时检索测试：XML 解析、缓存、librarian 集成与失败降级。"""
import pytest

from app.agents import librarian
from app.config import settings
from app.rag import arxiv as arxiv_client


def _local(result):
    return [r for r in result["results"] if r["source"] == "local"]


def _arxiv(result):
    return [r for r in result["results"] if r["source"] == "arxiv"]

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
def test_librarian_mock_is_explicit_and_never_fills_other_topics(monkeypatch):
    monkeypatch.setattr(settings, 'arxiv_enabled', True)
    result = librarian.retrieve('AI 硬件', top_k=3)
    assert set(librarian.CONTRACT_KEYS) == set(result)
    assert result['sources']['arxiv'] == 'mock'
    assert _arxiv(result) == []
    assert _local(result) == []


def test_librarian_arxiv_failure_degrades(monkeypatch):
    """arXiv 失败时本地资料不受影响，arxiv_papers 为空。"""
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "arxiv_enabled", True)

    def boom(query, top_k=3, timeout=5.0):
        raise RuntimeError("network down")

    monkeypatch.setattr(arxiv_client, "search_arxiv", boom)
    result = librarian.retrieve("diffusion", top_k=3)
    assert _arxiv(result) == []
    assert result["sources"]["arxiv"] == "failed"
    assert len(_local(result)) > 0  # 本地 hybrid 正常
    assert "arXiv 检索不可用" in result["notice"]


def test_librarian_arxiv_disabled(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "arxiv_enabled", False)
    result = librarian.retrieve("diffusion", top_k=3)
    assert result["sources"]["arxiv"] == "disabled"
    assert _arxiv(result) == []


def test_search_documents_excludes_arxiv():
    """Professor 复用的检索归口不混入外部论文。"""
    docs = librarian.search_documents("diffusion", top_k=3)
    assert isinstance(docs, list)
    # 本地文档字段是 title/type/url/snippet，不含 authors/year
    assert all("authors" not in d for d in docs)


def test_uncovered_local_topic_still_searches_arxiv_and_persists_per_project(client, monkeypatch):
    from app.memory.store import store
    from app.memory.artifacts import read_artifact
    monkeypatch.setattr(settings, 'mock_mode', False)
    monkeypatch.setattr(settings, 'arxiv_enabled', True)
    queries = []
    def search(query, **kwargs):
        queries.append(query)
        return [{'title': query, 'authors': ['Author'], 'year': '2026',
                 'url': 'https://arxiv.org/abs/1234.5678', 'snippet': 'test abstract'}]
    monkeypatch.setattr(arxiv_client, 'search_arxiv', search)
    ids = [store.create_session(goal=goal) for goal in ('AI 硬件', '机器人视觉')]
    for sid in ids:
        store.update_state(sid, quest_status='professor')
        response = client.post('/api/library/retrieve', json={'session_id': sid, 'query': ''})
        assert response.status_code == 200
        result = response.json()
        assert result['sources']['arxiv'] == 'ok'
        assert _local(result) == []
        assert _arxiv(result)[0]['title'] == result['arxiv_query']
        assert read_artifact(sid, 'library_result') == result
        assert store.get_state(sid)['quest_status'] == 'professor'
    assert queries == ['TinyML, embedded machine learning', 'robot vision']
    assert _arxiv(read_artifact(ids[0], 'library_result'))[0]['title'] == 'TinyML, embedded machine learning'


def test_empty_results_are_success_not_failure(monkeypatch):
    monkeypatch.setattr(settings, 'mock_mode', False)
    monkeypatch.setattr(settings, 'arxiv_enabled', True)
    monkeypatch.setattr(arxiv_client, 'search_arxiv', lambda *a, **kw: [])
    assert librarian.retrieve('AI 硬件')['sources']['arxiv'] == 'ok'


def test_professor_does_not_trigger_external_search(monkeypatch):
    monkeypatch.setattr(settings, 'mock_mode', False)
    monkeypatch.setattr(settings, 'arxiv_enabled', True)
    def unexpected(*args, **kwargs):
        raise AssertionError('Professor must not trigger an unused external search')
    monkeypatch.setattr(arxiv_client, 'search_arxiv', unexpected)
    assert librarian.search_documents('DDPM')


def test_arxiv_error_feed_is_not_a_paper():
    xml = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors#incorrect_id_format</id><title>Error</title></entry></feed>'
    with pytest.raises(ValueError):
        arxiv_client._parse_atom(xml)


def test_cache_honors_requested_result_count(monkeypatch):
    arxiv_client.clear_cache()
    calls = []
    class Resp:
        text = SAMPLE_ATOM
        def raise_for_status(self):
            pass
    monkeypatch.setattr(arxiv_client, '_respect_rate_limit', lambda: None)
    def get(url, **kwargs):
        assert url.startswith('https://')
        calls.append(kwargs['params']['max_results'])
        return Resp()
    monkeypatch.setattr(arxiv_client.httpx, 'get', get)
    assert len(arxiv_client.search_arxiv('test', 1)) == 1
    assert len(arxiv_client.search_arxiv('test', 2)) == 2
    assert calls == [1, 2]
    arxiv_client.clear_cache()


def test_chinese_topic_mapping_and_unknown_topic_require_keywords():
    assert arxiv_client.suggested_terms('我完全零基础，每周三小时，想学 AI 硬件') == 'TinyML, embedded machine learning'
    assert arxiv_client.suggested_terms('我想学植物种植') == ''
    assert arxiv_client.search_expression('TinyML, embedded machine learning') == 'all:"TinyML" OR all:"embedded machine learning"'


def test_unmapped_chinese_query_does_not_match_generic_ai(monkeypatch):
    monkeypatch.setattr(settings, 'mock_mode', False)
    monkeypatch.setattr(settings, 'arxiv_enabled', True)
    monkeypatch.setattr(arxiv_client, 'search_arxiv', lambda *a, **kw: pytest.fail('must request keywords first'))
    result = librarian.retrieve('我想学植物种植')
    assert result['sources']['arxiv'] == 'needs_query'
    assert _arxiv(result) == []


def test_manual_paper_query_preserves_original_project_and_stage(client, monkeypatch):
    from app.memory.store import store
    monkeypatch.setattr(settings, 'mock_mode', False)
    monkeypatch.setattr(settings, 'arxiv_enabled', True)
    terms = []
    monkeypatch.setattr(arxiv_client, 'search_arxiv', lambda query, **kw: terms.append(query) or [])
    sid = store.create_session(goal='AI 硬件')
    store.update_state(sid, quest_status='professor')
    response = client.post('/api/library/retrieve', json={'session_id': sid, 'query': '', 'arxiv_query': 'keyword spotting'})
    assert response.status_code == 200
    assert response.json()['query'] == 'AI 硬件'
    assert response.json()['arxiv_query'] == 'keyword spotting'
    assert terms == ['keyword spotting']
    assert store.get_state(sid)['quest_status'] == 'professor'
