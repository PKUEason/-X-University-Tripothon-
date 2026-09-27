"""HTTP + SSE 路由。SSE 事件规范见 README「接口契约」。"""
import json

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool

from app.agents import lab_mentor, librarian, orchestrator, professor, scholar
from app.api.schemas import (
    ClarifyRequest,
    LabRequest,
    MemoryRememberRequest,
    ProgressRequest,
    ProfessorChatRequest,
    QuestAdvanceRequest,
    RetrieveRequest,
    RoadmapRequest,
    SessionCreate,
)
from app.memory.store import store

router = APIRouter()


def _sse(generator):
    """把同步的 Agent 事件生成器包成 SSE 响应（阻塞调用放到线程池）。"""

    async def event_generator():
        async for event in iterate_in_threadpool(generator):
            yield {"event": event["type"], "data": json.dumps(event, ensure_ascii=False)}

    return EventSourceResponse(event_generator())


def _require_session(session_id: str):
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"session 不存在：{session_id}")
    return session


# ---------------- 会话 ----------------
@router.post("/session/create")
def create_session(body: SessionCreate):
    sid = store.create_session(goal=body.goal, nickname=body.nickname)
    return {"session_id": sid, "goal": body.goal, "nickname": body.nickname}


@router.get("/session/{session_id}")
def get_session(session_id: str):
    session = _require_session(session_id)
    session.pop("state", None)
    return {
        "session": session,
        "state": store.get_state(session_id),
        "roadmap": store.get_roadmap(session_id),
        "messages": store.list_messages(session_id, limit=100),
    }


@router.post("/session/{session_id}/progress")
def update_progress(session_id: str, body: ProgressRequest):
    _require_session(session_id)
    ok = store.set_task_status(session_id, body.task_id, body.status)
    if not ok:
        raise HTTPException(status_code=404, detail=f"任务不存在：{body.task_id}")
    return {"ok": True, "task_id": body.task_id, "status": body.status}


# ---------------- Memory ----------------
@router.get("/memory")
def recall_memory(session_id: str, kind: str | None = None, key: str | None = None):
    _require_session(session_id)
    return {"memories": store.recall(session_id, kind=kind, key=key)}


@router.post("/memory/remember")
def remember_memory(body: MemoryRememberRequest):
    _require_session(body.session_id)
    store.remember(body.session_id, body.kind, body.key, body.content)
    return {"ok": True}


# ---------------- Scholar Agent ----------------
@router.post("/scholar/clarify")
def scholar_clarify(body: ClarifyRequest):
    _require_session(body.session_id)
    return _sse(scholar.stream_clarify(body.session_id, body.message))


@router.post("/scholar/roadmap")
def scholar_roadmap(body: RoadmapRequest):
    _require_session(body.session_id)
    return _sse(scholar.generate_roadmap(body.session_id))


# ---------------- Library ----------------
@router.post("/library/retrieve")
def library_retrieve(body: RetrieveRequest):
    _require_session(body.session_id)
    result = librarian.retrieve(body.query, top_k=body.top_k)
    store.add_message(body.session_id, "user", f"[Library 检索] {body.query}", agent="librarian")
    store.add_message(
        body.session_id, "assistant",
        f"[Library 检索结果] 共 {len(result['documents'])} 条资料", agent="librarian",
    )
    return result


# ---------------- Professor ----------------
@router.post("/professor/chat")
def professor_chat(body: ProfessorChatRequest):
    _require_session(body.session_id)
    return _sse(professor.stream_chat(
        body.session_id, body.message, stage_id=body.stage_id, task_id=body.task_id
    ))


# ---------------- Lab ----------------
@router.post("/lab/guidance")
def lab_guidance(body: LabRequest):
    _require_session(body.session_id)
    return lab_mentor.generate_guidance(body.session_id, body.stage_id, body.task_id)


# ---------------- Quest 编排（多 Agent） ----------------
@router.get("/quest/{session_id}")
def quest_status(session_id: str):
    result = orchestrator.get_quest(session_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/quest/advance")
def quest_advance(body: QuestAdvanceRequest):
    _require_session(body.session_id)
    return _sse(orchestrator.advance(body.session_id, message=body.message))
