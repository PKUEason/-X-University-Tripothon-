"""HTTP + SSE 路由。SSE 事件规范见 README「接口契约」。"""
import json
import threading
from contextlib import contextmanager

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
    SessionRestore,
)
from app.memory.store import store
from app.memory.artifacts import save_artifact

router = APIRouter()
# Single-process local server: deletion must not race an Agent writing its result.
_activity_lock = threading.Lock()
_active_sessions: dict[str, int] = {}

# /api/memory 不暴露的内部 key：artifact 产物、project_card、request 幂等缓存。
# 这些是 Agent 间协作的内部实现，前端应通过 /api/quest 或专用端点读取，不应直接看到原始 JSON。
_INTERNAL_MEMORY_KEYS = frozenset({"library_result", "professor_result", "lab_result", "project_card"})


def _is_internal_memory_key(key: str) -> bool:
    return key in _INTERNAL_MEMORY_KEYS or key.startswith("request:")


@contextmanager
def _using_session(session_id: str):
    with _activity_lock:
        _require_session(session_id)
        _active_sessions[session_id] = _active_sessions.get(session_id, 0) + 1
    try:
        yield
    finally:
        with _activity_lock:
            _active_sessions[session_id] -= 1
            if not _active_sessions[session_id]:
                del _active_sessions[session_id]


def _sse(generator, session_id):
    """把同步的 Agent 事件生成器包成 SSE 响应（阻塞调用放到线程池）。"""

    async def event_generator():
        try:
            with _using_session(session_id):
                try:
                    async for event in iterate_in_threadpool(generator):
                        yield {"event": event["type"], "data": json.dumps(event, ensure_ascii=False)}
                finally:
                    generator.close()
        except HTTPException as error:
            yield {"event": "error", "data": json.dumps({"type": "error", "message": error.detail}, ensure_ascii=False)}

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


@router.post("/session/restore")
def restore_session(body: SessionRestore):
    if body.status in ("library", "professor", "lab", "project_ready") and body.roadmap is None:
        raise HTTPException(422, "恢复此阶段需要本地任务路线。")
    sid = store.restore_snapshot(body.model_dump())
    return {"session_id": sid, "restored_from": "browser_snapshot"}


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
    with _using_session(session_id):
        _require_session(session_id)
        ok = store.set_task_status(session_id, body.task_id, body.status)
        if not ok:
            raise HTTPException(status_code=404, detail=f"任务不存在：{body.task_id}")
        return {"ok": True, "task_id": body.task_id, "status": body.status}


# ---------------- Memory ----------------
@router.get("/memory")
def recall_memory(session_id: str, kind: str | None = None, key: str | None = None):
    _require_session(session_id)
    memories = store.recall(session_id, kind=kind, key=key)
    # 过滤内部实现细节（artifact / project_card / request 缓存），只暴露用户级记忆
    memories = [m for m in memories if not _is_internal_memory_key(m.get("key", ""))]
    return {"memories": memories}


@router.post("/memory/remember")
def remember_memory(body: MemoryRememberRequest):
    with _using_session(body.session_id):
        _require_session(body.session_id)
        store.remember(body.session_id, body.kind, body.key, body.content)
        return {"ok": True}


# ---------------- Scholar Agent ----------------
@router.post("/scholar/clarify")
def scholar_clarify(body: ClarifyRequest):
    _require_session(body.session_id)
    return _sse(scholar.stream_clarify(body.session_id, body.message), body.session_id)


@router.post("/scholar/roadmap")
def scholar_roadmap(body: RoadmapRequest):
    _require_session(body.session_id)
    return _sse(scholar.generate_roadmap(body.session_id), body.session_id)


# ---------------- Library ----------------
@router.post("/library/retrieve")
def library_retrieve(body: RetrieveRequest):
    with _using_session(body.session_id):
        _require_session(body.session_id)
        query = body.query.strip() or librarian.project_query(body.session_id)
        result = librarian.retrieve(query, top_k=body.top_k, arxiv_query=body.arxiv_query)
        save_artifact(body.session_id, "library_result", result)
        store.add_message(body.session_id, "user", f"[Library 检索] {query}", agent="librarian")
        store.add_message(
            body.session_id, "assistant",
            f"[Library 检索结果] 共 {len(result['results'])} 条资料", agent="librarian",
        )
        return result


# ---------------- Professor ----------------
@router.post("/professor/chat")
def professor_chat(body: ProfessorChatRequest):
    _require_session(body.session_id)
    def events():
        text, references, fallback, failed = "", [], False, False
        for event in professor.stream_chat(
            body.session_id, body.message, stage_id=body.stage_id, task_id=body.task_id
        ):
            if event["type"] == "fallback":
                fallback, text = True, ""
            if event["type"] == "token":
                text += event["delta"]
            if event["type"] == "references":
                references = event["references"]
            if event["type"] == "error":
                failed = True
            yield event
        if not failed and text.strip():
            save_artifact(body.session_id, "professor_result", {
                "question": body.message, "answer": text, "references": references,
                "task_id": body.task_id, "degraded": fallback,
            })
    return _sse(events(), body.session_id)


# ---------------- Lab ----------------
@router.post("/lab/guidance")
def lab_guidance(body: LabRequest):
    with _using_session(body.session_id):
        _require_session(body.session_id)
        result = lab_mentor.generate_guidance(body.session_id, body.stage_id, body.task_id)
        if "error" in result:
            raise HTTPException(502, result["error"])
        return result


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
    return _sse(orchestrator.advance(body.session_id, message=body.message, request_id=body.request_id, expected_status=body.expected_status), body.session_id)


@router.delete("/session/{session_id}")
def delete_session(session_id: str):
    with _activity_lock:
        if _active_sessions.get(session_id):
            raise HTTPException(409, "该项目正在处理请求，请等回复完成后再删除。")
        store.delete_session(session_id)
        orchestrator.cleanup_session_locks(session_id)
    return {"ok": True}
