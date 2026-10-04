# -*- coding: utf-8 -*-
"""联网搜索服务：Opportunity Scout 的数据来源。

可插拔 provider：
  - bing：Bing RSS 搜索（免费无 key，国内直连，默认）
  - tavily：Tavily Search API（专为 Agent 设计，免费 1000 次/月，需 TAVILY_API_KEY）
  - mock：预制结果（无网络 / 路演 / 离线时使用）
  - auto（默认）：优先 bing；显式配了 tavily 且有 key 时可用 tavily

任何 provider 失败都降级 mock，保证 Opportunity Scout 永远有结果。
"""
import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Protocol

import httpx2 as httpx

from app.config import settings

log = logging.getLogger("web_search")

TAVILY_API = "https://api.tavily.com/search"
BING_RSS_URL = "https://www.bing.com/search"


class SearchResult(dict):
    """单条搜索结果：title / url / content。"""


class SearchProvider(Protocol):
    def search(self, query: str, max_results: int) -> list[dict[str, str]]: ...


class TavilyProvider:
    """Tavily Search API。返回标准化的 [{title, url, content}]。"""

    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def search(self, query: str, max_results: int = 8) -> list[dict[str, str]]:
        resp = httpx.post(
            TAVILY_API,
            json={
                "api_key": self.api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": False,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": (r.get("content", "") or "")[:600],
            }
            for r in results
            if r.get("title")
        ]


class BingRSSProvider:
    """Bing RSS 搜索：免费无 key，国内直连 cn.bing.com，返回 [{title, url, content}]。

    使用 RSS 格式（?format=rss）返回 XML，比爬 HTML 稳定。
    模块级缓存 1 小时 + 1 秒礼貌限速。
    """

    _cache: dict[str, tuple[float, list[dict[str, str]]]] = {}
    _last_request = 0.0
    CACHE_TTL = 3600.0
    MIN_INTERVAL = 1.0

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def search(self, query: str, max_results: int = 8) -> list[dict[str, str]]:
        now = time.time()
        # 缓存命中
        cached = self._cache.get(query)
        if cached and now - cached[0] < self.CACHE_TTL:
            return cached[1][:max_results]
        # 限速
        wait = self.MIN_INTERVAL - (now - self._last_request)
        if wait > 0:
            time.sleep(wait)
        resp = httpx.get(
            BING_RSS_URL,
            params={"q": query, "format": "rss"},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/rss+xml,text/xml,*/*",
            },
            follow_redirects=True,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        type(self)._last_request = time.time()
        root = ET.fromstring(resp.text)
        items = root.findall(".//item")
        results: list[dict[str, str]] = []
        for item in items[:max_results]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = item.findtext("description") or ""
            desc_clean = re.sub(r"<[^>]+>", "", desc).strip()
            if title and link:
                results.append({"title": title, "url": link, "content": desc_clean[:600]})
        if results:
            type(self)._cache[query] = (time.time(), results)
        return results


class MockProvider:
    """预制搜索结果，不依赖网络。按 query 关键词简单匹配。"""

    _CORPUS = [
        {"title": "HuggingFace Diffusers", "url": "https://github.com/huggingface/diffusers",
         "content": "最主流的扩散模型推理/训练库，支持 Stable Diffusion、DDPM、DDIM 等，社区活跃，有大量示例脚本和预训练模型。"},
        {"title": "Stable Diffusion 官方仓库", "url": "https://github.com/Stability-AI/stablediffusion",
         "content": "Stability AI 官方的 Latent Diffusion 实现，包含训练、微调、推理代码，是理解潜空间扩散的最佳参考。"},
        {"title": "Papers with Code - Diffusion Models", "url": "https://paperswithcode.com/task/diffusion-models",
         "content": "扩散模型方向的论文、代码、排行榜聚合平台，可按任务筛选最新 SOTA 方法和开源实现。"},
        {"title": "r/StableDiffusion 社区", "url": "https://www.reddit.com/r/StableDiffusion/",
         "content": "Reddit 上最大的 Stable Diffusion 用户社区，每日分享作品、技巧、模型和工作流，适合找同好和最新动态。"},
        {"title": "Kaggle - Diffusion Models 竞赛与数据集", "url": "https://www.kaggle.com/search?q=diffusion+model",
         "content": "Kaggle 上扩散模型相关的竞赛、数据集和 Notebook，可免费使用 GPU 算力，是入门和实战的好平台。"},
        {"title": "AI 相关竞赛汇总（AI Crowd / CodaLab）", "url": "https://www.aicrowd.com/challenges",
         "content": "AI Crowd 和 CodaLab 上的机器学习竞赛平台，经常有图像生成、扩散模型相关赛事，有奖金和算力支持。"},
        {"title": "OpenAI / DeepSeek API 文档", "url": "https://platform.deepseek.com/",
         "content": "大模型 API 平台，可用于生成 prompt、辅助代码、做文本侧的创意生成，与扩散模型配合做完整应用。"},
        {"title": "GitHub Trending - Computer Vision", "url": "https://github.com/trending?since=weekly",
         "content": "GitHub 每周趋势榜，可发现最新开源的图像生成、扩散模型微调、ControlNet 等热门项目。"},
    ]

    def search(self, query: str, max_results: int = 8) -> list[dict[str, str]]:
        q = (query or "").lower()
        if not q:
            return self._CORPUS[:max_results]
        tokens = [t for t in q.split() if t] + [q]

        def score(item):
            hay = (item["title"] + item["content"]).lower()
            return sum(1 for t in tokens if t in hay)

        ranked = sorted(self._CORPUS, key=score, reverse=True)
        hits = [r for r in ranked if score(r) > 0]
        return (hits or self._CORPUS)[:max_results]


def _build_provider() -> SearchProvider:
    provider = (settings.web_search_provider or "auto").lower()
    if provider == "mock":
        return MockProvider()
    if provider == "tavily":
        if settings.tavily_api_key:
            return TavilyProvider(settings.tavily_api_key, timeout=settings.web_search_timeout)
        log.warning("TAVILY_API_KEY 未配置，回退 Bing RSS")
    # auto / bing / 默认 → Bing RSS（免费无 key，国内直连）
    return BingRSSProvider(timeout=settings.web_search_timeout)


_provider: SearchProvider | None = None


def search(query: str, max_results: int = 8) -> tuple[list[dict[str, str]], str]:
    """联网搜索，返回 (results, provider_name)。任何异常降级 mock。"""
    global _provider
    if _provider is None:
        _provider = _build_provider()
    name = type(_provider).__name__.lower().replace("provider", "")
    try:
        results = _provider.search(query, max_results=max_results)
        if results:
            return results, name
        log.warning("搜索结果为空，降级 mock")
    except Exception as exc:
        log.warning("搜索 provider %s 失败：%s，降级 mock", name, exc)
    return MockProvider().search(query, max_results=max_results), "mock"


def reset_provider() -> None:
    """测试用：重置 provider 单例。"""
    global _provider
    _provider = None
