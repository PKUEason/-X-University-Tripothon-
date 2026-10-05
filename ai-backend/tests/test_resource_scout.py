"""resource_scout：课程视频 + 书籍推荐的单元测试。"""
import pytest
from app.config import settings
from app.services import resource_scout


# ---------------- 域名过滤 ----------------
def test_course_domain_filter():
    assert resource_scout._matches_domain("https://www.bilibili.com/video/BV1xx", resource_scout.COURSE_DOMAINS)
    assert resource_scout._matches_domain("https://youtube.com/watch?v=xxx", resource_scout.COURSE_DOMAINS)
    assert resource_scout._matches_domain("https://www.coursera.org/learn/ml", resource_scout.COURSE_DOMAINS)
    assert not resource_scout._matches_domain("https://example.com/blog", resource_scout.COURSE_DOMAINS)


def test_book_domain_filter():
    assert resource_scout._matches_domain("https://book.douban.com/subject/123", resource_scout.BOOK_DOMAINS)
    assert resource_scout._matches_domain("https://www.amazon.com/dp/123", resource_scout.BOOK_DOMAINS)
    assert resource_scout._matches_domain("https://www.oreilly.com/library/view/xxx", resource_scout.BOOK_DOMAINS)
    assert not resource_scout._matches_domain("https://example.com/book", resource_scout.BOOK_DOMAINS)


# ---------------- 去重 ----------------
def test_dedupe_by_url():
    items = [
        {"title": "A", "url": "https://x.com/a"},
        {"title": "A dup", "url": "https://x.com/a"},
        {"title": "B", "url": "https://x.com/b"},
    ]
    out = resource_scout._dedupe(items)
    assert len(out) == 2
    assert out[0]["title"] == "A"


# ---------------- search_courses ----------------
def test_search_courses_disabled(monkeypatch):
    monkeypatch.setattr(settings, "web_search_enabled", False)
    assert resource_scout.search_courses("python") == []


def test_search_courses_mock_mode(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", True)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    assert resource_scout.search_courses("python") == []


def test_search_courses_filters_domains(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    fake = [
        {"title": "B站 Python 教程", "url": "https://www.bilibili.com/video/BV1xx", "content": "course"},
        {"title": "无关博客", "url": "https://example.com/post", "content": "blog"},
    ]
    monkeypatch.setattr(
        "app.services.resource_scout.web_search.search",
        lambda q, max_results=8: (fake, "bingrss"),
    )
    out = resource_scout.search_courses("python", max_results=5)
    assert len(out) == 1
    assert out[0]["type"] == "course"
    assert out[0]["source"] == "course"
    assert "bilibili" in out[0]["url"]


def test_search_courses_swallows_errors(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    def boom(q, max_results=8):
        raise RuntimeError("network down")
    monkeypatch.setattr("app.services.resource_scout.web_search.search", boom)
    assert resource_scout.search_courses("python") == []


# ---------------- search_books ----------------
def test_search_books_filters_domains(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    fake = [
        {"title": "豆瓣 Python 编程", "url": "https://book.douban.com/subject/123", "content": "book"},
        {"title": "无关页面", "url": "https://example.com/page", "content": "other"},
    ]
    monkeypatch.setattr(
        "app.services.resource_scout.web_search.search",
        lambda q, max_results=8: (fake, "bingrss"),
    )
    out = resource_scout.search_books("python", max_results=5)
    assert len(out) == 1
    assert out[0]["type"] == "book"
    assert out[0]["source"] == "book"


# ---------------- scout 统一入口 ----------------
def test_scout_returns_combined(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    monkeypatch.setattr(resource_scout, "search_courses", lambda q, max_results=4: [
        {"title": "课程", "url": "https://bilibili.com/v/1", "type": "course", "source": "course"},
    ])
    monkeypatch.setattr(resource_scout, "search_books", lambda q, max_results=3: [
        {"title": "书籍", "url": "https://book.douban.com/subject/1", "type": "book", "source": "book"},
    ])
    results, status = resource_scout.scout("python")
    assert status == "ok"
    assert len(results) == 2
    types = {r["type"] for r in results}
    assert "course" in types
    assert "book" in types


def test_scout_disabled(monkeypatch):
    monkeypatch.setattr(settings, "web_search_enabled", False)
    results, status = resource_scout.scout("python")
    assert status == "disabled"
    assert results == []


def test_scout_mock_mode(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", True)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    results, status = resource_scout.scout("python")
    assert status == "mock"
    assert results == []


def test_scout_empty_query(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    results, status = resource_scout.scout("")
    assert results == []
