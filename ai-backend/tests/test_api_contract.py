"""接口契约测试：8 个端点的状态码、SSE 事件序列、JSON 结构。

全部跑在 MOCK_MODE 下，不联网、不花钱、确定性输出——
用来保证「前端按契约渲染 3D 场景」这件事在任何一次改动后都不会被悄悄破坏。
"""
import pytest

from app.api.schemas import LabRequest, Roadmap

SSE_ENDPOINTS_REQUIRING_SESSION = [
    ("/api/scholar/clarify", {"session_id": "ghost", "message": "hi"}),
    ("/api/scholar/roadmap", {"session_id": "ghost"}),
    ("/api/professor/chat", {"session_id": "ghost", "message": "hi"}),
]
JSON_ENDPOINTS_REQUIRING_SESSION = [
    ("/api/library/retrieve", {"session_id": "ghost", "query": "ddpm"}),
    ("/api/lab/guidance", {"session_id": "ghost"}),
]


# ---------------- 健康检查 ----------------
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mock_mode"] is True
    assert "version" in body and "model" in body


# ---------------- 会话 ----------------
def test_create_session(client):
    r = client.post("/api/session/create", json={"goal": "学扩散模型", "nickname": "Eason"})
    assert r.status_code == 200
    body = r.json()
    assert body["goal"] == "学扩散模型"
    assert body["nickname"] == "Eason"
    assert len(body["session_id"]) == 12


def test_create_session_without_body_fields(client):
    """goal / nickname 都是可选的，空请求体不能 500。"""
    r = client.post("/api/session/create", json={})
    assert r.status_code == 200


def test_get_session_snapshot(client, session):
    r = client.get(f"/api/session/{session}")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"session", "state", "roadmap", "messages"}
    assert body["roadmap"] is None
    assert body["messages"] == []
    assert "state" not in body["session"]      # 内部字段不对外暴露


@pytest.mark.parametrize("path,payload", SSE_ENDPOINTS_REQUIRING_SESSION + JSON_ENDPOINTS_REQUIRING_SESSION)
def test_unknown_session_returns_404(client, path, payload):
    r = client.post(path, json=payload)
    assert r.status_code == 404
    assert "session 不存在" in r.json()["detail"]


# ---------------- Scholar：澄清 ----------------
def test_clarify_sse_event_sequence(sse, session):
    events = sse("/api/scholar/clarify",
                 {"session_id": session, "message": "我有 PyTorch 基础，每天 3 小时"})
    kinds = [e["event"] for e in events]
    assert kinds[-1] == "done"
    assert "token" in kinds
    assert "ready" in kinds
    assert kinds.index("ready") < kinds.index("done")
    assert all(isinstance(e["payload"]["delta"], str) for e in events if e["event"] == "token")
    assert events[-1]["payload"]["type"] == "done"


def test_clarify_becomes_ready_after_followup(sse, session):
    first = sse("/api/scholar/clarify", {"session_id": session, "message": "我想学扩散模型"})
    assert first[-2]["payload"]["ready"] is False

    second = sse("/api/scholar/clarify", {"session_id": session, "message": "有 PyTorch 基础，每天 3 小时"})
    assert second[-2]["payload"]["ready"] is True


def test_clarify_persists_messages(client, sse, session):
    sse("/api/scholar/clarify", {"session_id": session, "message": "你好"})
    snap = client.get(f"/api/session/{session}").json()
    roles = [m["role"] for m in snap["messages"]]
    assert roles == ["user", "assistant"]
    assert all(m["agent"] == "scholar" for m in snap["messages"])
    assert snap["state"]["clarify_ready"] is False


# ---------------- Scholar：路线图 ----------------
def test_roadmap_sse_and_schema(sse, session):
    events = sse("/api/scholar/roadmap", {"session_id": session})
    kinds = [e["event"] for e in events]
    assert "status" in kinds
    assert kinds[-1] == "done"
    assert kinds.count("roadmap") == 1

    payload = next(e["payload"] for e in events if e["event"] == "roadmap")
    rm = Roadmap.model_validate(payload["roadmap"])     # 必须过契约模型

    assert len(rm.stages) == 4
    assert [s.space for s in rm.stages] == ["gate", "library", "professor_office", "lab"]
    assert sum(len(s.tasks) for s in rm.stages) >= 5
    assert rm.final_outcome
    assert rm.stages[0].tasks[0].space == "gate"


def test_roadmap_persisted_and_idempotent(client, sse, session):
    sse("/api/scholar/roadmap", {"session_id": session})
    sse("/api/scholar/roadmap", {"session_id": session})
    snap = client.get(f"/api/session/{session}").json()
    assert snap["roadmap"]["title"]
    assert len(snap["roadmap"]["stages"]) == 4


# ---------------- Library ----------------
def test_library_retrieve(client, session):
    r = client.post("/api/library/retrieve",
                    json={"session_id": session, "query": "DDPM 扩散模型论文", "top_k": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "curated-v1"
    assert 0 < len(body["documents"]) <= 3
    for doc in body["documents"]:
        assert set(doc) == {"title", "type", "url", "snippet"}
        assert doc["title"]


def test_library_top_k_respected(client, session):
    r = client.post("/api/library/retrieve", json={"session_id": session, "query": "扩散", "top_k": 2})
    assert len(r.json()["documents"]) <= 2


def test_library_writes_to_transcript(client, session):
    client.post("/api/library/retrieve", json={"session_id": session, "query": "DDPM"})
    msgs = client.get(f"/api/session/{session}").json()["messages"]
    assert len(msgs) == 2
    assert all(m["agent"] == "librarian" for m in msgs)


# ---------------- Professor ----------------
def test_professor_sse(sse, session):
    events = sse("/api/professor/chat",
                 {"session_id": session, "message": "请讲一下反向扩散过程",
                  "stage_id": "stage-3", "task_id": "t-3-1"})
    kinds = [e["event"] for e in events]
    assert kinds[-1] == "done"
    assert kinds.count("token") >= 1
    text = "".join(e["payload"]["delta"] for e in events if e["event"] == "token")
    assert text.strip()


def test_professor_carries_task_context(client, sse, session):
    """带 task_id 提问时，回答里应出现该任务标题（mock 会拼进文案）。"""
    sse("/api/scholar/roadmap", {"session_id": session})
    events = sse("/api/professor/chat",
                 {"session_id": session, "message": "讲讲这个", "task_id": "t-3-1"})
    text = "".join(e["payload"]["delta"] for e in events if e["event"] == "token")
    assert "研讨" in text or "任务" in text


# ---------------- Lab ----------------
def test_lab_guidance_schema(client, session):
    r = client.post("/api/lab/guidance", json={"session_id": session, "task_id": "t-4-1"})
    assert r.status_code == 200
    body = r.json()
    for key in ("overview", "steps", "deliverables", "pitfalls", "tools"):
        assert key in body, f"缺少字段 {key}"
    assert len(body["steps"]) >= 3
    assert all({"title", "detail"} <= set(s) for s in body["steps"])
    assert body["deliverables"] and body["tools"]


def test_lab_request_model_accepts_all_optional(client, session):
    """stage_id / task_id 都是可选的，只传 session 也不能炸。"""
    body = LabRequest(session_id=session)
    assert body.stage_id is None
    assert client.post("/api/lab/guidance", json={"session_id": session}).status_code == 200


# ---------------- 进度 ----------------
def test_progress_updates_and_persists(client, sse, session):
    sse("/api/scholar/roadmap", {"session_id": session})
    r = client.post(f"/api/session/{session}/progress", json={"task_id": "t-1-1", "status": "done"})
    assert r.status_code == 200 and r.json()["ok"] is True

    snap = client.get(f"/api/session/{session}").json()
    task = next(t for s in snap["roadmap"]["stages"] for t in s["tasks"] if t["id"] == "t-1-1")
    assert task["status"] == "done"


def test_progress_rejects_unknown_task(client, sse, session):
    sse("/api/scholar/roadmap", {"session_id": session})
    r = client.post(f"/api/session/{session}/progress", json={"task_id": "t-9-9", "status": "done"})
    assert r.status_code == 404


def test_progress_rejects_invalid_status(client, session):
    r = client.post(f"/api/session/{session}/progress", json={"task_id": "t-1-1", "status": "finished"})
    assert r.status_code == 422
