# -*- coding: utf-8 -*-
"""Memory：存储层 + 画像提取 + 会话摘要 + API 契约。"""
import pytest

from app.memory import memory_service as ms
from app.memory.store import store


# ---------- 存储层 ----------
def test_remember_and_recall():
    sid = store.create_session(goal="记忆测试")
    store.remember(sid, "note", "k1", "内容甲")
    rows = store.recall(sid, kind="note", key="k1")
    assert len(rows) == 1 and rows[0]["content"] == "内容甲"


def test_remember_is_upsert():
    sid = store.create_session(goal="upsert 测试")
    store.remember(sid, "note", "k", "v1")
    store.remember(sid, "note", "k", "v2")
    rows = store.recall(sid, kind="note", key="k")
    assert len(rows) == 1 and rows[0]["content"] == "v2"


def test_global_memory():
    sid = store.create_session(goal="全局记忆测试")
    store.remember(None, "note", "global-key", "全局内容")
    rows = store.recall(sid, key="global-key")
    assert rows and rows[0]["content"] == "全局内容"


def test_forget():
    sid = store.create_session(goal="forget 测试")
    store.remember(sid, "note", "k", "v")
    assert store.forget(sid, "note", "k") is True
    assert store.recall(sid, key="k") == []


# ---------- 画像提取（conftest 已设 MOCK_MODE=true） ----------
def test_extract_profile_writes_memories():
    sid = store.create_session(goal="扩散模型文生图")
    store.add_message(sid, "user", "我有 PyTorch 基础，每天 3 小时，想跑通文生图", agent="scholar")
    profile = ms.extract_profile(sid)
    assert set(profile) == set(ms.PROFILE_KEYS)
    rows = store.recall(sid, kind="profile")
    assert len(rows) == 4
    assert any("文生图" in r["content"] for r in rows)


def test_build_memory_block():
    sid = store.create_session(goal="block 测试")
    ms.extract_profile(sid)
    block = ms.build_memory_block(sid)
    assert "[学生画像]" in block and "目标" in block


def test_build_memory_block_empty():
    sid = store.create_session(goal="空画像")
    assert ms.build_memory_block(sid) == ""


# ---------- 会话摘要 ----------
def test_summarize_when_short_history():
    sid = store.create_session(goal="短会话")
    for i in range(3):
        store.add_message(sid, "user", f"问题 {i}", agent="professor")
    assert ms.summarize_if_needed(sid, "professor") is None


def test_summarize_long_history():
    sid = store.create_session(goal="长会话")
    for i in range(ms.SUMMARY_THRESHOLD + 2):
        store.add_message(sid, "user" if i % 2 == 0 else "assistant", f"第 {i} 条内容", agent="professor")
    summary = ms.summarize_if_needed(sid, "professor")
    assert summary
    stored = store.get_summary(sid, "professor")
    assert stored and stored["content"] == summary


def test_messages_with_summary():
    sid = store.create_session(goal="摘要上下文")
    for i in range(ms.SUMMARY_THRESHOLD + 2):
        store.add_message(sid, "user", f"消息 {i}", agent="professor")
    ms.summarize_if_needed(sid, "professor")
    msgs = ms.messages_with_summary(sid, "professor")
    assert msgs[0]["role"] == "system" and "摘要" in msgs[0]["content"]
    # 摘要之后只保留最近的原始消息
    assert len(msgs) <= ms.KEEP_RECENT + 1


def test_record_struggle():
    sid = store.create_session(goal="卡点记录")
    ms.record_struggle(sid, "t-2-1", "不理解反向过程为什么能预测噪声")
    rows = store.recall(sid, kind="progress")
    assert rows and "反向过程" in rows[0]["content"]


# ---------- API ----------
def test_memory_endpoints(client, session):
    r = client.post(
        "/api/memory/remember",
        json={"session_id": session, "kind": "note", "key": "api-k", "content": "api 内容"},
    )
    assert r.status_code == 200 and r.json()["ok"]
    r = client.get(f"/api/memory?session_id={session}")
    assert r.status_code == 200
    assert any(m["key"] == "api-k" for m in r.json()["memories"])


def test_memory_endpoints_404(client):
    assert client.get("/api/memory?session_id=nope").status_code == 404
