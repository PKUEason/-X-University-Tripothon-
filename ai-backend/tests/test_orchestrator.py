# -*- coding: utf-8 -*-
"""多 Agent 编排：Quest 状态机走查 + Project Card 契约。"""

from app.agents import orchestrator
from app.memory.store import store


def _advance(sid, message=None):
    return list(orchestrator.advance(sid, message=message))


def test_initial_quest_status():
    sid = store.create_session(goal="Quest 初始")
    quest = orchestrator.get_quest(sid)
    assert quest["status"] == "created"
    assert quest["project"] is None


def test_advance_without_message_errors():
    sid = store.create_session(goal="无消息")
    events = _advance(sid)
    assert events[0]["type"] == "error"


def test_full_quest_walkthrough():
    sid = store.create_session(goal="两周跑通扩散模型文生图 Demo")

    # 第一轮澄清：mock ready=false，仍在 clarifying
    events = _advance(sid, message="我想学习扩散模型文生图")
    kinds = [e["type"] for e in events]
    assert "quest" in kinds and "token" in kinds
    assert orchestrator.get_quest(sid)["status"] == "clarifying"

    # 第二轮澄清：ready=true → quest_ready
    events = _advance(sid, message="我有 PyTorch 基础，每天 3 小时")
    assert orchestrator.get_quest(sid)["status"] == "quest_ready"
    quest_events = [e for e in events if e["type"] == "quest"]
    assert quest_events[-1]["status"] == "quest_ready"

    # 生成路线图 → library
    events = _advance(sid)
    assert any(e["type"] == "roadmap" for e in events)
    assert orchestrator.get_quest(sid)["status"] == "library"

    # Library 检索 → professor
    events = _advance(sid)
    assert any(e["type"] == "references" for e in events)
    assert orchestrator.get_quest(sid)["status"] == "professor"

    # Professor → lab
    events = _advance(sid)
    assert orchestrator.get_quest(sid)["status"] == "lab"

    # Lab：实践指导 + Project Card → project_ready
    events = _advance(sid)
    assert any(e["type"] == "lab_guidance" for e in events)
    project_events = [e for e in events if e["type"] == "project"]
    assert project_events
    quest = orchestrator.get_quest(sid)
    assert quest["status"] == "project_ready"
    assert quest["project"] is not None


def test_project_card_contract():
    sid = store.create_session(goal="Project 契约")
    card = orchestrator.generate_project_card(sid)
    for key in ("title", "summary", "deliverables", "tech_stack", "next_steps"):
        assert key in card
    assert card["title"] and card["deliverables"]
    # 已写入长期记忆
    row = store.recall(sid, kind="note", key="project_card")
    assert row


def test_project_ready_is_idempotent():
    sid = store.create_session(goal="幂等测试")
    store.update_state(sid, quest_status="project_ready")
    events = _advance(sid)
    assert events[-1]["type"] == "quest"
    assert events[-1]["status"] == "project_ready"


def test_quest_completed_tasks_counting():
    sid = store.create_session(goal="任务计数")
    _advance(sid, message="我想学习扩散模型文生图")
    _advance(sid, message="有基础，每天 3 小时")
    _advance(sid)  # roadmap
    quest = orchestrator.get_quest(sid)
    assert quest["total_tasks"] >= 4
    assert isinstance(quest["completed_tasks"], list)


# ---------- SSE 端点 ----------
def test_quest_endpoints(client, session):
    r = client.get(f"/api/quest/{session}")
    assert r.status_code == 200
    assert r.json()["status"] == "created"

    r = client.post(
        "/api/quest/advance",
        json={"session_id": session, "message": "我想学习扩散模型文生图"},
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


def test_quest_404(client):
    assert client.get("/api/quest/nope").status_code == 404
