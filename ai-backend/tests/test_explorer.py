"""Explorer Agent：物品交互与好奇心激发的单元测试。"""
import pytest
from app.agents import explorer
from app.config import settings


@pytest.fixture
def sample_artifact():
    return {
        "artifact_id": "book-001",
        "name": "一本旧书",
        "tag": "book",
        "category": "reading",
        "location": "library",
        "description": "书架上的一本泛黄的旧书",
    }


# ---------------- _gather_player_context ----------------
def test_gather_player_context_returns_dict():
    """验证玩家上下文收集不报错。"""
    from app.memory.store import store
    sid = store.create_session(goal="学扩散模型", nickname="测试同学")
    ctx = explorer._gather_player_context(sid)
    assert ctx["goal"] == "学扩散模型"
    assert ctx["nickname"] == "测试同学"
    assert "roadmap_title" in ctx
    assert "current_stage" in ctx


# ---------------- _extract_questions ----------------
def test_extract_questions():
    text = "这是一个陈述。这是第一个问题？这是第二个问题？结尾。"
    qs = explorer._extract_questions(text)
    assert len(qs) == 2
    assert "第一个问题" in qs[0]
    assert "第二个问题" in qs[1]


def test_extract_questions_empty():
    assert explorer._extract_questions("没有问句的陈述。") == []


# ---------------- _search_artifact_background ----------------
def test_search_background_disabled(monkeypatch):
    monkeypatch.setattr(settings, "web_search_enabled", False)
    assert explorer._search_artifact_background("书", "book") == ""


def test_search_background_mock_mode(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", True)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    assert explorer._search_artifact_background("书", "book") == ""


def test_search_background_returns_formatted(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    fake = [{"title": "书籍的历史", "content": "从竹简到电子书"}]
    monkeypatch.setattr(
        "app.agents.explorer.web_search.search",
        lambda q, max_results=8: (fake, "bingrss"),
    )
    out = explorer._search_artifact_background("旧书", "book")
    assert "书籍的历史" in out
    assert "从竹简到电子书" in out


def test_search_background_rejects_mock_provider(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    monkeypatch.setattr(
        "app.agents.explorer.web_search.search",
        lambda q, max_results=8: ([{"title": "x", "content": "y"}], "mock"),
    )
    assert explorer._search_artifact_background("书", "book") == ""


# ---------------- interact (mock mode) ----------------
def test_interact_mock_mode_yields_events(sample_artifact):
    from app.memory.store import store
    sid = store.create_session(goal="学扩散模型")
    events = list(explorer.interact(sid, sample_artifact))
    types = [e["type"] for e in events]
    assert "status" in types
    assert "token" in types
    assert "questions" in types
    assert "artifact_info" in types
    assert "done" in types
    # 验证交互记录已存储
    memories = store.recall(sid, kind="note")
    artifact_keys = [m["key"] for m in memories if m["key"].startswith("artifact:")]
    assert "artifact:book-001" in artifact_keys


def test_interact_unknown_session(sample_artifact):
    events = list(explorer.interact("nonexistent", sample_artifact))
    assert events[0]["type"] == "error"


# ---------------- stream_chat (mock mode) ----------------
def test_chat_mock_mode():
    from app.memory.store import store
    sid = store.create_session(goal="学扩散模型")
    events = list(explorer.stream_chat(sid, "我觉得这个物品很神秘"))
    types = [e["type"] for e in events]
    assert "token" in types
    assert "done" in types


def test_chat_unknown_session():
    events = list(explorer.stream_chat("nonexistent", "hello"))
    assert events[0]["type"] == "error"


# ---------------- _build_interact_messages ----------------
def test_build_interact_messages(sample_artifact):
    player = {"goal": "学AI", "nickname": "小明", "roadmap_title": "", "current_stage": "",
              "quest_status": "", "dialogue": "", "profile": "", "artifact_history": ""}
    msgs = explorer._build_interact_messages(sample_artifact, player, "背景资料")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert "探索者精灵" in msgs[0]["content"]
    assert "一本旧书" in msgs[1]["content"]
    assert "背景资料" in msgs[1]["content"]


def test_build_interact_messages_no_background(sample_artifact):
    player = {"goal": "", "nickname": "", "roadmap_title": "", "current_stage": "",
              "quest_status": "", "dialogue": "", "profile": "", "artifact_history": ""}
    msgs = explorer._build_interact_messages(sample_artifact, player, "")
    assert "背景资料" not in msgs[1]["content"]
