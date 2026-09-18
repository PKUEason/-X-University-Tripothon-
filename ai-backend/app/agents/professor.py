"""AI Professor：在 Professor Office 围绕当前任务授课答疑（流式）。"""
import logging
from typing import Iterator, Optional

from app.agents.llm import llm
from app.config import settings
from app.core import prompts
from app.core.guard import public_error_message
from app.memory.store import store
from app.mock_data import golden_path as mock

log = logging.getLogger("professor")


def _chunk(text: str, size: int = 12) -> Iterator[str]:
    yield from (text[i : i + 12] for i in range(0, len(text), size))


def _current_task(roadmap: Optional[dict], task_id: Optional[str]):
    if not roadmap:
        return None, None
    for stage in roadmap.get("stages", []):
        for task in stage.get("tasks", []):
            if task.get("id") == task_id:
                return task, stage
    return None, None


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

    if settings.mock_mode:
        answer = mock.professor_answer(message, task_title)
        for piece in _chunk(answer):
            yield {"type": "token", "delta": piece}
        store.add_message(session_id, "assistant", answer, agent="professor", task_id=task_id)
        yield {"type": "done"}
        return

    context = prompts.build_context_block(session.get("goal"), roadmap, stage_id, task_id)
    task_hint = f"当前正在讲解的任务：{task_title}。" if task_title else "学生尚未指定具体任务。"
    system_msg = prompts.PROFESSOR_SYSTEM + "\n\n[学习背景]\n" + context + "\n" + task_hint

    history = store.list_messages(session_id, agent="professor", limit=10)
    messages = [{"role": "system", "content": system_msg}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]

    answer = ""
    try:
        for delta in llm.stream_text(messages, temperature=0.5, max_tokens=1500):
            answer += delta
            yield {"type": "token", "delta": delta}
    except Exception as exc:
        log.warning("professor LLM 调用失败：%s", exc)
        if not settings.fallback_to_mock:
            store.add_message(session_id, "assistant", answer, agent="professor", task_id=task_id)
            yield {"type": "error", "message": f"AI Professor 暂不可用：{public_error_message(exc)}"}
            yield {"type": "done"}
            return
        yield {"type": "fallback", "reason": f"DeepSeek 调用失败，已切换演示模式：{public_error_message(exc)}"}
        answer = mock.professor_answer(message, task_title)
        for piece in _chunk(answer):
            yield {"type": "token", "delta": piece}

    store.add_message(session_id, "assistant", answer.strip(), agent="professor", task_id=task_id)
    yield {"type": "done"}
