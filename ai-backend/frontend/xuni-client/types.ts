/**
 * X University AI Backend · 前端契约类型
 *
 * 与后端 app/api/schemas.py 一一对应，保持同步（字段名/可选性/枚举值）。
 * 后端契约变更时，本文件是唯一需要跟着改的前端文件。
 */

// ---------------- 领域枚举 ----------------

/** 3D 世界四个空间，与前端场景 key 对应 */
export type Space = "gate" | "library" | "professor_office" | "lab";

/** 任务状态：由 /session/{id}/progress 更新，驱动场景中任务点亮/解锁 */
export type TaskStatus = "pending" | "in_progress" | "done";

/** 资料类型 */
export type ResourceType = "paper" | "article" | "video" | "course" | "tool";

// ---------------- 路线图领域模型 ----------------

export interface Resource {
  title: string;
  type: ResourceType;
  /** 模型可能给空串，前端按无链接处理 */
  url: string;
}

export interface TaskNode {
  id: string;
  title: string;
  description: string;
  space: Space;
  deliverable: string;
  resources: Resource[];
  status: TaskStatus;
}

export interface Stage {
  id: string;
  name: string;
  space: Space;
  objective: string;
  tasks: TaskNode[];
}

export interface Roadmap {
  title: string;
  summary: string;
  estimated_duration: string;
  stages: Stage[];
  final_outcome: string;
}

// ---------------- 会话 ----------------

export interface CreateSessionInput {
  goal?: string;
  nickname?: string;
}

export interface SessionCreated {
  session_id: string;
  goal?: string;
  nickname?: string;
}

/** GET /session/{id} 的完整快照 */
export interface SessionSnapshot {
  session: {
    session_id: string;
    goal: string | null;
    nickname: string | null;
    created_at: string;
    updated_at: string;
  };
  state: Record<string, unknown>;
  roadmap: Roadmap | null;
  messages: SessionMessage[];
}

export interface SessionMessage {
  id: number;
  session_id: string;
  role: "user" | "assistant";
  agent: string | null;
  task_id: string | null;
  content: string;
  created_at: string;
}

export interface ProgressInput {
  task_id: string;
  status: TaskStatus;
}

export interface ProgressResult {
  ok: boolean;
  task_id: string;
  status: TaskStatus;
}

// ---------------- 请求体（与后端 Pydantic 模型一致） ----------------

export interface ClarifyInput {
  session_id: string;
  message: string;
}

export interface SessionOnlyInput {
  session_id: string;
}

export interface ProfessorChatInput extends SessionOnlyInput {
  message: string;
  stage_id?: string;
  task_id?: string;
}

export interface RetrieveInput extends SessionOnlyInput {
  query: string;
  stage_id?: string;
  task_id?: string;
  top_k?: number;
}

export interface LabInput extends SessionOnlyInput {
  stage_id?: string;
  task_id?: string;
}

// ---------------- 非 SSE 响应体 ----------------

export interface LibraryDocument {
  title: string;
  type: ResourceType;
  url: string;
  snippet: string;
}

export interface LibraryRetrieveResult {
  documents: LibraryDocument[];
  engine: string;
  notice: string;
}

export interface LabGuidanceResult {
  overview: string;
  steps: { title: string; detail: string }[];
  deliverables: string[];
  pitfalls: string[];
  tools: string[];
  /** LLM 故障降级时出现 */
  degraded?: boolean;
  degraded_reason?: string;
}

export interface ApiErrorBody {
  detail?: string;
}

// ---------------- SSE 事件（data 统一含 type 字段） ----------------

export interface SseEnvelope<TType extends string, TData extends Record<string, unknown> = Record<string, unknown>> {
  /** 事件名，与 event: 行一致 */
  event: TType;
  /** data: 行 JSON.parse 后的内容 */
  data: TData;
}

/** Scholar 澄清事件 */
export type ClarifyEvent =
  | SseEnvelope<"token", { type: "token"; delta: string }>
  | SseEnvelope<"ready", { type: "ready"; ready: boolean }>
  | SseEnvelope<"fallback", { type: "fallback"; reason: string }>
  | SseEnvelope<"error", { type: "error"; message: string }>
  | SseEnvelope<"done", { type: "done" }>;

/** Scholar 路线图事件 */
export type RoadmapEvent =
  | SseEnvelope<"status", { type: "status"; stage: string }>
  | SseEnvelope<"roadmap", { type: "roadmap"; roadmap: Roadmap }>
  | SseEnvelope<"fallback", { type: "fallback"; reason: string }>
  | SseEnvelope<"error", { type: "error"; message: string }>
  | SseEnvelope<"done", { type: "done" }>;

/** Professor 答疑事件 */
export type ProfessorEvent =
  | SseEnvelope<"token", { type: "token"; delta: string }>
  | SseEnvelope<"fallback", { type: "fallback"; reason: string }>
  | SseEnvelope<"error", { type: "error"; message: string }>
  | SseEnvelope<"done", { type: "done" }>;

// ---------------- 流式结果（stream* 方法 resolve 时的聚合值） ----------------

export interface ClarifyResult {
  text: string;
  ready: boolean;
  fallback: boolean;
  error?: string;
}

export interface RoadmapResult {
  roadmap: Roadmap;
  fallback: boolean;
  error?: string;
}

export interface ProfessorResult {
  text: string;
  fallback: boolean;
  error?: string;
}

// ---------------- 回调处理器 ----------------

export interface ClarifyHandlers {
  onToken?: (delta: string) => void;
  onReady?: (ready: boolean) => void;
  onFallback?: (reason: string) => void;
  onError?: (message: string) => void;
}

export interface RoadmapHandlers {
  onStatus?: (stage: string) => void;
  onRoadmap?: (roadmap: Roadmap) => void;
  onFallback?: (reason: string) => void;
  onError?: (message: string) => void;
}

export interface ProfessorHandlers {
  onToken?: (delta: string) => void;
  onFallback?: (reason: string) => void;
  onError?: (message: string) => void;
}
