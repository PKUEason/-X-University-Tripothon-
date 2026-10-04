# -*- coding: utf-8 -*-
"""联网搜索服务测试：Bing RSS 解析、Tavily、mock、降级。"""
import pytest

from app.config import settings
from app.services import web_search

SAMPLE_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>Bing</title>
<item><title>Result One</title><link>https://example.com/1</link><description>Desc one here</description></item>
<item><title>Result Two</title><link>https://example.com/2</link><description>&lt;p&gt;Desc two with HTML&lt;/p&gt;</description></item>
<item><title></title><link>https://example.com/3</link><description>no title</description></item>
</channel></rss>"""


@pytest.fixture(autouse=True)
def _reset_providers():
    web_search.reset_provider()
    web_search.BingRSSProvider._cache.clear()
    web_search.BingRSSProvider._last_request = 0.0
    yield
    web_search.reset_provider()
    web_search.BingRSSProvider._cache.clear()


def test_mock_provider_returns_results():
    p = web_search.MockProvider()
    results = p.search("diffusion model", max_results=3)
    assert len(results) == 3
    assert all("title" in r and "url" in r and "content" in r for r in results)


def test_mock_provider_empty_query():
    p = web_search.MockProvider()
    results = p.search("", max_results=2)
    assert len(results) == 2


def test_bing_rss_parses_items(monkeypatch):
    class FakeResp:
        status_code = 200
        text = SAMPLE_RSS

        def raise_for_status(self):
            pass

    monkeypatch.setattr(web_search.httpx, "get", lambda *a, **k: FakeResp())
    p = web_search.BingRSSProvider(timeout=5)
    results = p.search("test query", max_results=5)
    assert len(results) == 2  # 第三条无 title 被跳过
    assert results[0]["title"] == "Result One"
    assert results[0]["url"] == "https://example.com/1"
    assert results[0]["content"] == "Desc one here"
    # HTML 标签被 strip
    assert results[1]["content"] == "Desc two with HTML"


def test_bing_rss_respects_max_results(monkeypatch):
    class FakeResp:
        status_code = 200
        text = SAMPLE_RSS

        def raise_for_status(self):
            pass

    monkeypatch.setattr(web_search.httpx, "get", lambda *a, **k: FakeResp())
    p = web_search.BingRSSProvider(timeout=5)
    results = p.search("test", max_results=1)
    assert len(results) == 1


def test_bing_rss_caches_results(monkeypatch):
    calls = []

    class FakeResp:
        status_code = 200
        text = SAMPLE_RSS

        def raise_for_status(self):
            pass

    def fake_get(*a, **k):
        calls.append(1)
        return FakeResp()

    monkeypatch.setattr(web_search.httpx, "get", fake_get)
    p = web_search.BingRSSProvider(timeout=5)
    p.search("cache test", max_results=3)
    p.search("cache test", max_results=3)  # 第二次命中缓存
    assert len(calls) == 1


def test_tavily_provider_parses_response(monkeypatch):
    class FakeResp:
        status_code = 200

        def json(self):
            return {"results": [
                {"title": "Paper A", "url": "https://a.com", "content": "content A"},
                {"title": "Paper B", "url": "https://b.com", "content": "content B"},
            ]}

        def raise_for_status(self):
            pass

    monkeypatch.setattr(web_search.httpx, "post", lambda *a, **k: FakeResp())
    p = web_search.TavilyProvider(api_key="test-key")
    results = p.search("test", max_results=2)
    assert len(results) == 2
    assert results[0]["title"] == "Paper A"


def test_search_auto_uses_bing_by_default(monkeypatch):
    """auto 模式无 Tavily key 时使用 Bing RSS。"""
    monkeypatch.setattr(settings, "tavily_api_key", "")
    monkeypatch.setattr(settings, "web_search_provider", "auto")

    class FakeResp:
        status_code = 200
        text = SAMPLE_RSS

        def raise_for_status(self):
            pass

    monkeypatch.setattr(web_search.httpx, "get", lambda *a, **k: FakeResp())
    results, provider = web_search.search("test", max_results=2)
    assert provider == "bingrss"
    assert len(results) == 2


def test_search_bing_failure_falls_back_to_mock(monkeypatch):
    """Bing 失败时降级 mock，保证永远有结果。"""
    monkeypatch.setattr(settings, "web_search_provider", "bing")

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(web_search.httpx, "get", boom)
    results, provider = web_search.search("test", max_results=2)
    assert provider == "mock"
    assert len(results) > 0
