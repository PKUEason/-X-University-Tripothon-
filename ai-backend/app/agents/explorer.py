"""Explorer Agent：3D 校园物品交互与好奇心激发。

学生点击校园里的物品（书、器皿、雕像等）时被唤醒，
结合物品信息 + 玩家项目背景 + 联网检索，生成「大问题」和探索话题，
与玩家进行简短对话，激发探索欲。
"""
import logging
import time
from typing import Any, Iterator, Optional

from app.agents.llm import llm
from app.config import settings
from app.core import prompts
from app.core.guard import public_error_message
from app.memory.store import store
from app.mock_data import golden_path as mock
from app.services import web_search

log = logging.getLogger(__name__)


def _gather_player_context(session_id: str) -> dict[str, Any]:
    """收集玩家身份与项目信息，作为 Agent 的前置上下文。"""
    session = store.get_session(session_id) or {}
    goal = session.get("goal", "")
    nickname = session.get("nickname", "")
    roadmap = store.get_roadmap(session_id)
    state = store.get_state(session_id)
    messages = store.list_messages(session_id, agent="scholar", limit=6)
    dialogue = "\n".join(f"{m['role']}: {m['content']}" for m in messages)

    # 当前阶段
    current_stage = ""
    if roadmap:
        for stage in roadmap.get("stages", []):
            for task in stage.get("tasks", []):
                if task.get("status") == "in_progress":
                    current_stage = f"{stage.get('name', '')} - {task.get('title', '')}"
                    break
            if current_stage:
                break

    # 玩家画像（从 memory 提取）
    profile_notes = store.recall(session_id, kind="profile")
    profile_text = "\n".join(f"- {n.get('key', '')}: {n.get('content', '')}" for n in profile_notes[:3])

    # 历史物品交互记录
    artifact_history = store.recall(session_id, kind="note")
    artifact_history = [n for n in artifact_history if n.get("key", "").startswith("artifact:")][-3:]
    history_text = "\n".join(f"- 交互过 {n.get('key', '').replace('artifact:', '')}: {n.get('content', '')[:80]}" for n in artifact_history)

    return {
        "goal": goal,
        "nickname": nickname,
        "roadmap_title": roadmap.get("title", "") if roadmap else "",
        "current_stage": current_stage,
        "quest_status": state.get("quest_status", ""),
        "dialogue": dialogue,
        "profile": profile_text,
        "artifact_history": history_text,
    }


def _search_artifact_background(name: str, tag: str, max_results: int = 3) -> str:
    """联网搜索物品相关的背景知识、名人名言、历史故事。"""
    if settings.mock_mode or not settings.web_search_enabled:
        return ""
    query = f"{name} {tag} 历史 故事 名言"
    try:
        results, provider = web_search.search(query, max_results=max_results)
        if provider == "mock" or not results:
            return ""
        lines = []
        for r in results[:max_results]:
            title = (r.get("title") or "").strip()
            content = (r.get("content") or "").strip()[:200]
            if title:
                lines.append(f"- {title}: {content}")
        return "\n".join(lines)
    except Exception as exc:
        log.warning("explorer 物品背景搜索失败：%s", exc)
        return ""


def _build_interact_messages(artifact: dict[str, Any], player: dict[str, Any], background: str) -> list[dict[str, str]]:
    """构建物品交互的 prompt。"""
    artifact_info = (
        f"物品名称：{artifact.get('name', '未知物品')}\n"
        f"物品标签：{artifact.get('tag', '')}\n"
        f"物品类别：{artifact.get('category', '')}\n"
        f"所在空间：{artifact.get('location', '')}\n"
        f"物品描述：{artifact.get('description', '')}"
    )
    player_info = (
        f"学生昵称：{player.get('nickname', '同学')}\n"
        f"学习目标：{player.get('goal', '（未记录）')}\n"
        f"路线图：{player.get('roadmap_title', '（未生成）')}\n"
        f"当前阶段：{player.get('current_stage', '（未知）')}\n"
    )
    if player.get("profile"):
        player_info += f"玩家画像：\n{player['profile']}\n"
    if player.get("artifact_history"):
        player_info += f"历史交互：\n{player['artifact_history']}\n"

    user_content = f"【物品信息】\n{artifact_info}\n\n【学生信息】\n{player_info}"
    if background:
        user_content += f"\n\n【背景资料】\n以下是关于这个物品的联网搜索结果，请参考：\n{background}"

    return [
        {"role": "system", "content": prompts.EXPLORER_INTERACT_SYSTEM},
        {"role": "user", "content": user_content},
    ]


def interact(session_id: str, artifact: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """点击物品时调用：生成好奇心问题/话题，流式输出。

    artifact: {artifact_id, name, tag, category, description, location}
    SSE 事件：status / token / questions / artifact_info / done / error
    """
    session = store.get_session(session_id)
    if session is None:
        yield {"type": "error", "message": "session 不存在"}
        return

    if settings.mock_mode:
        yield {"type": "status", "stage": "探索者精灵正在苏醒…"}
        time.sleep(0.3)
        response = mock.explorer_interact(artifact)
        yield {"type": "artifact_info", "artifact": artifact}
        yield {"type": "token", "delta": response}
        yield {"type": "questions", "questions": mock.explorer_questions(artifact)}
        # 记录交互
        store.remember(session_id, "note", f"artifact:{artifact.get('artifact_id', 'unknown')}",
                       f"交互物品：{artifact.get('name', '')}，标签：{artifact.get('tag', '')}")
        yield {"type": "done"}
        return

    player = _gather_player_context(session_id)

    # 联网搜索物品背景
    yield {"type": "status", "stage": "正在检索物品的故事…"}
    background = _search_artifact_background(
        artifact.get("name", ""), artifact.get("tag", "")
    )

    messages = _build_interact_messages(artifact, player, background)
    yield {"type": "artifact_info", "artifact": artifact}
    yield {"type": "status", "stage": "探索者精灵正在低语…"}

    full_text = ""
    try:
        for delta in llm.stream_text(messages, temperature=0.8, max_tokens=800):
            full_text += delta
            yield {"type": "token", "delta": delta}
    except Exception as exc:
        log.warning("explorer 交互生成失败：%s", exc)
        if not settings.fallback_to_mock:
            yield {"type": "error", "message": f"探索者精灵暂时无法回应：{public_error_message(exc)}"}
            yield {"type": "done"}
            return
        yield {"type": "fallback", "reason": f"已切换演示模式：{public_error_message(exc)}"}
        full_text = mock.explorer_interact(artifact)
        yield {"type": "token", "delta": full_text}

    # 从回复中提取问题（简单的问号分句，后续可优化为结构化输出）
    questions = _extract_questions(full_text)
    if questions:
        yield {"type": "questions", "questions": questions}

    # 记录交互历史
    store.remember(
        session_id, "note",
        f"artifact:{artifact.get('artifact_id', 'unknown')}",
        f"交互物品：{artifact.get('name', '')}（{artifact.get('tag', '')}），回复：{full_text[:150]}",
    )
    yield {"type": "done"}


def stream_chat(session_id: str, message: str, artifact_context: Optional[dict[str, Any]] = None) -> Iterator[dict[str, Any]]:
    """与探索者精灵继续对话。

    artifact_context: 当前物品的上下文（可选，用于保持话题连贯）
    SSE 事件：status / token / done / error
    """
    session = store.get_session(session_id)
    if session is None:
        yield {"type": "error", "message": "session 不存在"}
        return

    if settings.mock_mode:
        yield {"type": "status", "stage": "探索者精灵在思考…"}
        time.sleep(0.3)
        yield {"type": "token", "delta": mock.explorer_chat(message, artifact_context)}
        yield {"type": "done"}
        return

    player = _gather_player_context(session_id)
    history = store.list_messages(session_id, agent="explorer", limit=8)
    dialogue = "\n".join(f"{m['role']}: {m['content']}" for m in history)

    artifact_info = ""
    if artifact_context:
        artifact_info = (
            f"\n当前物品：{artifact_context.get('name', '')}"
            f"（{artifact_context.get('tag', '')}，位于 {artifact_context.get('location', '')}）"
        )

    user_content = (
        f"学生说：{message}\n\n"
        f"学生目标：{player.get('goal', '')}\n"
        f"当前阶段：{player.get('current_stage', '')}"
        f"{artifact_info}\n\n"
        f"对话历史：\n{dialogue}"
    )
    messages = [
        {"role": "system", "content": prompts.EXPLORER_CHAT_SYSTEM},
        {"role": "user", "content": user_content},
    ]

    yield {"type": "status", "stage": "探索者精灵在思考…"}
    full_text = ""
    try:
        for delta in llm.stream_text(messages, temperature=0.8, max_tokens=600):
            full_text += delta
            yield {"type": "token", "delta": delta}
    except Exception as exc:
        log.warning("explorer 对话失败：%s", exc)
        if not settings.fallback_to_mock:
            yield {"type": "error", "message": f"探索者精灵暂时无法回应：{public_error_message(exc)}"}
            yield {"type": "done"}
            return
        yield {"type": "fallback", "reason": f"已切换演示模式：{public_error_message(exc)}"}
        full_text = mock.explorer_chat(message, artifact_context)
        yield {"type": "token", "delta": full_text}

    # 记录对话
    store.add_message(session_id, "user", message, agent="explorer")
    store.add_message(session_id, "assistant", full_text, agent="explorer")
    yield {"type": "done"}


def _extract_questions(text: str) -> list[str]:
    """从 Agent 回复中提取问句（以问号/？结尾的句子）。"""
    import re
    # 按句号/问号/感叹号分句，保留问句
    sentences = re.split(r'(?<=[？?。！!])\s*', text)
    questions = [s.strip() for s in sentences if re.search(r'[？?]$', s.strip())]
    return questions[:5]
