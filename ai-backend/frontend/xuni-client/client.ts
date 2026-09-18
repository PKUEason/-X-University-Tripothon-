/**
 * X University AI Backend · 前端客户端封装
 *
 * 纯 TypeScript + fetch，无第三方依赖；兼容所有现代浏览器（含 Three.js 前端工程）。
 * 所有方法都封装了后端契约，前端业务层不要直接拼 URL / 解析 SSE。
 *
 * 快速开始：
 *   const xuni = new XUniversityClient("http://127.0.0.1:8000/api");
 *   const { session_id } = await xuni.createSession({ goal: "两周入门扩散模型" });
 *   const result = await xuni.streamClarify(
 *     { session_id, message: "我有 PyTorch 基础，每天 3 小时" },
 *     { onToken: (d) => appendToChat(d) }
 *   );
 *   if (result.ready) {
 *     const { roadmap } = await xuni.streamRoadmap({ session_id }, { onStatus: setLoadingText });
 *   }
 */
import type {
  ApiErrorBody,
  ClarifyEvent,
  ClarifyHandlers,
  ClarifyInput,
  ClarifyResult,
  CreateSessionInput,
  LabGuidanceResult,
  LabInput,
  LibraryRetrieveResult,
  ProfessorChatInput,
  ProfessorEvent,
  ProfessorHandlers,
  ProfessorResult,
  ProgressInput,
  ProgressResult,
  RetrieveInput,
  RoadmapEvent,
  RoadmapHandlers,
  RoadmapResult,
  SessionCreated,
  SessionOnlyInput,
  SessionSnapshot,
  TaskStatus,
} from "./types";

export * from "./types";

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** SSE 事件基类：后端 data 里一定有 type 字段 */
type AnySseEvent = ClarifyEvent | RoadmapEvent | ProfessorEvent;

const DEFAULT_BASE = "http://127.0.0.1:8000/api";

export class XUniversityClient {
  private readonly base: string;

  constructor(baseURL: string = DEFAULT_BASE) {
    this.base = baseURL.replace(/\/+$/, "");
  }

  // ============ 会话 ============

  /** 创建会话，返回 session_id（3D 世界进入时的第一步） */
  async createSession(input: CreateSessionInput = {}): Promise<SessionCreated> {
    return this.request<SessionCreated>("/session/create", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  /** 会话快照：goal / state / roadmap / 全部消息，用于恢复 3D 场景状态 */
  async getSession(sessionId: string): Promise<SessionSnapshot> {
    return this.request<SessionSnapshot>(`/session/${encodeURIComponent(sessionId)}`);
  }

  /** 更新任务状态，驱动场景中任务点亮/解锁 */
  async updateProgress(sessionId: string, taskId: string, status: TaskStatus): Promise<ProgressResult> {
    const body: ProgressInput = { task_id: taskId, status };
    return this.request<ProgressResult>(`/session/${encodeURIComponent(sessionId)}/progress`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  // ============ Scholar：目标澄清（SSE 流式） ============

  /**
   * 目标澄清对话。resolve 时机：收到 done 事件。
   * 返回聚合结果；流式文本通过 handlers.onToken 实时渲染。
   */
  async streamClarify(input: ClarifyInput, handlers: ClarifyHandlers = {}, signal?: AbortSignal): Promise<ClarifyResult> {
    const result: ClarifyResult = { text: "", ready: false, fallback: false };
    await this.streamPost<ClarifyEvent>("/scholar/clarify", input, (ev) => {
      switch (ev.event) {
        case "token":
          result.text += ev.data.delta;
          handlers.onToken?.(ev.data.delta);
          break;
        case "ready":
          result.ready = ev.data.ready;
          handlers.onReady?.(ev.data.ready);
          break;
        case "fallback":
          result.fallback = true;
          handlers.onFallback?.(ev.data.reason);
          break;
        case "error":
          result.error = ev.data.message;
          handlers.onError?.(ev.data.message);
          break;
        case "done":
          break;
      }
    }, signal);
    return result;
  }

  // ============ Scholar：路线图（SSE 流式） ============

  /** 生成学习路线图。roadmap 事件返回完整路线，前端可直接渲染 3D 任务节点。 */
  async streamRoadmap(input: SessionOnlyInput, handlers: RoadmapHandlers = {}, signal?: AbortSignal): Promise<RoadmapResult> {
    const result: RoadmapResult = { roadmap: null as unknown as RoadmapResult["roadmap"], fallback: false };
    await this.streamPost<RoadmapEvent>("/scholar/roadmap", input, (ev) => {
      switch (ev.event) {
        case "status":
          handlers.onStatus?.(ev.data.stage);
          break;
        case "roadmap":
          result.roadmap = ev.data.roadmap;
          handlers.onRoadmap?.(ev.data.roadmap);
          break;
        case "fallback":
          result.fallback = true;
          handlers.onFallback?.(ev.data.reason);
          break;
        case "error":
          result.error = ev.data.message;
          handlers.onError?.(ev.data.message);
          break;
        case "done":
          break;
      }
    }, signal);
    if (!result.roadmap) {
      throw new ApiError(502, "路线图流结束但未收到 roadmap 事件（后端异常）");
    }
    return result;
  }

  // ============ Library：资料检索 ============

  /** 图书馆检索（Phase 1 精选语料；Phase 2 升级向量 RAG 后返回结构不变） */
  async libraryRetrieve(input: RetrieveInput): Promise<LibraryRetrieveResult> {
    return this.request<LibraryRetrieveResult>("/library/retrieve", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  // ============ Professor：答疑（SSE 流式） ============

  /** AI Professor 答疑，自动携带路线图与当前任务上下文 */
  async streamProfessorChat(input: ProfessorChatInput, handlers: ProfessorHandlers = {}, signal?: AbortSignal): Promise<ProfessorResult> {
    const result: ProfessorResult = { text: "", fallback: false };
    await this.streamPost<ProfessorEvent>("/professor/chat", input, (ev) => {
      switch (ev.event) {
        case "token":
          result.text += ev.data.delta;
          handlers.onToken?.(ev.data.delta);
          break;
        case "fallback":
          result.fallback = true;
          handlers.onFallback?.(ev.data.reason);
          break;
        case "error":
          result.error = ev.data.message;
          handlers.onError?.(ev.data.message);
          break;
        case "done":
          break;
      }
    }, signal);
    return result;
  }

  // ============ Lab：实践指导 ============

  /** 实验室实践指导（结构化 JSON） */
  async labGuidance(input: LabInput): Promise<LabGuidanceResult> {
    return this.request<LabGuidanceResult>("/lab/guidance", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  // ============ 内部实现 ============

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const resp = await fetch(`${this.base}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    });
    if (!resp.ok) {
      throw await this.toApiError(resp);
    }
    return (await resp.json()) as T;
  }

  /** 发 POST 并流式消费 SSE 文本，逐事件回调 */
  private async streamPost<TEvent extends AnySseEvent>(
    path: string,
    body: object,
    onEvent: (ev: TEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    const resp = await fetch(`${this.base}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    if (!resp.ok) {
      throw await this.toApiError(resp);
    }
    await readSseStream(resp, (event, data) => {
      onEvent({ event, data } as TEvent);
    }, signal);
  }

  private async toApiError(resp: Response): Promise<ApiError> {
    let message = `${resp.status} ${resp.statusText}`;
    try {
      const body = (await resp.json()) as ApiErrorBody;
      if (body.detail) message = body.detail;
    } catch {
      /* 非 JSON 响应体，保留默认消息 */
    }
    return new ApiError(resp.status, message);
  }
}

/**
 * 把 fetch 响应体按 SSE 协议逐帧读出：
 *   event: xxx
 *   data: {...}
 *   (空行)
 */
export async function readSseStream(
  resp: Response,
  onEvent: (event: string, data: unknown) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (!resp.body) {
    throw new ApiError(502, "响应没有 body，无法读取流");
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let eventName = "";
  const dataLines: string[] = [];

  const flush = () => {
    if (!eventName) return;
    const raw = dataLines.join("\n");
    const name = eventName; // 先取事件名，再清空状态，避免把空串传进回调
    dataLines.length = 0;
    eventName = "";
    if (!raw) return;
    try {
      onEvent(name, JSON.parse(raw));
    } catch {
      // 坏帧直接跳过，不中断流
    }
  };

  const onAbort = () => {
    void reader.cancel().catch(() => undefined);
  };
  signal?.addEventListener("abort", onAbort, { once: true });

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let nl: number;
      while ((nl = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, nl).replace(/\r$/, "");
        buffer = buffer.slice(nl + 1);
        if (line === "") {
          flush();
          continue;
        }
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trim());
        }
        // 忽略注释行 / retry 行
      }
    }
    buffer += decoder.decode();
    if (buffer.trim()) {
      const line = buffer.replace(/\r$/, "");
      if (line === "") flush();
      else if (line.startsWith("event:")) eventName = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      flush();
    }
  } finally {
    signal?.removeEventListener("abort", onAbort);
  }
}
