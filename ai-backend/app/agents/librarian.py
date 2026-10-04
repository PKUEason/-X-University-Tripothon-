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

RAG_ENABLED = True
RETRIEVAL_VERSION = 3
CONTRACT_KEYS = ('documents', 'engine', 'notice', 'query', 'retrieval_version', 'coverage', 'arxiv_papers', 'arxiv_status', 'arxiv_query')
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
                'notice': '当前资料库尚未覆盖这个项目方向，未找到可推荐的资料。不会用其他项目的文献填充；本地库目前仅覆盖扩散模型与柔性机器人入门资料。下方 arXiv 论文独立检索，尚不包含网页教程。'}
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
    result = _retrieve_local(query, top_k, force_search=force_search)
    terms = arxiv_query.strip() if arxiv_query is not None else arxiv_client.suggested_terms(query)
    result['arxiv_query'] = terms
    result['arxiv_papers'], result['arxiv_status'] = _fetch_arxiv(terms)
    if result['arxiv_status'] == 'failed':
        result['notice'] += ' arXiv 检索不可用，请稍后重试。'
    return result


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


def search_documents(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return _retrieve_local(query, top_k, force_search=True)['documents']


def _build_notice() -> str:
    if _hybrid.degraded:
        return '向量检索不可用，已改用本地关键词检索；结果仍按项目主题过滤。'
    if _hybrid.mode == 'bm25':
        return '按项目主题筛选的本地 BM25 关键词检索；不是全网检索。'
    return f'按项目主题筛选的本地 Hybrid RAG（{_embedding_provider.name}）；不是全网检索。'
