"""RAG 检索增强模块（第二阶段）。

- corpus.py：Library 文档库（含正文，可切块检索）
- retriever.py：零新依赖的 BM25 检索（中文专业词表 + 2-gram，英文直接切词）

设计取向：路演环境要稳定、离线可复现，因此 v1 不引入 sentence-transformers / Chroma
（模型文件大、Python 新版本兼容性风险）。语料规模在百篇以内时 BM25 效果足够，
返回结构与 curated 完全同构，前端零改动；未来要换向量检索只需替换 retriever 内部实现。
"""
