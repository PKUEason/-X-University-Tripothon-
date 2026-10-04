# -*- coding: utf-8 -*-
"""多 Agent 编排器：Quest 状态机 + Project Card 生成。

Quest 状态机（与 Demo 空间流转一一对应）：
    created → clarifying → quest_ready → library → professor → lab → project_ready

advance(session_id) 每次推进一步，内部委托对应 Agent（scholar / librarian /
lab_mentor）并透传它们的 SSE 事件；空间切换时插入 quest 事件，前端据此驱动
3D 场景移动。Lab 完成后自动生成 Project Card，作为整条 Quest 的最终成果。
"""
import json
import logging
import threading
from typing import Any, Iterator, Optional

from app.agents import lab_mentor, librarian, scholar
from app.agents.llm import llm
from app.config import settings
from app.core import prompts
from app.core.guard import public_error_message
from app.memory.store import store
from app.memory.artifacts import read_artifact, save_artifact, context as artifact_context

log = logging.getLogger("orchestrator")

QUEST_STATUSES = (
    "created", "clarifying", "quest_ready", "library", "professor", "lab", "project_ready",
)

_MOCK_PROJECT = {
    "title": "扩散模型文生图 Demo：从噪声到图像",
    "summary": (
        "基于 Stable Diffusion 与 Diffusers，实现了文本提示驱动的文生图管线，"
        "完成环境搭建、采样调度对比与首批图像生成，并支持 LoRA 风格扩展。"
    ),
    "deliverables": [
        "可运行的文生图 Demo（Diffusers Pipeline）",
        "采样器对比实验记录（DDIM / DPM-Solver 步数与耗时）",
        "项目说明与复现文档",
    ],
    "tech_stack": ["Python", "PyTorch", "HuggingFace Diffusers", "Stable Diffusion", "LoRA"],
    "next_steps": [
        "用 LoRA 微调专属风格并评估 CLIP Score",
        "接入 ControlNet 实现构图控制",
        "把 Demo 封装为 Web/3D 场景内可交互应用",
    ],
}


def _quest_event(status: str, message: str) -> dict[str, Any]:
    return {"type": "quest", "status": status, "message": message}


def _all_tasks(roadmap: Optional[dict]) -> list[dict]:
    if not roadmap:
        return []
    return [t for s in roadmap.get("stages", []) for t in s.get("tasks", [])]


def _first_task_id(roadmap: Optional[dict], space: str) -> Optional[str]:
    for stage in roadmap.get("stages", []) if roadmap else []:
        if stage.get("space") == space:
            for task in stage.get("tasks", []):
                return task.get("id")
    return None


def get_quest(session_id: str) -> dict[str, Any]:
    session = store.get_session(session_id)
    if session is None:
        return {"error": "session 不存在"}
    state = store.get_state(session_id)
    roadmap = store.get_roadmap(session_id)
    tasks = _all_tasks(roadmap)
    done_ids = [t.get("id") for t in tasks if t.get("status") == "done"]

    project = None
    rows = store.recall(session_id, kind="note", key="project_card")
    # recall 同时返回会话记忆与全局记忆（全局在前），project_card 必须只取当前会话的，
    # 否则全局记忆会被误当成项目卡。
    row = next((r for r in rows if r.get("session_id") == session_id), None)
    if row:
        try:
            project = json.loads(row["content"])
        except (ValueError, TypeError):
            project = None

    return {
        "session_id": session_id,
        "status": state.get("quest_status", "created"),
        "goal": session.get("goal"),
        "total_tasks": len(tasks),
        "completed_tasks": done_ids,
        "project": project,
        "library_result": read_artifact(session_id, "library_result"),
        "professor_result": read_artifact(session_id, "professor_result"),
        "lab_result": read_artifact(session_id, "lab_result"),
        "fallbacks": state.get("fallbacks", []),
    }


def generate_project_card(session_id: str) -> dict[str, Any]:
    """Lab 完成后总结 Project Card（LLM；失败/无 key 用 mock）。"""
    session = store.get_session(session_id) or {}
    roadmap = store.get_roadmap(session_id)
    goal = session.get("goal", "")

    if settings.mock_mode:
        card = dict(_MOCK_PROJECT)
        card["degraded"] = True
        card["degraded_reason"] = "MOCK_MODE"
    else:
        try:
            payload = json.dumps(
                {"goal": goal, "stage_results": artifact_context(session_id), "roadmap": roadmap}, ensure_ascii=False
            )[:18000]
            data = llm.chat_json(
                [
                    {"role": "system", "content": prompts.PROJECT_CARD_SYSTEM},
                    {"role": "user", "content": payload},
                ],
                temperature=0.3,
                max_tokens=1200,
            )
            card = {
                "title": str(data.get("title") or "X University 项目成果"),
                "summary": str(data.get("summary") or ""),
                "deliverables": [str(x) for x in data.get("deliverables", [])][:6],
                "tech_stack": [str(x) for x in data.get("tech_stack", [])][:8],
                "next_steps": [str(x) for x in data.get("next_steps", [])][:4],
            }
            if not card["deliverables"]:
                raise ValueError("Project Card 缺少产出物")
        except Exception as exc:
            log.warning("Project Card 生成失败，使用 mock：%s", exc)
            card = dict(_MOCK_PROJECT)
            card["degraded"] = True
            card["degraded_reason"] = public_error_message(exc)

    card["artifact_type"] = "project_plan"
    store.remember(session_id, "note", "project_card", json.dumps(card, ensure_ascii=False))
    return card


def _advance(session_id: str, message: Optional[str] = None) -> Iterator[dict]:
    """推进 Quest 一个阶段。事件透传 + quest 状态切换事件。"""
    session = store.get_session(session_id)
    if session is None:
        yield {"type": "error", "message": "session 不存在"}
        return

    state = store.get_state(session_id)
    status = state.get("quest_status", "created")

    # ---- created / clarifying：Scholar 目标澄清 ----
    if status in ("created", "clarifying") or (status == "quest_ready" and message):
        if not message:
            yield {"type": "error", "message": "请先告诉 Scholar Agent 你的学习/研究目标。"}
            return
        store.update_state(session_id, quest_status="clarifying")
        yield _quest_event("clarifying", "Scholar Agent 正在与你确认目标…")
        ready = False
        for event in scholar.stream_clarify(session_id, message):
            if event["type"] == "ready":
                ready = bool(event.get("ready"))
            yield event
            if event["type"] == "error":
                return
        new_status = "quest_ready" if ready else "clarifying"
        store.update_state(session_id, quest_status=new_status)
        if ready:
            yield _quest_event("quest_ready", "目标已确认，下一步将生成专属 Quest 路线。")
        return

    # ---- quest_ready：生成路线图 ----
    if status == "quest_ready":
        yield _quest_event("quest_ready", "Scholar Agent 正在生成 Quest 路线图…")
        got_roadmap = False
        for event in scholar.generate_roadmap(session_id):
            got_roadmap = got_roadmap or event["type"] == "roadmap"
            yield event
            if event["type"] == "error":
                return
        if not got_roadmap:
            yield {"type": "error", "message": "未收到路线图，阶段未推进"}
            return
        store.update_state(session_id, quest_status="library")
        yield _quest_event("library", "Quest 已生成，欢迎进入 Library 图书馆！")
        return

    # ---- library：基于目标检索资料 ----
    if status == "library":
        yield _quest_event("library", "图书馆正在为你调取相关资料…")
        query = librarian.project_query(session_id)
        result = librarian.retrieve(query, top_k=5)
        save_artifact(session_id, "library_result", result)
        yield {"type": "references", "references": [
            {"title": d["title"], "type": d.get("type", "article"), "url": d.get("url", "")}
            for d in result["results"] if d.get("url")
        ]}
        store.update_state(session_id, quest_status="professor")
        yield _quest_event("professor", "资料已就绪，前往 Professor Office 与 AI Professor 研讨。")
        return

    # ---- professor：研讨完成，进入 Lab ----
    if status == "professor":
        store.update_state(session_id, quest_status="lab")
        yield _quest_event("lab", "理解已检验，进入 X Lab 开始动手实践。")
        return

    # ---- lab：实践指导 + Project Card ----
    if status == "lab":
        yield _quest_event("lab", "Lab Mentor 正在生成本任务实践方案…")
        lab_task_id = _first_task_id(store.get_roadmap(session_id), "lab")
        guidance = lab_mentor.generate_guidance(session_id, task_id=lab_task_id)
        if guidance.get("error"):
            yield {"type": "error", "message": guidance["error"]}
            return
        save_artifact(session_id, "lab_result", guidance)
        yield {"type": "lab_guidance", "guidance": guidance}
        if guidance.get("degraded"):
            yield {"type": "fallback", "reason": guidance.get("degraded_reason", "Lab 使用示例方案")}
        project = generate_project_card(session_id)
        if project.get("degraded"):
            yield {"type": "fallback", "reason": project.get("degraded_reason", "成果卡使用示例")}
        store.update_state(session_id, quest_status="project_ready")
        yield {"type": "project", "project": project}
        yield _quest_event("project_ready", "恭喜！你的 Project / Research Result 已生成。")
        return

    # ---- project_ready：已完成 ----
    yield _quest_event("project_ready", "Quest 已完成，可查看并导出 Project Card。")


# Single-process local demo: serialize each session and replay successful request IDs.
# A multi-worker deployment must replace this with a database/distributed lock.
_locks = {}
_locks_guard = threading.Lock()


def cleanup_session_locks(session_id: str) -> None:
    """会话删除时回收其锁，避免 _locks 只增不减。"""
    with _locks_guard:
        _locks.pop(session_id, None)


def advance(session_id, message=None, request_id=None, expected_status=None):
    with _locks_guard:
        lock = _locks.setdefault(session_id, threading.Lock())
    if not lock.acquire(blocking=False):
        yield {"type": "error", "message": "此会话仍在处理上一请求，请稍后恢复进度"}
        return
    try:
        if request_id:
            cached = read_artifact(session_id, "request:" + request_id)
            if cached is not None:
                yield from cached
                return
        current = get_quest(session_id).get("status")
        if expected_status and current != expected_status:
            yield {"type": "error", "message": "任务阶段已变化，请恢复进度后继续"}
            return
        events = []
        failed = False
        for event in _advance(session_id, message):
            events.append(event)
            failed = failed or event["type"] == "error"
            if event["type"] == "fallback":
                state = store.get_state(session_id)
                reasons = state.get("fallbacks", [])
                reason = event.get("reason", "演示数据")
                store.update_state(session_id, fallbacks=list(dict.fromkeys(reasons + [reason]))[-12:])
            yield event
        if request_id and not failed:
            save_artifact(session_id, "request:" + request_id, events)
            store.cleanup_request_cache(session_id, keep=10)
    finally:
        lock.release()
