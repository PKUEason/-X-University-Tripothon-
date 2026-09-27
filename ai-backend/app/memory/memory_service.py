# -*- coding: utf-8 -*-
"""Memory 服务：用户画像提取、会话摘要、记忆上下文构建。

- extract_profile：Scholar 澄清完成后调用，LLM 提取画像存入 memories（失败用 mock）；
- summarize_if_needed / messages_with_summary：长对话自动摘要，控制喂给 LLM 的上下文长度；
- build_memory_block：把画像拼进各 Agent 的 system 背景，让 AI「记得学生是谁」。
"""
import logging
from typing import Any, Optional

from app.agents.llm import llm
from app.config import settings
from app.core import prompts
from app.memory.store import store

log = logging.getLogger("memory")

PROFILE_KEYS = ("goal", "background", "time_budget", "style")

# mock / 降级用画像（与黄金路径一致）
_MOCK_PROFILE = {
    "goal": "两周入门扩散模型并跑通文生图 Demo",
    "background": "有 PyTorch 基础，了解神经网络基本概念",
    "time_budget": "每天约 3 小时，共两周",
    "style": "动手实践 + 项目驱动",
}
_MOCK_SUMMARY = (
    "此前对话：学生说明学习目标为扩散模型文生图，具备 PyTorch 基础，"
    "每天可投入约 3 小时、周期两周；Scholar 已完成目标澄清。"
)

# 消息条数超过该阈值触发摘要；保留最近 KEEP_RECENT 条原文
SUMMARY_THRESHOLD = 12
KEEP_RECENT = 6


def extract_profile(session_id: str) -> dict[str, Any]:
    """从 Scholar 对话提取画像并写入长期记忆。返回画像 dict。"""
    history = store.list_messages(session_id, agent="scholar", limit=10)
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history)

    profile: dict[str, str]
    if settings.mock_mode:
        profile = dict(_MOCK_PROFILE)
    else:
        try:
            data = llm.chat_json(
                [
                    {"role": "system", "content": prompts.MEMORY_PROFILE_SYSTEM},
                    {"role": "user", "content": f"对话记录如下：\n{transcript}"},
                ],
                temperature=0.1,
                max_tokens=600,
            )
            profile = {k: str(data.get(k, "")).strip() for k in PROFILE_KEYS}
        except Exception as exc:
            log.warning("画像提取失败，使用 mock 画像：%s", exc)
            profile = dict(_MOCK_PROFILE)

    for key, value in profile.items():
        store.remember(session_id, "profile", key, value)
    log.info("学生画像已写入记忆：%s", profile.get("goal", ""))
    return profile


def summarize_if_needed(
    session_id: str, agent: str, threshold: int = SUMMARY_THRESHOLD
) -> Optional[str]:
    """消息超过阈值时摘要早期对话并持久化。返回摘要文本（无需摘要时返回 None）。"""
    history = store.list_messages(session_id, agent=agent, limit=100)
    if len(history) <= threshold:
        return None

    to_summarize = history[:-KEEP_RECENT]
    if not to_summarize:
        return None
    last_id = to_summarize[-1]["id"]

    existing = store.get_summary(session_id, agent)
    if existing and existing["up_to_id"] >= last_id:
        return existing["content"]

    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in to_summarize)
    if settings.mock_mode:
        summary = _MOCK_SUMMARY
    else:
        try:
            raw = llm.chat(
                [
                    {"role": "system", "content": prompts.CONVERSATION_SUMMARY_SYSTEM},
                    {"role": "user", "content": transcript},
                ],
                temperature=0.1,
                max_tokens=400,
            )
            summary = (
                raw.choices[0].message.content if hasattr(raw, "choices") else str(raw)
            ).strip()
        except Exception as exc:
            log.warning("会话摘要失败，使用 mock 摘要：%s", exc)
            summary = _MOCK_SUMMARY

    store.save_summary(session_id, agent, summary, last_id)
    log.info("已生成 %s 对话摘要（覆盖至消息 #%s）", agent, last_id)
    return summary


def messages_with_summary(
    session_id: str, agent: str, recent_limit: int = 8
) -> list[dict[str, str]]:
    """构建对话上下文：摘要（若有）+ 最近若干条原始消息，避免重复与超长。"""
    history = store.list_messages(session_id, agent=agent, limit=100)
    summary = store.get_summary(session_id, agent)
    out: list[dict[str, str]] = []
    if summary:
        out.append({"role": "system", "content": "[此前对话摘要] " + summary["content"]})
        cutoff = summary["up_to_id"]
        history = [m for m in history if m["id"] > cutoff]
    out += [{"role": m["role"], "content": m["content"]} for m in history[-recent_limit:]]
    return out


def build_memory_block(session_id: str) -> str:
    """把学生画像拼成给各 Agent 的背景文本；无画像时返回空串。"""
    rows = store.recall(session_id, kind="profile")
    if not rows:
        return ""
    labels = {"goal": "目标", "background": "基础", "time_budget": "时间", "style": "偏好"}
    lines = ["[学生画像]"]
    for row in rows:
        if row.get("content"):
            lines.append(f"- {labels.get(row['key'], row['key'])}：{row['content']}")
    return "\n".join(lines)


def record_struggle(session_id: str, task_id: Optional[str], question: str) -> None:
    """Professor 答疑后记录学生的卡点（kind=progress），供后续回顾与个性化引导。"""
    key = f"struggle:{task_id or 'general'}"
    store.remember(session_id, "progress", key, question[:300])
