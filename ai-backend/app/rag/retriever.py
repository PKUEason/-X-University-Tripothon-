# -*- coding: utf-8 -*-
"""轻量 BM25 检索器：零新依赖，支持中英文专业语料。

分词策略：
- 英文/数字：正则切词（ddpm、unet、clip、lora、fid 等术语天然覆盖）；
- 中文：专业词表最大匹配 + 未命中部分按 2-gram 滑窗。

打分：标准 BM25（词频饱和 + 文档长度归一），段落级切块后把分数聚合回文档，
snippet 取该文档得分最高的段落。
"""
import math
import re
from collections import Counter
from typing import Any, Optional

from app.rag.corpus import LIBRARY_CORPUS

# 中文专业词表（最大匹配，长词优先）。随语料主题扩充即可。
TERM_VOCAB = (
    "扩散模型", "去噪扩散概率模型", "随机微分方程", "前向过程", "反向过程", "逆过程",
    "噪声调度", "高斯噪声", "潜空间", "文本到图像", "文生图", "图像到图像",
    "文本编码器", "交叉注意力", "时间步嵌入", "低秩适配", "参数高效",
    "生成图像", "训练稳定性", "采样路径", "采样步数", "快速采样", "确定性采样",
    "推理管线", "微调方法", "全量微调", "过拟合", "损失函数", "均方误差",
    "重参数化", "变分自编码器", "编码器", "解码器", "注意力", "卷积",
    "扩散", "去噪", "采样", "噪声", "推理", "训练", "评估", "数据集",
    "调度器", "检查点", "提示词", "负面提示词", "触发词", "梯度", "超参数",
    "优化器", "学习率", "批量", "迭代", "收敛", "归一化", "激活函数",
    "直觉", "数学", "论文", "文档", "工具", "质量", "风格", "主体",
    "图像", "文本", "模型", "网络", "框架", "目标", "任务", "步骤",
)

_EN_PATTERN = re.compile(r"[a-z0-9]+")
_HAN_PATTERN = re.compile(r"[一-龥]+")
_VOCAB_SORTED = sorted(TERM_VOCAB, key=len, reverse=True)

SNIPPET_LEN = 140

# 停用词：单字虚词 + 高频 2-gram 口语词，避免它们在 2-gram 切分后制造噪声匹配
STOPWORDS = {
    "的", "了", "是", "在", "和", "与", "或", "把", "被", "让", "用", "为", "以",
    "于", "中", "上", "下", "不", "也", "都", "就", "还", "很", "能", "会", "要",
    "想", "可", "吗", "呢", "啊", "吧", "怎么", "什么", "为什么", "怎样", "如何",
    "这个", "那个", "一个", "我们", "他们", "它们", "自己", "可以", "需要", "应该",
    "进行", "通过", "关于", "对于", "以及", "并且", "或者", "如果", "因为", "所以",
}


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    tokens = _EN_PATTERN.findall(text)
    for run in _HAN_PATTERN.findall(text):
        i = 0
        while i < len(run):
            matched = next((w for w in _VOCAB_SORTED if run.startswith(w, i)), None)
            if matched:
                tokens.append(matched)
                i += len(matched)
            else:
                if i + 1 < len(run):
                    tokens.append(run[i : i + 2])
                i += 1
    return [t for t in tokens if t not in STOPWORDS]


def _split_paragraphs(content: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n+", content) if p.strip()]


def build_paragraph_chunks(corpus: list[dict]) -> list[tuple[int, int, str, str]]:
    """统一的段落切块，BM25 与向量侧共用，保证 chunk 顺序严格对齐。

    返回：(doc_index, paragraph_index, display_para(纯段落), scored_text(标题+段落))
    """
    chunks: list[tuple[int, int, str, str]] = []
    for di, doc in enumerate(corpus):
        title = doc.get("title", "")
        for pi, para in enumerate(_split_paragraphs(doc.get("content", ""))):
            scored = f"{title}。{para}" if title else para
            chunks.append((di, pi, para, scored))
    return chunks


class BM25Retriever:
    """段落级 BM25，结果聚合回文档。"""

    def __init__(self, corpus: list[dict], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.corpus = corpus
        # chunks: (doc_index, display_para)；打分文本另存 title+para
        raw_chunks = build_paragraph_chunks(corpus)
        self.chunks: list[tuple[int, str]] = [(di, para) for di, _, para, _ in raw_chunks]
        scored_texts = [scored for _, _, _, scored in raw_chunks]
        self.chunk_tokens = [tokenize(text) for text in scored_texts]
        self.N = len(self.chunks)
        self.dl = [len(toks) for toks in self.chunk_tokens]
        self.avgdl = (sum(self.dl) / self.N) if self.N else 0.0
        self.tf = [Counter(toks) for toks in self.chunk_tokens]
        df: Counter = Counter()
        for toks in self.chunk_tokens:
            for term in set(toks):
                df[term] += 1
        self.idf = {
            term: math.log(1.0 + (self.N - n + 0.5) / (n + 0.5)) for term, n in df.items()
        }

    def _score_chunk(self, qi: list[str], ci: int) -> float:
        tf, dl = self.tf[ci], self.dl[ci]
        length_norm = 1.0 - self.b + self.b * (dl / self.avgdl if self.avgdl else 0.0)
        total = 0.0
        for term in qi:
            f = tf.get(term, 0)
            if f:
                total += self.idf.get(term, 0.0) * (f * (self.k1 + 1.0)) / (f + self.k1 * length_norm)
        return total

    def search_chunks(self, query: str, candidate_k: int = 20) -> list[tuple[int, float]]:
        """chunk 级排名（供 hybrid 融合）：[(chunk_index, score)] 降序。"""
        qi = tokenize(query)
        if not qi:
            return []
        scored = [
            (ci, self._score_chunk(qi, ci)) for ci in range(self.N)
        ]
        scored = [(ci, s) for ci, s in scored if s > 0]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:candidate_k]

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        ranked_chunks = self.search_chunks(query, candidate_k=self.N)
        # 段落得分 → 聚合到文档（取最高段落分，并记住该段落作为 snippet）
        best: dict[int, tuple[float, str]] = {}
        for ci, score in ranked_chunks:
            di, para = self.chunks[ci]
            if di not in best or score > best[di][0]:
                best[di] = (score, para)
        ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:top_k]
        docs = []
        for di, (_score, para) in ranked:
            src = self.corpus[di]
            snippet = para if len(para) <= SNIPPET_LEN else para[:SNIPPET_LEN] + "…"
            docs.append(
                {
                    "title": src["title"],
                    "type": src.get("type", "article"),
                    "url": src.get("url", ""),
                    "snippet": snippet,
                }
            )
        return docs


# 进程内单例（语料固定，import 时构建一次）
retriever: Optional[BM25Retriever] = None
if LIBRARY_CORPUS:
    retriever = BM25Retriever(LIBRARY_CORPUS)


def retrieve(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    if retriever is None:
        return []
    return retriever.search(query, top_k=top_k)
