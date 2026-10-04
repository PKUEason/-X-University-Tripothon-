# -*- coding: utf-8 -*-
"""arXiv 实时检索：Library 空间的「最新论文」区。

- 官方 API：http://export.arxiv.org/api/query（免费、无需 key）；
- 解析 Atom XML（标准库 xml.etree，零依赖）；
- 内存缓存 1 小时，避免重复查询；
- 限速 3 秒/次（arXiv 官方要求），超时默认 5 秒，失败抛异常由上层降级；
- 只用于 Library 展示区，不注入 Professor prompt（避免外部内容不可控）。
"""
import logging
import re
import time
from threading import Lock
import xml.etree.ElementTree as ET
from typing import Any, Optional

import httpx2 as httpx

log = logging.getLogger("arxiv")

ARXIV_API = "https://export.arxiv.org/api/query"
_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
_CACHE_TTL = 3600.0  # 1 小时
_RATE_LIMIT_SEC = 3.0
_SNIPPET_LEN = 220

_cache: dict[tuple[str, int], tuple[float, list[dict]]] = {}
_last_request_ts = 0.0
_request_lock = Lock()


def suggested_terms(query: str) -> str:
    """Small explicit bilingual hints; other Chinese topics need user keywords.

    No translation model is called and no unknown topic is silently mapped to AI.
    """
    for pattern, terms in [
        (r'柔性机器人|软体机器人|soft robotics', 'soft robotics'),
        (r'扩散模型|文生图|diffusion|ddpm|ddim', 'diffusion models'),
        (r'AI\s*硬件|人工智能硬件|嵌入式.*(?:AI|机器学习)|tinyml', 'TinyML, embedded machine learning'),
        (r'机器人视觉', 'robot vision'),
    ]:
        if re.search(pattern, query, re.I):
            return terms
    return '' if re.search(r'[\u3400-\u9fff]', query) else query.strip()[:200]


def search_expression(query: str) -> str:
    # Phrase queries avoid an unqualified long sentence matching only "AI".
    terms = [re.sub(r'[^a-zA-Z0-9 _-]', ' ', term).strip()
             for term in re.split(r'[,，;；]', query)]
    return ' OR '.join(f'all:"{term}"' for term in terms if term)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _parse_atom(xml_text: str) -> list[dict[str, Any]]:
    """解析 arXiv Atom 响应，返回标准化论文列表。"""
    root = ET.fromstring(xml_text)
    papers: list[dict[str, Any]] = []
    for entry in root.findall("a:entry", _ATOM_NS):
        title = _collapse(entry.findtext("a:title", default="", namespaces=_ATOM_NS))
        summary = _collapse(entry.findtext("a:summary", default="", namespaces=_ATOM_NS))
        arxiv_id = entry.findtext("a:id", default="", namespaces=_ATOM_NS).strip()
        if '/api/errors' in arxiv_id:
            raise ValueError('arXiv returned an API error')
        published = entry.findtext("a:published", default="", namespaces=_ATOM_NS)
        year = published[:4] if published else ""
        authors = [
            _collapse(a.findtext("a:name", default="", namespaces=_ATOM_NS))
            for a in entry.findall("a:author", _ATOM_NS)
        ]
        # abs 页 URL：优先 rel=alternate 的 link，否则用 id
        url = arxiv_id
        for link in entry.findall("a:link", _ATOM_NS):
            if link.get("rel") == "alternate":
                url = link.get("href", arxiv_id)
                break
        snippet = summary if len(summary) <= _SNIPPET_LEN else summary[:_SNIPPET_LEN] + "…"
        papers.append(
            {
                "title": title,
                "authors": authors,
                "year": year,
                "url": url,
                "snippet": snippet,
            }
        )
    return papers


def _respect_rate_limit() -> None:
    global _last_request_ts
    now = time.monotonic()
    wait = _RATE_LIMIT_SEC - (now - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.monotonic()


def search_arxiv(
    query: str, top_k: int = 3, timeout: float = 5.0
) -> list[dict[str, Any]]:
    """按相关性检索 arXiv，返回 top_k 篇论文。空结果返回 []。"""
    q = (query or "").strip()
    expression = search_expression(q)
    if not expression:
        return []
    if top_k <= 0:
        return []
    cache_key = (q.lower(), top_k)
    now = time.time()
    if cache_key in _cache:
        ts, papers = _cache[cache_key]
        if now - ts < _CACHE_TTL:
            return papers[:top_k]

    with _request_lock:
        _respect_rate_limit()
    resp = httpx.get(
        ARXIV_API,
        params={
            "search_query": expression,
            "start": 0,
            "max_results": top_k,
        },
        timeout=timeout,
        follow_redirects=True,
    )
    resp.raise_for_status()
    papers = _parse_atom(resp.text)
    _cache[cache_key] = (now, papers)
    return papers[:top_k]


def clear_cache() -> None:
    """测试用：清空内存缓存。"""
    _cache.clear()
