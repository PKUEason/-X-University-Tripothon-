"""API 请求 / 响应数据模型（前后端契约）。"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Space = Literal["gate", "library", "professor_office", "lab"]
TaskStatus = Literal["pending", "in_progress", "done"]


# ---------- 路线图领域模型 ----------
class Resource(BaseModel):
    title: str = ""
    type: Literal["paper", "article", "video", "course", "tool"] = "article"
    url: str = ""


class TaskNode(BaseModel):
    id: str
    title: str
    description: str = ""
    space: Space = "library"
    deliverable: str = ""
    resources: list[Resource] = Field(default_factory=list)
    status: TaskStatus = "pending"


class Stage(BaseModel):
    id: str
    name: str
    space: Space = "gate"
    objective: str = ""
    tasks: list[TaskNode] = Field(default_factory=list)


class Roadmap(BaseModel):
    title: str
    summary: str = ""
    estimated_duration: str = ""
    stages: list[Stage]
    final_outcome: str = ""


# ---------- 请求体 ----------
class SessionCreate(BaseModel):
    goal: Optional[str] = None
    nickname: Optional[str] = None


class ClarifyRequest(BaseModel):
    session_id: str
    message: str


class RoadmapRequest(BaseModel):
    session_id: str


class ProfessorChatRequest(BaseModel):
    session_id: str
    message: str
    stage_id: Optional[str] = None
    task_id: Optional[str] = None


class RetrieveRequest(BaseModel):
    session_id: str
    query: str
    arxiv_query: Optional[str] = Field(default=None, max_length=200)
    stage_id: Optional[str] = None
    task_id: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20, description="返回资料条数，1-20")


class LabRequest(BaseModel):
    session_id: str
    stage_id: Optional[str] = None
    task_id: Optional[str] = None


class ProgressRequest(BaseModel):
    task_id: str
    status: TaskStatus


class MemoryQuery(BaseModel):
    session_id: str
    kind: Optional[str] = None
    key: Optional[str] = None


class MemoryRememberRequest(BaseModel):
    session_id: str
    kind: Literal["profile", "progress", "note"] = "note"
    key: str
    content: str


class QuestAdvanceRequest(BaseModel):
    session_id: str
    message: Optional[str] = None
    request_id: Optional[str] = Field(default=None, max_length=80)
    expected_status: Optional[str] = None
