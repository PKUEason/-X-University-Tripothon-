"""资源侦察：为学习目标推荐具体的课程视频、书籍、教程等。

基于 web_search（Bing RSS 默认），用教育类查询词搜索并过滤域名，
返回结构化的资源列表。失败时静默降级，不阻塞主流程。
"""
import logging
import re
from typing import Any

from app.config import settings
from app.services import web_search

log = logging.getLogger(__name__)

# 教育类域名白名单：课程视频
COURSE_DOMAINS = (
    'bilibili.com', 'youtube.com', 'youtu.be', 'coursera.org', 'udemy.com',
    'edx.org', 'xuetangx.com', 'icourse163.org', 'mooc.org', 'khanacademy.org',
    'mit.edu', 'opencourseware', 'skillshare.com', 'pluralsight.com',
    'lynda.com', 'linkedin.com/learning', 'freecodecamp.org', 'codecademy.com',
)

# 教育类域名白名单：书籍
BOOK_DOMAINS = (
    'book.douban.com', 'douban.com', 'amazon.com', 'amazon.cn', 'jd.com',
    'dangdang.com', 'oreilly.com', 'manning.com', 'nostarch.com',
    'packtpub.com', 'springer.com', 'elsevier.com', 'mitpress.mit.edu',
    'press.princeton.edu', 'books.google.com', 'goodreads.com',
)

# 查询词模板
COURSE_QUERIES = (
    '{q} 课程 教程 入门',
    '{q} course tutorial beginner',
    '{q} 视频教程',
)

BOOK_QUERIES = (
    '{q} 书籍 推荐',
    '{q} book recommendation',
    '{q} 教材 入门',
)


def _matches_domain(url: str, domains: tuple[str, ...]) -> bool:
    url_lower = (url or '').lower()
    return any(d in url_lower for d in domains)


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for item in items:
        url = item.get('url', '')
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(item)
    return out


def search_courses(query: str, max_results: int = 4) -> list[dict[str, Any]]:
    """搜索课程视频资源。返回 [{title, url, snippet, type, source}]。"""
    if not query or not settings.web_search_enabled or settings.mock_mode:
        return []
    results: list[dict[str, Any]] = []
    for tmpl in COURSE_QUERIES:
        q = tmpl.format(q=query)
        try:
            raw, provider = web_search.search(q, max_results=5)
            if provider == 'mock':
                continue
            for r in raw:
                url = r.get('url', '')
                if _matches_domain(url, COURSE_DOMAINS):
                    results.append({
                        'title': r.get('title', '').strip(),
                        'url': url,
                        'snippet': (r.get('content') or '').strip()[:200],
                        'type': 'course',
                        'source': 'course',
                    })
        except Exception as exc:
            log.warning('resource_scout 课程搜索失败：%s', exc)
    return _dedupe(results)[:max_results]


def search_books(query: str, max_results: int = 3) -> list[dict[str, Any]]:
    """搜索书籍资源。返回 [{title, url, snippet, type, source}]。"""
    if not query or not settings.web_search_enabled or settings.mock_mode:
        return []
    results: list[dict[str, Any]] = []
    for tmpl in BOOK_QUERIES:
        q = tmpl.format(q=query)
        try:
            raw, provider = web_search.search(q, max_results=5)
            if provider == 'mock':
                continue
            for r in raw:
                url = r.get('url', '')
                if _matches_domain(url, BOOK_DOMAINS):
                    results.append({
                        'title': r.get('title', '').strip(),
                        'url': url,
                        'snippet': (r.get('content') or '').strip()[:200],
                        'type': 'book',
                        'source': 'book',
                    })
        except Exception as exc:
            log.warning('resource_scout 书籍搜索失败：%s', exc)
    return _dedupe(results)[:max_results]


def scout(query: str, max_courses: int = 4, max_books: int = 3) -> tuple[list[dict[str, Any]], str]:
    """统一入口：搜索课程 + 书籍，返回 (results, status)。

    status: ok / disabled / mock / failed
    """
    if not settings.web_search_enabled:
        return [], 'disabled'
    if settings.mock_mode:
        return [], 'mock'
    try:
        courses = search_courses(query, max_results=max_courses)
        books = search_books(query, max_results=max_books)
        combined = courses + books
        if not combined:
            return [], 'ok'  # 搜索成功但无教育类命中
        return combined, 'ok'
    except Exception as exc:
        log.warning('resource_scout 失败：%s', exc)
        return [], 'failed'
