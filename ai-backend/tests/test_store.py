"""SQLite 记忆层：会话 / 消息 / 路线图 / 任务状态。"""
from app.memory.store import Store


def _store(tmp_path) -> Store:
    return Store(tmp_path / "test.db")


def test_create_and_get_session(tmp_path):
    s = _store(tmp_path)
    sid = s.create_session(goal="学扩散模型", nickname="Eason")
    row = s.get_session(sid)
    assert row["goal"] == "学扩散模型"
    assert row["nickname"] == "Eason"
    assert len(sid) == 12


def test_get_missing_session_returns_none(tmp_path):
    assert _store(tmp_path).get_session("nope") is None


def test_state_roundtrip(tmp_path):
    s = _store(tmp_path)
    sid = s.create_session()
    assert s.get_state(sid) == {}
    s.update_state(sid, clarify_round=1, clarify_ready=False)
    s.update_state(sid, clarify_round=2)
    state = s.get_state(sid)
    assert state == {"clarify_round": 2, "clarify_ready": False}


def test_set_goal(tmp_path):
    s = _store(tmp_path)
    sid = s.create_session()
    s.set_goal(sid, "新目标")
    assert s.get_session(sid)["goal"] == "新目标"


def test_messages_are_ordered_and_limited(tmp_path):
    s = _store(tmp_path)
    sid = s.create_session()
    for i in range(30):
        s.add_message(sid, "user" if i % 2 == 0 else "assistant", f"m{i}", agent="scholar")
    msgs = s.list_messages(sid, limit=10)
    assert len(msgs) == 10
    assert [m["content"] for m in msgs] == [f"m{i}" for i in range(20, 30)]


def test_messages_can_be_filtered_by_agent(tmp_path):
    s = _store(tmp_path)
    sid = s.create_session()
    s.add_message(sid, "user", "问教授", agent="professor")
    s.add_message(sid, "user", "问学者", agent="scholar")
    only_prof = s.list_messages(sid, agent="professor")
    assert [m["content"] for m in only_prof] == ["问教授"]


def test_roadmap_roundtrip(tmp_path):
    s = _store(tmp_path)
    sid = s.create_session()
    assert s.get_roadmap(sid) is None
    s.save_roadmap(sid, {"title": "路线", "stages": []})
    assert s.get_roadmap(sid)["title"] == "路线"


def test_set_task_status_updates_nested_node(tmp_path):
    s = _store(tmp_path)
    sid = s.create_session()
    s.save_roadmap(sid, {
        "title": "路线",
        "stages": [{"id": "stage-1", "space": "gate",
                    "tasks": [{"id": "t-1-1", "status": "pending"},
                              {"id": "t-1-2", "status": "pending"}]}],
    })
    assert s.set_task_status(sid, "t-1-2", "done") is True
    tasks = s.get_roadmap(sid)["stages"][0]["tasks"]
    assert tasks[0]["status"] == "pending"
    assert tasks[1]["status"] == "done"


def test_set_task_status_returns_false_for_unknown(tmp_path):
    s = _store(tmp_path)
    sid = s.create_session()
    assert s.set_task_status(sid, "t-9-9", "done") is False   # 无路线图
    s.save_roadmap(sid, {"stages": [{"tasks": [{"id": "t-1-1", "status": "pending"}]}]})
    assert s.set_task_status(sid, "t-9-9", "done") is False   # 有路线图但没这个任务


def test_two_stores_are_isolated(tmp_path):
    """不同 db 文件互不干扰——保证测试不会串味。"""
    a, b = Store(tmp_path / "a.db"), Store(tmp_path / "b.db")
    sid = a.create_session(goal="A")
    assert b.get_session(sid) is None
