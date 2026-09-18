"""故障降级路径：断网 / 余额不足 / 超时 / JSON 解析失败时，Demo 不能中断。

这是整个项目「路演保险」的核心，但恰恰是端到端冒烟测试覆盖不到的
（真实 API 正常时永远不会走进这些分支）。这里用伪造 LLM 强制触发。
"""
import pytest

from app.agents import lab_mentor, professor, scholar


def _boom(*args, **kwargs):
    raise RuntimeError("模拟：DeepSeek 余额不足 / 网络超时")


def _boom_mid_stream(*args, **kwargs):
    yield "我已经说了一半"
    raise RuntimeError("模拟：流式传输中途断开")


@pytest.fixture()
def patched(monkeypatch):
    """把 LLM 的两个入口都换成可注入的桩。"""

    def _install(stream=None, json_=None):
        if stream is not None:
            monkeypatch.setattr("app.agents.llm.llm.stream_text", stream)
        if json_ is not None:
            monkeypatch.setattr("app.agents.llm.llm.chat_json", json_)

    return _install


# ---------------- Scholar：澄清降级 ----------------
def test_clarify_falls_back_to_mock(sse, session, live_mode, patched):
    patched(stream=_boom)
    events = sse("/api/scholar/clarify", {"session_id": session, "message": "我想学扩散模型"})
    kinds = [e["event"] for e in events]

    assert "fallback" in kinds
    assert kinds[-1] == "done"
    assert "error" not in kinds
    assert "token" in kinds                       # 降级后依然有内容产出
    assert events[kinds.index("fallback")]["payload"]["reason"]


def test_clarify_mid_stream_failure_still_completes(sse, session, live_mode, patched):
    patched(stream=_boom_mid_stream)
    events = sse("/api/scholar/clarify", {"session_id": session, "message": "你好"})
    kinds = [e["event"] for e in events]
    assert "fallback" in kinds
    assert kinds[-1] == "done"


def test_clarify_raises_error_when_fallback_disabled(sse, session, live_mode, patched):
    live_mode.fallback_to_mock = False
    patched(stream=_boom)
    events = sse("/api/scholar/clarify", {"session_id": session, "message": "你好"})
    kinds = [e["event"] for e in events]

    assert "error" in kinds
    assert "fallback" not in kinds
    assert kinds[-1] == "done"                    # 即使报错也要正常收尾
    assert "AI 服务暂不可用" in events[kinds.index("error")]["payload"]["message"]


# ---------------- Scholar：路线图降级 ----------------
def test_roadmap_falls_back_to_mock(sse, session, live_mode, patched):
    patched(json_=_boom)
    events = sse("/api/scholar/roadmap", {"session_id": session})
    kinds = [e["event"] for e in events]

    assert "fallback" in kinds
    assert kinds.count("roadmap") == 1
    assert kinds[-1] == "done"
    rm = next(e["payload"]["roadmap"] for e in events if e["event"] == "roadmap")
    assert len(rm["stages"]) == 4                 # 降级路线图依然是完整可渲染的


def test_roadmap_raises_error_when_fallback_disabled(sse, session, live_mode, patched):
    live_mode.fallback_to_mock = False
    patched(json_=_boom)
    events = sse("/api/scholar/roadmap", {"session_id": session})
    kinds = [e["event"] for e in events]

    assert "error" in kinds
    assert "roadmap" not in kinds
    assert kinds[-1] == "done"


# ---------------- Professor：答疑降级 ----------------
def test_professor_falls_back_to_mock(sse, session, live_mode, patched):
    patched(stream=_boom)
    events = sse("/api/professor/chat", {"session_id": session, "message": "讲讲反向扩散"})
    kinds = [e["event"] for e in events]

    assert "fallback" in kinds
    assert kinds[-1] == "done"
    assert "".join(e["payload"]["delta"] for e in events if e["event"] == "token").strip()


# ---------------- Lab：实践指导降级 ----------------
def test_lab_marks_degraded_when_llm_fails(client, session, live_mode, patched):
    patched(json_=_boom)
    body = client.post("/api/lab/guidance", json={"session_id": session, "task_id": "t-4-1"}).json()

    assert body["degraded"] is True
    assert body["degraded_reason"]
    for key in ("overview", "steps", "deliverables", "pitfalls", "tools"):
        assert key in body


def test_lab_marks_degraded_when_json_incomplete(client, session, live_mode, patched):
    """模型返回了合法 JSON 但缺字段——同样要降级，不能把残缺结构丢给前端。"""
    patched(json_=lambda *a, **k: {"overview": "只有一个字段"})
    body = client.post("/api/lab/guidance", json={"session_id": session}).json()

    assert body["degraded"] is True
    assert "steps" in body and len(body["steps"]) >= 3


def test_lab_uses_llm_output_when_valid(client, session, live_mode, patched):
    good = {
        "overview": "真实模型输出",
        "steps": [{"title": "步骤一", "detail": "细节"}],
        "deliverables": ["产出"],
        "pitfalls": ["坑"],
        "tools": ["diffusers"],
    }
    patched(json_=lambda *a, **k: good)
    body = client.post("/api/lab/guidance", json={"session_id": session}).json()

    assert body["overview"] == "真实模型输出"
    assert "degraded" not in body


# ---------------- 单元级：降级不依赖 HTTP ----------------
def test_scholar_stream_clarify_yields_fallback_event_directly(live_mode, monkeypatch, tmp_path):
    from app.memory.store import Store

    monkeypatch.setattr("app.agents.llm.llm.stream_text", _boom)
    monkeypatch.setattr(scholar, "store", Store(tmp_path / "u.db"))
    sid = scholar.store.create_session(goal="学扩散模型")

    kinds = [e["type"] for e in scholar.stream_clarify(sid, "你好")]
    assert "fallback" in kinds and kinds[-1] == "done"


def test_lab_mentor_returns_error_dict_when_fallback_disabled(live_mode, monkeypatch, tmp_path):
    from app.memory.store import Store

    live_mode.fallback_to_mock = False
    monkeypatch.setattr("app.agents.llm.llm.chat_json", _boom)
    monkeypatch.setattr(lab_mentor, "store", Store(tmp_path / "u.db"))
    sid = lab_mentor.store.create_session(goal="学扩散模型")

    result = lab_mentor.generate_guidance(sid, task_id="t-4-1")
    assert "error" in result


def test_professor_yields_error_when_fallback_disabled(live_mode, monkeypatch, tmp_path):
    from app.memory.store import Store

    live_mode.fallback_to_mock = False
    monkeypatch.setattr("app.agents.llm.llm.stream_text", _boom)
    monkeypatch.setattr(professor, "store", Store(tmp_path / "u.db"))
    sid = professor.store.create_session(goal="学扩散模型")

    kinds = [e["type"] for e in professor.stream_chat(sid, "讲讲反向扩散")]
    assert "error" in kinds and kinds[-1] == "done"
