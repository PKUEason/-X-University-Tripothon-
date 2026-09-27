# -*- coding: utf-8 -*-
"""Embedding 后端：可插拔，统一 embed(texts)->vectors 接口。

- OpenAICompatibleEmbeddingProvider：任何 OpenAI 兼容 /embeddings 端点
  （硅基流动免费 BGE、OpenAI、本地 vLLM/Ollama 等），复用已安装的 openai SDK；
- FastEmbedProvider：本地 ONNX 模型（fastembed 为可选依赖，见 requirements-rag.txt），
  装好后离线可跑，不发文档给第三方；
- HashEmbeddingProvider：零依赖确定性特征哈希，不是语义 embedding——
  用于测试融合管线，以及未配置任何后端时让向量路保持可运行；
- NoneProvider：显式关闭向量路。

工厂 build_provider() 按 settings 探测；任何后端构造失败都安全回退，不抛到服务层。
"""
import hashlib
import logging
import math
from typing import Any, Optional, Protocol

from app.config import settings

log = logging.getLogger("embeddings")


class EmbeddingProvider(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class NoneProvider:
    name = "none"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]


class HashEmbeddingProvider:
    """确定性特征哈希（feature hashing）：token→MD5 映射到固定维度，带符号消冲突。"""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        # name 含维度：不同维度实例的缓存互不覆盖
        self.name = f"hash-deterministic-{dim}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        from app.rag.retriever import tokenize

        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for tok in tokenize(text):
                h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
                idx = h % self.dim
                sign = 1.0 if (h >> 9) & 1 else -1.0
                vec[idx] += sign
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


class OpenAICompatibleEmbeddingProvider:
    """OpenAI 兼容 embedding API。构造不联网，首次 embed 才发起请求。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 30.0,
    ) -> None:
        from openai import OpenAI

        if not base_url:
            raise ValueError("EMBEDDING_BASE_URL 为空，无法使用 API 后端")
        self.client = OpenAI(
            base_url=base_url, api_key=api_key or "dummy-key", timeout=timeout
        )
        self.model = model
        self.name = f"api:{model}"
        self._dim = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self.client.embeddings.create(model=self.model, input=texts)
        ordered = sorted(resp.data, key=lambda d: d.index)
        vectors = [list(map(float, d.embedding)) for d in ordered]
        if vectors:
            self._dim = len(vectors[0])
        return vectors


class FastEmbedProvider:
    """fastembed 本地 ONNX embedding（可选依赖：pip install -r requirements-rag.txt）。"""

    def __init__(self, model: str) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise ImportError(
                "未安装 fastembed，请执行 pip install -r requirements-rag.txt"
            ) from exc
        self._engine = TextEmbedding(model_name=model)
        self.model_name = model
        self.name = f"fastembed:{model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = [list(map(float, v)) for v in self._engine.embed(texts)]
        return vectors


def _build_api_provider() -> Optional[OpenAICompatibleEmbeddingProvider]:
    if not settings.embedding_base_url:
        return None
    return OpenAICompatibleEmbeddingProvider(
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
        model=settings.embedding_model,
    )


def _build_fastembed_provider() -> Optional[FastEmbedProvider]:
    try:
        return FastEmbedProvider(settings.embedding_local_model)
    except Exception as exc:
        log.warning("fastembed 后端不可用：%s", exc)
        return None


def build_provider(kind: Optional[str] = None) -> EmbeddingProvider:
    """按配置构建 embedding 后端，失败逐级降级，保证返回可用对象。"""
    kind = (kind or settings.embedding_provider).lower()

    if kind == "none":
        return NoneProvider()
    if kind == "hash":
        return HashEmbeddingProvider()
    if kind == "api":
        provider = _build_api_provider()
        if provider:
            return provider
        log.warning("EMBEDDING_PROVIDER=api 但配置不全，降级哈希后端")
        return HashEmbeddingProvider()
    if kind == "fastembed":
        provider = _build_fastembed_provider()
        if provider:
            return provider
        log.warning("fastembed 不可用，降级哈希后端")
        return HashEmbeddingProvider()

    # auto：API 配置优先（真语义、零本地体积）→ fastembed → 哈希兜底
    api = _build_api_provider()
    if api is not None:
        log.info("embedding 自动选择 OpenAI 兼容 API：%s", settings.embedding_base_url)
        return api
    local = _build_fastembed_provider()
    if local is not None:
        log.info("embedding 自动选择 fastembed 本地模型")
        return local
    log.info("embedding 未配置任何后端，使用确定性哈希（无语义，仅保证管线可跑）")
    return HashEmbeddingProvider()
