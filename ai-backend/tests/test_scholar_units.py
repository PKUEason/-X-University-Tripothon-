"""Scholar 内部的两个纯函数：流式标记过滤器 + 路线图规范化。

这两处是最容易出隐蔽 bug 的地方——标记可能被 chunk 切断，
模型输出的路线图可能缺 id / space / 乱序，一旦漏了前端 3D 场景就渲染不出来。
"""
from app.agents.scholar import _MarkerFilter, _normalize_roadmap, _search_background
from app.config import settings


# ---------------- _MarkerFilter ----------------
def test_marker_stripped_in_one_shot():
    f = _MarkerFilter()
    out = f.feed("目标已明确。\n<<<READY:true>>>")
    assert out == "目标已明确。\n"
    assert f.ready is True
    assert f.flush() == ""


def test_marker_ready_false():
    f = _MarkerFilter()
    f.feed("还需要了解你的基础。<<<READY:false>>>")
    assert f.ready is False


def test_marker_split_across_chunks():
    """模拟 SSE 逐字符下发，标记被切成碎片。"""
    f = _MarkerFilter()
    text = "很好，我们开始吧。<<<READY:true>>>"
    emitted = "".join(f.feed(ch) for ch in text)
    emitted += f.flush()
    assert emitted == "很好，我们开始吧。"
    assert f.ready is True


def test_marker_in_the_middle():
    f = _MarkerFilter()
    out = f.feed("前半段<<<READY:true>>>后半段")
    out += f.flush()
    assert out == "前半段后半段"
    assert f.ready is True


def test_plain_text_is_passed_through_untouched():
    f = _MarkerFilter()
    text = "这是一段完全没有机器标记的普通回答，长度超过四十二个字符用来触发尾缓冲逻辑。"
    out = "".join(f.feed(ch) for ch in text) + f.flush()
    assert out == text
    assert f.ready is None


def test_double_angle_brackets_that_are_not_the_marker():
    """`<<` 开头但不是 `<<<READY:` 时要原样放行，不能吞字。"""
    f = _MarkerFilter()
    text = "a <<b 这不是标记 c"
    out = "".join(f.feed(ch) for ch in text) + f.flush()
    assert out == text


def test_ready_stays_none_when_marker_truncated_halfway():
    """流被截断在 `<<<`（半个前缀），ready 保持 None，让上层 _heuristic_ready 兜底。"""
    f = _MarkerFilter()
    f.feed("好的。<<<")
    assert f.flush() == ""
    assert f.ready is None


def test_ready_parsed_when_marker_value_truncated():
    """流被截断在 `<<<READY:true`（已写 MARKER 但缺 >>>），flush 时解析出 true。"""
    f = _MarkerFilter()
    f.feed("好的。<<<READY:true")
    assert f.flush() == ""
    assert f.ready is True


def test_ready_stays_none_when_marker_value_empty():
    """流被截断在 `<<<READY:`（已写 MARKER 但没写值），保持 None 不瞎猜。"""
    f = _MarkerFilter()
    f.feed("好的。<<<READY:")
    assert f.flush() == ""
    assert f.ready is None


# ---------------- _normalize_roadmap ----------------
def _stage(space, n_tasks=1, with_id=False):
    tasks = []
    for j in range(n_tasks):
        t = {"title": f"任务{j + 1}", "description": "描述", "deliverable": "成果"}
        if with_id:
            t["id"] = f"t-{j + 1}"
        tasks.append(t)
    s = {"name": f"{space} 阶段", "objective": "目标", "tasks": tasks}
    if with_id:
        s["id"] = f"stage-{space}"
    s["space"] = space
    return s


def test_normalize_fills_missing_ids_and_status():
    data = {"stages": [_stage("gate", 1), _stage("library", 2)]}
    out = _normalize_roadmap(data)
    assert [s["id"] for s in out["stages"]] == ["stage-1", "stage-2"]
    assert [t["id"] for t in out["stages"][1]["tasks"]] == ["t-2-1", "t-2-2"]
    assert all(t["status"] == "pending" for s in out["stages"] for t in s["tasks"])


def test_normalize_forces_gate_first_and_renumbers():
    """模型漏了 gate 阶段时，必须补一个并整体重编号。"""
    data = {"stages": [_stage("library", 2), _stage("lab", 1)]}
    out = _normalize_roadmap(data)
    spaces = [s["space"] for s in out["stages"]]
    assert spaces == ["gate", "library", "lab"]
    assert [s["id"] for s in out["stages"]] == ["stage-1", "stage-2", "stage-3"]
    assert out["stages"][0]["tasks"][0]["id"] == "t-1-1"
    assert out["stages"][1]["tasks"][0]["id"] == "t-2-1"


def test_normalize_handles_empty_stages():
    out = _normalize_roadmap({"stages": []})
    assert len(out["stages"]) == 1
    assert out["stages"][0]["space"] == "gate"
    assert out["stages"][0]["tasks"]


def test_normalize_replaces_invalid_space():
    data = {"stages": [{"name": "怪空间", "space": "cafeteria", "tasks": []},
                       {"name": "图书馆", "space": "library", "tasks": []}]}
    out = _normalize_roadmap(data)
    assert out["stages"][0]["space"] == "gate"          # 首阶段强制 gate
    assert out["stages"][1]["space"] == "library"       # 合法值保留


def test_normalize_backfills_resource_defaults():
    """模型经常给 resources 但省略 url / type，这里必须补默认值，否则前端会 undefined。"""
    data = {"stages": [{"name": "图书馆", "space": "library",
                        "tasks": [{"title": "精读", "resources": [{"title": "DDPM 论文"}]}]}]}
    out = _normalize_roadmap(data)
    res = out["stages"][1]["tasks"][0]["resources"][0]
    assert res["title"] == "DDPM 论文"
    assert res["type"] == "article"
    assert res["url"] == ""


def test_normalize_skips_non_dict_entries():
    data = {"stages": ["我是一个字符串", {"name": "图书馆", "space": "library",
                                          "tasks": [None, {"title": "有效任务"}]}]}
    out = _normalize_roadmap(data)
    assert len(out["stages"]) == 2                       # 字符串阶段被丢弃，补了 gate
    tasks = [t for s in out["stages"] for t in s["tasks"]]
    assert all(isinstance(t, dict) for t in tasks)


def test_normalize_fills_top_level_defaults():
    out = _normalize_roadmap({"stages": [_stage("gate")]})
    assert out["title"] and out["summary"] is not None
    assert out["estimated_duration"] and out["final_outcome"]


# ---------------- 回归：曾经会「吃掉」一个空间 ----------------
def test_normalize_missing_gate_keeps_every_space():
    """模型返回 [library, professor_office, lab] 时，必须补 gate 而不是把 library 改名成 gate。

    历史 bug：首阶段被无条件改写成 gate，导致 library 空间从路线图里消失，
    前端 3D 图书馆永远收不到任务节点。
    """
    data = {"stages": [_stage("library", 2), _stage("professor_office", 1), _stage("lab", 1)]}
    out = _normalize_roadmap(data)
    assert [s["space"] for s in out["stages"]] == ["gate", "library", "professor_office", "lab"]
    # 原 library 阶段的内容不能被改动
    lib = out["stages"][1]
    assert lib["name"] == "library 阶段"
    assert len(lib["tasks"]) == 2


def test_normalize_moves_misplaced_gate_to_front():
    """gate 出现在中间时要前移，而不是再补一个（避免出现两个 gate）。"""
    data = {"stages": [_stage("library", 1), _stage("gate", 1), _stage("lab", 1)]}
    out = _normalize_roadmap(data)
    assert [s["space"] for s in out["stages"]] == ["gate", "library", "lab"]
    assert sum(1 for s in out["stages"] if s["space"] == "gate") == 1


def test_normalize_infers_space_by_position():
    """模型完全不给 space 字段时，按阶段位置推断，保证四空间齐全。"""
    data = {"stages": [
        {"name": "一", "tasks": [{"title": "t"}]},
        {"name": "二", "tasks": [{"title": "t"}]},
        {"name": "三", "tasks": [{"title": "t"}]},
        {"name": "四", "tasks": [{"title": "t"}]},
    ]}
    out = _normalize_roadmap(data)
    assert [s["space"] for s in out["stages"]] == ["gate", "library", "professor_office", "lab"]


def test_normalize_output_is_always_contract_valid():
    """喂各种脏输入，输出都必须能通过 Pydantic 契约模型。"""
    from app.api.schemas import Roadmap

    dirty_cases = [
        {"stages": []},
        {"stages": [{"space": "cafeteria", "tasks": []}]},
        {"stages": [_stage("lab", 2)]},
        {"stages": [None, "字符串", _stage("library", 1)]},
        {"stages": [_stage("professor_office", 1), _stage("gate", 1), _stage("library", 1)]},
        {},
    ]
    for case in dirty_cases:
        rm = Roadmap.model_validate(_normalize_roadmap(dict(case)))
        assert rm.stages, f"输入 {case} 产出了空路线图"
        assert rm.stages[0].space == "gate", f"输入 {case} 的首阶段不是 gate"
        ids = [t.id for s in rm.stages for t in s.tasks]
        assert len(ids) == len(set(ids)), f"输入 {case} 产生了重复任务 id：{ids}"


# ---------------- _search_background（联网背景搜索） ----------------
def test_search_background_returns_empty_in_mock_mode(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", True)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    assert _search_background("diffusion model") == ""


def test_search_background_returns_empty_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "web_search_enabled", False)
    assert _search_background("diffusion model") == ""


def test_search_background_formats_results(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    fake = [
        {"title": "Diffusion Models Explained", "content": "A gentle intro to diffusion."},
        {"title": "DDPM Paper", "content": "Denoising diffusion probabilistic models."},
    ]
    monkeypatch.setattr(
        "app.agents.scholar.web_search.search",
        lambda q, max_results=8: (fake, "bingrss"),
    )
    out = _search_background("diffusion", max_results=3)
    assert "Diffusion Models Explained" in out
    assert "A gentle intro to diffusion." in out
    assert "DDPM Paper" in out
    # 每条以 "- " 开头
    assert all(line.startswith("- ") for line in out.split("\n") if line)


def test_search_background_swallows_errors(monkeypatch):
    """搜索 provider 抛异常时返回空串，不阻塞澄清流程。"""
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    def boom(q, max_results=8):
        raise RuntimeError("network down")
    monkeypatch.setattr("app.agents.scholar.web_search.search", boom)
    assert _search_background("anything") == ""


def test_search_background_empty_results(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    monkeypatch.setattr(
        "app.agents.scholar.web_search.search",
        lambda q, max_results=8: ([], "bingrss"),
    )
    assert _search_background("xyzzy nonexistent") == ""


def test_search_background_rejects_mock_provider(monkeypatch):
    """联网失败降级到 mock 语料时，必须返回空串，不能把扩散模型写死内容当真实背景。"""
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "web_search_enabled", True)
    mock_corpus = [{"title": "HuggingFace Diffusers", "content": "扩散模型推理库"}]
    monkeypatch.setattr(
        "app.agents.scholar.web_search.search",
        lambda q, max_results=8: (mock_corpus, "mock"),
    )
    assert _search_background("柔性机器人入门") == ""
