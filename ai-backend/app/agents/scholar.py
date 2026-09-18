"""Scholar Agent：目标澄清（流式）+ 路线图生成（结构化 JSON）。

对前端输出统一为事件 dict：
  {"type": "status",  "stage": "..."}           路线图生成进度
  {"type": "token",   "delta": "..."}           流式文本
  {"type": "ready",   "ready": true/false}      澄清是否完成
  {"type": "roadmap", "roadmap": {...}}         完整路线图
  {"type": "fallback","reason": "..."}          已降级到 mock
  {"type": "error",   "message": "..."}         不可恢复错误
  {"type": "done"}
"""
import logging
import time
from typing import Iterator, Optional

from app.agents.llm import llm
from app.config import settings
from app.core import prompts
from app.core.guard import public_error_message
from app.memory.store import store
from app.mock_data import golden_path as mock

log = logging.getLogger("scholar")

VALID_SPACES = {"gate", "library", "professor_office", "lab"}
# 模型没给（或给了非法）space 时，按阶段位置推断，顺序与 README 契约一致
POSITION_SPACES = ["gate", "library", "professor_office", "lab"]

# ---------- 澄清完成度的启发式兜底 ----------
# 真实模型偶尔不遵守 prompt 里的 <<<READY:>>> 标记要求（实测 deepseek-flash 两轮都不输出）。
# 此时用用户消息内容判断目标是否已足够清晰，避免前端永远等不到 ready 信号。
_READY_BASE_KEYWORDS = ("基础", "会", "学过", "了解", "熟悉", "用过", "python", "pytorch", "经验", "掌握", "入门")
_READY_TIME_KEYWORDS = ("小时", "每天", "天", "周", "时间", "周期", "月")
_READY_OUTCOME_KEYWORDS = ("做出", "跑通", "demo", "生成", "实现", "完成", "作品", "成果", "目标", "学会", "想", "要", "研究", "学")


def _heuristic_ready(*texts: str) -> bool:
    """三类信息（基础 / 时间 / 成果）至少命中两类，即视为目标已足够清晰。"""
    blob = " ".join(texts).lower()
    groups = (_READY_BASE_KEYWORDS, _READY_TIME_KEYWORDS, _READY_OUTCOME_KEYWORDS)
    return sum(1 for group in groups if any(k in blob for k in group)) >= 2


def _synthetic_gate_stage() -> dict:
    """模型漏掉 gate 阶段时补一个（每次返回新 dict，避免被重编号污染）。"""
    return {
        "id": "stage-1",
        "name": "X Gate · 目标确认",
        "space": "gate",
        "objective": "明确学习目标、现有基础与最终交付物",
        "tasks": [{
            "id": "t-1-1",
            "title": "目标拆解与基础自评",
            "description": "明确最终成果形态，自评先修知识，形成学习目标声明。",
            "space": "gate",
            "deliverable": "学习目标声明",
            "resources": [],
            "status": "pending",
        }],
    }


# ---------------- 流式工具 ----------------
def _chunk(text: str, size: int = 12) -> Iterator[str]:
    """把预制文本切成小块，模拟流式打字效果。"""
    for i in range(0, len(text), size):
        yield text[i : i + size]
        time.sleep(0.01)


class _MarkerFilter:
    """从流式 token 中实时剔除 <<<READY:true/false>>> 标记并解析 ready 状态。"""

    MARKER = "<<<READY:"

    def __init__(self) -> None:
        self.buf = ""
        self.ready: Optional[bool] = None

    def feed(self, text: str) -> str:
        out: list[str] = []
        self.buf += text
        while True:
            idx = self.buf.find("<<<")
            if idx == -1:
                if len(self.buf) >= 4:  # 保留尾部 4 字符，防止标记被 chunk 切断
                    out.append(self.buf[:-4])
                    self.buf = self.buf[-4:]
                break
            if idx > 0:
                out.append(self.buf[:idx])
                self.buf = self.buf[idx:]
            if self.buf.startswith(self.MARKER):
                end = self.buf.find(">>>", len(self.MARKER))
                if end == -1:
                    break  # 等后续 chunk
                self.ready = "true" in self.buf[len(self.MARKER) : end].lower()
                self.buf = self.buf[end + 3 :]
                continue
            # 以 <<< 开头但不是目标标记：攒够长度仍不匹配则放行
            if len(self.buf) >= len(self.MARKER) and not self.MARKER.startswith(self.buf):
                out.append(self.buf[:3])
                self.buf = self.buf[3:]
                continue
            break
        return "".join(out)

    def flush(self) -> str:
        buf = self.buf
        if buf.startswith("<<<"):
            if self.MARKER.startswith(buf[: len(buf)]):
                self.ready = self.ready if self.ready is not None else False
                self.buf = ""
                return ""
        self.buf = ""
        return buf


# ---------------- 1. 目标澄清 ----------------
def stream_clarify(session_id: str, message: str) -> Iterator[dict]:
    session = store.get_session(session_id)
    if session is None:
        yield {"type": "error", "message": "session 不存在"}
        return

    if not session.get("goal"):
        store.set_goal(session_id, message)  # 第一句先作为目标草稿
    store.add_message(session_id, "user", message, agent="scholar")

    if settings.mock_mode:
        state = store.get_state(session_id)
        if state.get("clarify_round", 0) >= 1:
            reply, ready = mock.clarify_after_followup()
        else:
            store.update_state(session_id, clarify_round=state.get("clarify_round", 0) + 1)
            reply, ready = mock.clarify(session.get("goal") or message, message)
        for piece in _chunk(reply):
            yield {"type": "token", "delta": piece}
        yield {"type": "ready", "ready": ready}
        store.add_message(session_id, "assistant", reply, agent="scholar")
        store.update_state(session_id, clarify_ready=ready)
        yield {"type": "done"}
        return

    history = store.list_messages(session_id, agent="scholar", limit=12)
    messages = [{"role": "system", "content": prompts.SCHOLAR_CLARIFY_SYSTEM}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]

    reply_text = ""
    marker = _MarkerFilter()
    ready: Optional[bool] = None
    try:
        for delta in llm.stream_text(messages, temperature=0.6, max_tokens=1024):
            clean = marker.feed(delta)
            if clean:
                reply_text += clean
                yield {"type": "token", "delta": clean}
        tail = marker.flush()
        if tail:
            reply_text += tail
            yield {"type": "token", "delta": tail}
        ready = marker.ready
    except Exception as exc:  # 网络/余额/超时等
        log.warning("clarify LLM 调用失败：%s", exc)
        if not settings.fallback_to_mock:
            store.add_message(session_id, "assistant", reply_text, agent="scholar")
            yield {"type": "error", "message": f"AI 服务暂不可用：{public_error_message(exc)}"}
            yield {"type": "done"}
            return
        yield {"type": "fallback", "reason": f"DeepSeek 调用失败，已切换演示模式：{public_error_message(exc)}"}
        state = store.get_state(session_id)
        reply, ready = mock.clarify(session.get("goal") or message, message)
        reply_text = reply
        for piece in _chunk(reply):
            yield {"type": "token", "delta": piece}

    if ready is not True:
        # 兜底条件：模型未明确输出 <<<READY:true>>>（没给标记，或被非标记的 <<< 片段干扰成 false）。
        # 用启发式判断（基础/时间/成果 三类信息命中≥2），命中则升级为 ready，避免流程卡在澄清阶段。
        user_texts = [m["content"] for m in history if m.get("role") == "user"] + [message]
        heuristic = _heuristic_ready(*user_texts)
        if heuristic:
            log.info("clarify 标记缺失/为 false，启发式兜底升级 ready=true（模型标记=%s）", ready)
            ready = True

    reply_text = reply_text.strip()
    store.add_message(session_id, "assistant", reply_text, agent="scholar")
    store.update_state(session_id, clarify_ready=ready)
    yield {"type": "ready", "ready": ready}
    yield {"type": "done"}


# ---------------- 2. 路线图生成 ----------------
def _normalize_roadmap(data: dict) -> dict:
    """校验并规范化模型输出，保证产物一定能被前端 3D 场景渲染。

    做四件事：
    1. 补齐契约必填字段（stage.name / task.title / id / status / resource.url 等）；
    2. space 非法或缺失时按阶段位置推断，不丢空间；
    3. 保证 gate 阶段存在且位于首位（缺失补一个，错位则前移）；
    4. 按最终顺序统一重编号 id。

    输出必须能通过 app.api.schemas.Roadmap 校验（见 tests/test_scholar_units.py）。
    """
    stages = data.get("stages") or []
    cleaned: list[dict] = []
    for i, stage in enumerate(stages):
        if not isinstance(stage, dict):
            continue
        space = stage.get("space")
        if space not in VALID_SPACES:
            # 按位置推断，而不是一律塞 library——否则会丢掉某个空间
            space = POSITION_SPACES[i] if i < len(POSITION_SPACES) else "library"
        tasks = []
        for j, task in enumerate(stage.get("tasks") or []):
            if not isinstance(task, dict):
                continue
            t_space = task.get("space") if task.get("space") in VALID_SPACES else space
            resources = []
            for res in task.get("resources") or []:
                if isinstance(res, dict):
                    res.setdefault("title", "")
                    res.setdefault("type", "article")
                    res.setdefault("url", "")  # 模型可能省略 url，统一补默认值
                    resources.append(res)
            task["resources"] = resources
            task["id"] = task.get("id") or f"t-{i + 1}-{j + 1}"
            # title 是契约必填字段，模型漏了会给前端 undefined
            task["title"] = task.get("title") or f"任务 {j + 1}"
            task["description"] = task.get("description", "")
            task["deliverable"] = task.get("deliverable", "")
            task["space"] = t_space
            task["status"] = task.get("status", "pending")
            tasks.append(task)
        stage["id"] = stage.get("id") or f"stage-{i + 1}"
        stage["name"] = stage.get("name") or f"阶段 {i + 1}"
        stage["objective"] = stage.get("objective", "")
        stage["space"] = space
        stage["tasks"] = tasks
        cleaned.append(stage)

    # 保证 gate 阶段存在且在最前：缺失则补一个，位置不对则整体前移
    gate_idx = next((i for i, s in enumerate(cleaned) if s.get("space") == "gate"), None)
    if gate_idx is None:
        cleaned.insert(0, _synthetic_gate_stage())
    elif gate_idx != 0:
        cleaned.insert(0, cleaned.pop(gate_idx))

    # 统一重编号，保证 id 与最终顺序一致
    for i, stage in enumerate(cleaned):
        stage["id"] = f"stage-{i + 1}"
        for j, task in enumerate(stage.get("tasks", [])):
            task["id"] = f"t-{i + 1}-{j + 1}"

    data["stages"] = cleaned
    data.setdefault("title", "个性化学习与研究路线")
    data.setdefault("summary", "")
    data.setdefault("estimated_duration", "2 周")
    data.setdefault("final_outcome", "一个可展示的项目成果与研究报告")
    return data


def generate_roadmap(session_id: str) -> Iterator[dict]:
    session = store.get_session(session_id)
    if session is None:
        yield {"type": "error", "message": "session 不存在"}
        return
    goal = session.get("goal") or "（学生未明确填写目标）"

    if settings.mock_mode:
        yield {"type": "status", "stage": "Scholar Agent 正在规划学习路线…"}
        time.sleep(0.4)
        roadmap = mock.roadmap(goal)
        store.save_roadmap(session_id, roadmap)
        yield {"type": "roadmap", "roadmap": roadmap}
        yield {"type": "done"}
        return

    transcript = store.list_messages(session_id, agent="scholar", limit=12)
    dialogue = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
    user_content = f"学生目标：{goal}\n\n对话记录：\n{dialogue}"
    messages = [
        {"role": "system", "content": prompts.SCHOLAR_ROADMAP_SYSTEM},
        {"role": "user", "content": user_content},
    ]

    roadmap: Optional[dict] = None
    try:
        yield {"type": "status", "stage": "Scholar Agent 正在分析目标与基础…"}
        data = llm.chat_json(messages, temperature=0.3, max_tokens=4096, retries=1)
        yield {"type": "status", "stage": "正在匹配 X Gate / Library / Lab 学习空间…"}
        roadmap = _normalize_roadmap(data)
    except Exception as exc:
        log.warning("roadmap 生成失败：%s", exc)
        if not settings.fallback_to_mock:
            yield {"type": "error", "message": f"路线图生成失败：{public_error_message(exc)}"}
            yield {"type": "done"}
            return
        yield {"type": "fallback", "reason": f"DeepSeek 调用失败，已切换演示路线图：{public_error_message(exc)}"}
        time.sleep(0.3)
        roadmap = mock.roadmap(goal)

    store.save_roadmap(session_id, roadmap)
    yield {"type": "roadmap", "roadmap": roadmap}
    yield {"type": "done"}
