"""RAG 检索器单元测试：分词、BM25 排序、标题加权、零命中行为。"""
import pytest

from app.rag import retriever as r
from app.rag.corpus import LIBRARY_CORPUS


def test_corpus_is_well_formed():
    assert LIBRARY_CORPUS
    for doc in LIBRARY_CORPUS:
        assert doc["title"] and doc["url"] and doc["content"]
        assert doc["type"] in ("paper", "article", "video", "course", "tool")


def test_tokenize_english_terms():
    toks = r.tokenize("DDPM U-Net LoRA FID")
    assert "ddpm" in toks and "lora" in toks and "fid" in toks


def test_tokenize_chinese_vocab_match():
    toks = r.tokenize("扩散模型的前向过程加入高斯噪声")
    assert "扩散模型" in toks
    assert "前向过程" in toks
    assert "高斯噪声" in toks


def test_tokenize_chinese_bigram_fallback():
    # 词表外的中文按 2-gram 切
    toks = r.tokenize("菠萝披萨很好吃")
    assert len(toks) >= 2


def test_stopwords_removed():
    toks = r.tokenize("怎么 什么 为什么")
    assert "怎么" not in toks and "什么" not in toks


def test_retriever_built():
    assert r.retriever is not None
    assert r.retriever.N > 0


def test_search_ranks_topic_doc_first():
    docs = r.retrieve("LoRA 低秩适配", top_k=3)
    assert docs
    assert any("LoRA" in d["title"] for d in docs[:2])


def test_search_empty_query_returns_empty():
    assert r.retrieve("") == []


def test_search_unknown_query_returns_empty():
    assert r.retrieve("火星菜谱量子烹饪", top_k=3) == []


def test_search_snippet_is_plain_paragraph():
    docs = r.retrieve("DDPM 训练", top_k=1)
    assert docs
    # snippet 不应带标题前缀
    assert not docs[0]["snippet"].startswith(docs[0]["title"])


def test_search_respects_top_k():
    assert len(r.retrieve("扩散模型 采样 训练", top_k=2)) <= 2
