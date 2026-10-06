"""AI Professor：在 Professor Office 围绕当前任务授课答疑（流式）。

第二阶段增强：
- 答疑前通过 Librarian 的 Hybrid RAG（BM25+向量）检索相关资料，snippet 注入 system prompt，
  回答有据可依；
- 回答正文之后发 references 事件（可点击的资料来源，mock 模式同样提供）；
- 注入学生画像（Memory），历史对话自动摘要，答疑卡点写入长期记忆。
"""
import logging
from typing import Iterator, Optional

from app.agents import librarian
from app.agents.llm import llm, EmptyResponseError
from app.config import settings
from app.core import prompts
from app.core.guard import public_error_message
from app.memory.memory_service import build_memory_block, messages_with_summary, record_struggle
from app.memory.store import store
from app.memory.artifacts import context as artifact_context
from app.mock_data import golden_path as mock

log = logging.getLogger("professor")

REF_TOP_K = 3


def _chunk(text: str, size: int = 12) -> Iterator[str]:
    yield from (text[i : i + size] for i in range(0, len(text), size))


def _current_task(roadmap: Optional[dict], task_id: Optional[str]):
    if not roadmap:
        return None, None
    for stage in roadmap.get("stages", []):
        for task in stage.get("tasks", []):
            if task.get("id") == task_id:
                return task, stage
    return None, None


def _gather_references(query: str, task_title: Optional[str]) -> tuple[list[dict], list[dict]]:
    """RAG 检索（复用 Librarian 的 hybrid 检索）。
    返回 (references 事件用精简列表, 注入 prompt 用 docs 全文)。"""
    q = f"{task_title} {query}" if task_title else query
    docs = librarian.search_documents(q, top_k=REF_TOP_K)
    refs = [
        {"title": d["title"], "type": d.get("type", "article"), "url": d.get("url", "")}
        for d in docs
        if d.get("url")
    ]
    return refs, docs


def _reference_block(docs: list[dict]) -> str:
    if not docs:
        return "（未检索到直接资料，按通用原理讲解）"
    return "\n".join(f"- 《{d['title']}》：{d['snippet']}" for d in docs)


def stream_chat(
    session_id: str,
    message: str,
    stage_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> Iterator[dict]:
    session = store.get_session(session_id)
    if session is None:
        yield {"type": "error", "message": "session 不存在"}
        return

    roadmap = store.get_roadmap(session_id)
    task, stage = _current_task(roadmap, task_id)
    task_title = task.get("title") if task else None

    store.add_message(session_id, "user", message, agent="professor", task_id=task_id)

    # RAG 检索为纯本地计算、结果确定，mock 与真实模式都使用
    refs, ref_docs = _gather_references((session.get("goal") or "") + " " + message, task_title)

    if settings.mock_mode:
        answer = mock.professor_answer(message, task_title)
        for piece in _chunk(answer):
            yield {"type": "token", "delta": piece}
        store.add_message(session_id, "assistant", answer, agent="professor", task_id=task_id)
        record_struggle(session_id, task_id, message)
        if refs:
            yield {"type": "references", "references": refs}
        yield {"type": "done"}
        return

    context = prompts.build_context_block(session.get("goal"), roadmap, stage_id, task_id)
    context += "\n[此前空间产物]\n" + artifact_context(session_id)
    memory_block = build_memory_block(session_id)
    task_hint = f"当前正在讲解的任务：{task_title}。" if task_title else "学生尚未指定具体任务。"
    system_msg = (
        prompts.PROFESSOR_SYSTEM
        + "\n\n[学习背景]\n" + context
        + "\n" + task_hint
        + ("\n\n" + memory_block if memory_block else "")
        + "\n\n[图书馆检索到的相关资料，请优先据此讲解，不要编造资料外的事实]\n"
        + _reference_block(ref_docs)
    )

    messages = [{"role": "system", "content": system_msg}]
    messages += messages_with_summary(session_id, "professor", recent_limit=8)

    answer = ""
    try:
        for attempt in range(2):
            try:
                for delta in llm.stream_text(messages, temperature=0.5, max_tokens=1500 * (attempt + 1)):
                    answer += delta
                    yield {"type": "token", "delta": delta}
                if not answer.strip():
                    raise EmptyResponseError("模型未返回回答正文，请重试")
                break
            except EmptyResponseError:
                if attempt:
                    raise
                answer = ""
                log.warning("professor 收到空正文，重试一次")
    except Exception as exc:
        log.warning("professor LLM 调用失败：%s", exc)
        if not settings.fallback_to_mock:
            if answer.strip():
                store.add_message(session_id, "assistant", answer, agent="professor", task_id=task_id)
            yield {"type": "error", "message": f"AI Professor 暂不可用：{public_error_message(exc)}"}
            yield {"type": "done"}
            return
        yield {"type": "fallback", "reason": f"DeepSeek 调用失败，已切换演示模式：{public_error_message(exc)}"}
        answer = mock.professor_answer(message, task_title)
        for piece in _chunk(answer):
            yield {"type": "token", "delta": piece}

    store.add_message(session_id, "assistant", answer.strip(), agent="professor", task_id=task_id)
    record_struggle(session_id, task_id, message)
    if refs:
        yield {"type": "references", "references": refs}
    yield {"type": "done"}
