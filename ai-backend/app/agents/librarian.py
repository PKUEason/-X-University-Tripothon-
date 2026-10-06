"""Project-scoped retrieval from a small, explicitly covered local collection.

Local collection plus independent arXiv search. Unsupported local topics stay empty;
curated/mock mode must never substitute unrelated diffusion papers.
"""
import re
import logging
from typing import Any

from app.config import settings
from app.mock_data import golden_path as mock
from app.rag import arxiv as arxiv_client
from app.rag.corpus import LIBRARY_CORPUS
from app.rag.embeddings import build_provider
from app.rag.hybrid import HybridRetriever
from app.memory.store import store
from app.services import web_search
from app.services import resource_scout

RAG_ENABLED = True
RETRIEVAL_VERSION = 4
CONTRACT_KEYS = ('query', 'retrieval_version', 'coverage', 'engine', 'notice', 'results', 'sources', 'arxiv_query')
_embedding_provider = build_provider()
_hybrid = HybridRetriever(provider=_embedding_provider, mode=settings.rag_mode)
TOPICS = {
    'diffusion': r'扩散|文生图|去噪|潜空间|低秩适配|提示词|图像生成|生成图像|噪声调度|\b(?:ddpm|ddim|diffusion|diffusers|lora|clip|vae|u-net|fid|score-based)\b',
    'soft_robotics': r'柔性机器人|软体机器人|柔性机械|软体机械|气动|\b(?:soft robotics?|softrobots|pneunets?|sofa)\b',
}


def project_query(session_id: str) -> str:
    session = store.get_session(session_id) or {}
    messages = store.list_messages(session_id, agent='scholar', limit=20)
    parts = [session.get('goal') or ''] + [m['content'] for m in messages if m['role'] == 'user']
    return '\n'.join(dict.fromkeys(p.strip() for p in parts if p.strip()))[:4000]


def _retrieve_local(query: str, top_k: int = 5, *, force_search: bool = False) -> dict[str, Any]:
    topics = {topic for topic, pattern in TOPICS.items() if re.search(pattern, query or '', re.I)}
    eligible = [d for d in LIBRARY_CORPUS if d['topic'] in topics]
    base = {'query': query, 'retrieval_version': RETRIEVAL_VERSION, 'coverage': sorted(topics)}
    if not eligible:
        return {**base, 'documents': [], 'engine': 'local-collection',
                'notice': '当前资料库尚未覆盖这个项目方向，未找到可推荐的本地资料。不会用其他项目的文献填充；本地库目前仅覆盖扩散模型与柔性机器人入门资料。arXiv 论文和联网搜索会独立检索，与本地资料合并展示。'}
    allowed = {d['url'] for d in eligible}
    if (settings.mock_mode and not force_search) or not RAG_ENABLED:
        documents = mock.library_docs(query, top_k=top_k) if topics == {'diffusion'} else [
            {'title': d['title'], 'url': d['url'], 'type': d['type'], 'snippet': d['content'][:240]} for d in eligible]
        documents = [d for d in documents if d['url'] in allowed][:max(0, top_k)]
        engine, notice = 'curated-v1', '按当前项目主题筛选的本地资料（MOCK / 精选模式），不是全网检索。'
    else:
        documents = [d for d in _hybrid.search(query, top_k=len(LIBRARY_CORPUS)) if d['url'] in allowed][:max(0, top_k)]
        engine, notice = _hybrid.engine, _build_notice()
        if not documents:
            notice = '当前项目在本地资料库中没有相关命中；未用其他主题的资料填充。'
    return {**base, 'documents': documents, 'engine': engine, 'notice': notice}


def retrieve(query: str, top_k: int = 5, *, force_search: bool = False, arxiv_query: str | None = None) -> dict[str, Any]:
    """统一检索：自动从本地资料 + arXiv + 联网三路搜索，合并去重后返回单一 results 列表。

    每条结果标注 source（local / arxiv / web），前端无需分区展示。
    各路独立降级，任何一路失败不阻塞其他路；sources 字段记录每路状态。
    """
    local = _retrieve_local(query, top_k, force_search=force_search)
    terms = arxiv_query.strip() if arxiv_query is not None else arxiv_client.suggested_terms(query)
    arxiv_papers, arxiv_status = _fetch_arxiv(terms)
    web_results, web_status = _fetch_web(query)
    resource_results, resource_status = _fetch_resources(query)

    # 合并三路，按 url 去重，顺序：本地 → arXiv → 联网
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for doc in local['documents']:
        url = doc.get('url', '')
        if not url or url in seen:
            continue
        seen.add(url)
        results.append({
            'title': doc.get('title', ''),
            'url': url,
            'snippet': doc.get('snippet', ''),
            'source': 'local',
            'type': doc.get('type', 'doc'),
        })
    for paper in arxiv_papers:
        url = paper.get('url', '')
        if not url or url in seen:
            continue
        seen.add(url)
        results.append({
            'title': paper.get('title', ''),
            'url': url,
            'snippet': paper.get('snippet') or paper.get('summary', ''),
            'source': 'arxiv',
            'type': 'paper',
            'authors': paper.get('authors', []),
            'year': paper.get('year', ''),
        })
    for web in web_results:
        url = web.get('url', '')
        if not url or url in seen:
            continue
        seen.add(url)
        results.append({
            'title': web.get('title', ''),
            'url': url,
            'snippet': web.get('content', ''),
            'source': 'web',
            'type': 'webpage',
        })
    for res in resource_results:
        url = res.get('url', '')
        if not url or url in seen:
            continue
        seen.add(url)
        results.append({
            'title': res.get('title', ''),
            'url': url,
            'snippet': res.get('snippet', ''),
            'source': res.get('source', 'resource'),
            'type': res.get('type', 'resource'),
        })

    notice = local['notice']
    if arxiv_status == 'failed':
        notice += ' arXiv 检索不可用，请稍后重试。'
    if web_status == 'failed':
        notice += ' 联网搜索不可用，请稍后重试。'

    return {
        'query': local['query'],
        'retrieval_version': RETRIEVAL_VERSION,
        'coverage': local['coverage'],
        'engine': local['engine'],
        'notice': notice,
        'results': results,
        'sources': {'local': 'ok', 'arxiv': arxiv_status, 'web': web_status, 'resource': resource_status},
        'arxiv_query': terms,
    }


def _fetch_arxiv(query: str) -> tuple[list[dict[str, Any]], str]:
    if not settings.arxiv_enabled:
        return [], 'disabled'
    # Never label canned diffusion papers as live results for another topic.
    if settings.mock_mode:
        return [], 'mock'
    if not query or re.search(r'[\u3400-\u9fff]', query):
        return [], 'needs_query'
    try:
        return arxiv_client.search_arxiv(query, top_k=settings.arxiv_top_k,
                                        timeout=settings.arxiv_timeout), 'ok'
    except Exception:
        logging.getLogger(__name__).warning('arXiv search unavailable')
        return [], 'failed'


def _fetch_web(query: str) -> tuple[list[dict[str, Any]], str]:
    """联网搜索（Bing RSS 默认，免费无 key）。失败降级空结果，不阻塞 Library。"""
    if not settings.web_search_enabled:
        return [], 'disabled'
    if settings.mock_mode:
        return [], 'mock'
    if not query or not query.strip():
        return [], 'needs_query'
    try:
        results, provider = web_search.search(query, max_results=settings.web_search_max_results)
        if provider == 'mock':
            return [], 'failed'  # provider 降级到 mock 说明真实搜索失败
        return results, 'ok'
    except Exception:
        logging.getLogger(__name__).warning('web search unavailable')
        return [], 'failed'


def _fetch_resources(query: str) -> tuple[list[dict[str, Any]], str]:
    """资源推荐：搜索课程视频 + 书籍。失败降级空结果，不阻塞 Library。"""
    if not settings.web_search_enabled:
        return [], 'disabled'
    if settings.mock_mode:
        return [], 'mock'
    if not query or not query.strip():
        return [], 'needs_query'
    try:
        results, status = resource_scout.scout(query)
        return results, status
    except Exception:
        logging.getLogger(__name__).warning('resource scout unavailable')
        return [], 'failed'


def search_documents(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return _retrieve_local(query, top_k, force_search=True)['documents']


def _build_notice() -> str:
    if _hybrid.degraded:
        return '向量检索不可用，已改用本地关键词检索；结果仍按项目主题过滤。'
    if _hybrid.mode == 'bm25':
        return '按项目主题筛选的本地 BM25 关键词检索；不是全网检索。'
    return f'按项目主题筛选的本地 Hybrid RAG（{_embedding_provider.name}）；不是全网检索。'
