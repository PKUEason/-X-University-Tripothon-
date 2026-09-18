"""Lab Mentor：在 Research Lab 给出结构化实践指导（JSON）。Phase 1 可用，Phase 2 接代码执行工具。"""
import logging
from typing import Optional

from app.agents.llm import llm
from app.config import settings
from app.core import prompts
from app.core.guard import public_error_message
from app.memory.store import store
from app.mock_data import golden_path as mock

log = logging.getLogger("lab")


def _current_task(roadmap: Optional[dict], task_id: Optional[str]):
    if not roadmap:
        return None
    for stage in roadmap.get("stages", []):
        for task in stage.get("tasks", []):
            if task.get("id") == task_id:
                return task
    return None


def generate_guidance(
    session_id: str,
    stage_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> dict:
    session = store.get_session(session_id)
    if session is None:
        return {"error": "session 不存在"}

    roadmap = store.get_roadmap(session_id)
    task = _current_task(roadmap, task_id)
    task_title = task.get("title") if task else None
    task_desc = task.get("description") if task else None

    result = None
    degraded_reason: Optional[str] = None

    if not settings.mock_mode:
        context = prompts.build_context_block(session.get("goal"), roadmap, stage_id, task_id)
        user_msg = (
            f"{context}\n\n当前实验任务：{task_title or '（未指定，按总目标给出实践方案）'}\n"
            f"任务描述：{task_desc or '无'}\n请输出实践指导 JSON。"
        )
        messages = [
            {"role": "system", "content": prompts.LAB_SYSTEM},
            {"role": "user", "content": user_msg},
        ]
        try:
            data = llm.chat_json(messages, temperature=0.4, max_tokens=2500, retries=1)
            required = ("overview", "steps", "deliverables", "pitfalls", "tools")
            if all(k in data for k in required):
                result = data
            else:
                raise RuntimeError("Lab JSON 缺少必需字段")
        except Exception as exc:
            log.warning("lab guidance 生成失败：%s", exc)
            degraded_reason = public_error_message(exc)
            if not settings.fallback_to_mock:
                return {"error": f"Lab 指导生成失败：{public_error_message(exc)}"}

    if result is None:
        result = mock.lab_guidance(task_title)

    store.add_message(
        session_id,
        "assistant",
        f"【Lab 实践指导】{result.get('overview', '')}",
        agent="lab",
        task_id=task_id,
    )
    if degraded_reason:
        result["degraded"] = True
        result["degraded_reason"] = degraded_reason
    return result
