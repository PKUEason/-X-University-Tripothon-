# -*- coding: utf-8 -*-
"""AI Professor 第二阶段：RAG 注入 + references 事件 + 卡点记忆。"""

from app.agents import librarian, professor
from app.memory.store import store


def _events(session_id, message, task_id=None):
    return list(professor.stream_chat(session_id, message, task_id=task_id))


def test_professor_reuses_librarian_retrieval(monkeypatch, client, session):
    """钉住检索入口：Professor references 必须来自 Librarian（hybrid），不再直连 BM25。"""
    def fake_search(query, top_k=5):
        return [{"title": "定制检索资料", "type": "paper", "url": "https://example.com/x",
                 "snippet": "探针内容"}]
    monkeypatch.setattr(librarian, "search_documents", fake_search)
    events = _events(session, "某个语义化问题")
    refs = next(e["references"] for e in events if e["type"] == "references")
    assert refs[0]["title"] == "定制检索资料"


def test_references_event_emitted_in_mock_mode(client, session):
    events = _events(session, "请讲一下 DDPM 的反向去噪过程")
    kinds = [e["type"] for e in events]
    assert "references" in kinds
    refs = next(e["references"] for e in events if e["type"] == "references")
    assert refs
    for ref in refs:
        assert ref["title"] and ref["url"]
        assert ref["type"] in ("paper", "article", "video", "course", "tool")


def test_references_before_done(client, session):
    events = _events(session, "Stable Diffusion 为什么在潜空间扩散")
    kinds = [e["type"] for e in events]
    assert kinds.index("references") < kinds.index("done")


def test_references_are_topically_relevant(client, session):
    events = _events(session, "LoRA 低秩适配怎么微调")
    refs = next(e["references"] for e in events if e["type"] == "references")
    assert any("LoRA" in r["title"] for r in refs)


def test_answer_mentions_retrieved_topic(client, session):
    events = _events(session, "请讲一下 DDPM 前向加噪")
    text = "".join(e.get("delta", "") for e in events if e["type"] == "token")
    assert text.strip()


def test_struggle_recorded_to_memory(client, session):
    _events(session, "不理解 score 函数是什么", task_id=None)
    rows = store.recall(session, kind="progress")
    assert rows and "score" in rows[0]["content"]


def test_professor_sse_endpoint_references(client, sse, session):
    events = sse(
        "/api/professor/chat",
        {"session_id": session, "message": "DDIM 为什么能加速采样"},
    )
    kinds = [e["event"] for e in events]
    assert "references" in kinds
    payload = next(e["payload"] for e in events if e["event"] == "references")
    assert payload["references"]
