# X University · 3D 前端对接指南（给全栈同学）

后端接口契约见根目录 `README.md`；**本文件只回答一个问题：3D 场景里每一步该调什么、事件来了怎么用**。

配套物料（本目录）：
- `xuni-client/` —— 类型安全的 TS 客户端，**所有请求都走它，不要手拼 URL / 手解析 SSE**
- `examples/usage.ts` —— 纯 TS 黄金路径示例
- `examples/react-example.tsx` —— React 接线示例（X Gate 面板）
- `examples/sample-roadmap.json` —— **真实结构的路线图样例，脱离后端也能拿来渲染测试**
- `examples/verify-live.ts` —— 连通性自检脚本（需后端运行）

---

## 0. 一分钟架构

```
Three.js 场景(你)  ──XUniversityClient──▶  FastAPI 后端  ──▶  DeepSeek
  4 个空间              types.ts 约束          MOCK/降级兜底
  X Gate / Library / Professor Office / Lab
```

- 后端默认 `http://127.0.0.1:8000/api`，换端口改 `new XUniversityClient("...")` 参数；
- **SSE 全部用 fetch 流式**（客户端已封装），不要在浏览器里用 `EventSource`（它只支持 GET）；
- 所有请求都带 `session_id`——**进入游戏先 `createSession`，把 id 存全局**。

### 0.1 向量 RAG 升级（第二阶段，前端零改动）

Library 检索已从纯 BM25 升级为 **Hybrid = BM25 + 向量语义（RRF 融合）**：
- `documents` 结构与字段完全不变，`engine` 字段新取值：
  - `hybrid-v2(bm25+api:BAAI/bge-m3)` — 真语义混合检索（已配 embedding API）；
  - `hybrid-v2(bm25+hash-deterministic-256)` — 未配置后端时的兜底（管线可跑，但无语义增益）；
  - `bm25-v1` — 纯关键词（向量路故障自动降级，此时 `notice` 会说明原因）；
  - `curated-v1` — MOCK 模式 / 零命中兜底。
- 前端只需把 `engine` / `notice` 当作调试信息（可不展示），**无需任何对接改动**。
- 启用真语义（2 分钟，免费）：到 https://siliconflow.cn 注册（送额度）→ 控制台新建 API 密钥 →
  在后端 `.env` 填：
  ```
  EMBEDDING_PROVIDER=api
  EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
  EMBEDDING_API_KEY=<硅基流动密钥>
  EMBEDDING_MODEL=BAAI/bge-m3
  ```
  重启后端即可。不想注册也可本地离线方案：`pip install -r requirements-rag.txt` +
  `EMBEDDING_PROVIDER=fastembed`（首次自动下载约 100MB 模型）。

### 0.2 arXiv 实时检索（第三阶段，前端零改动）

Library 响应新增两个 additive 字段，分区展示「本地资料 + 最新论文」：
- `arxiv_papers: [{title, authors, year, url, snippet}]` — arXiv 最新论文（默认 3 篇）；
- `arxiv_status: "ok" | "failed" | "disabled"` — 失败时 `arxiv_papers` 为空，本地 `documents` 不受影响。
- 前端可在资料区下方加一个「最新论文」卡片组；不展示也完全兼容（字段被忽略）。
- MOCK 模式返回预制扩散模型论文，演示稳定；真实模式调 arXiv 官方 API（免费、8 秒超时降级）。

## 1. 空间 ↔ 接口映射

| 3D 空间 | 进入时调用 | 交互中调用 | 驱动什么 |
|---|---|---|---|
| X Gate（入学之门） | `createSession` | `streamClarify` → `streamRoadmap` | 对话打字机、路线图展示 |
| Library（图书馆） | `libraryRetrieve({query})` | 点资料卡片打开 URL | 资料列表、知识卡片 |
| Professor Office（教授办公室） | `streamProfessorChat({task_id})` | 继续追问 | 对话打字机 |
| Research Lab（实验室） | `labGuidance({task_id})` | — | 步骤清单、实践指导 |
| （Quest 编排模式） | `getQuest` / `advanceQuest` | 同左（见 2.1） | 一条线驱动全部空间切换 |
| （任意空间） | — | `updateProgress(task_id, status)` | 任务点亮/解锁 |

> 关键点：**任务（task）是贯穿一切的挂载点**。路线图的每个任务都带 `space` + `id`，前端在进入某空间时带上 `task_id` 调 Professor / Lab，后端会自动把该任务的上下文喂给 AI。角色进入某个空间 = 正在执行该空间对应的任务。

## 2. 黄金路径时序（第一版 Demo 就做这条）

```
1. 玩家进 X University → 调 createSession（后端返回 session_id）
2. X Gate 对话：streamClarify 逐字输出 → 收到 ready=true → 显示"生成路线"按钮
3. 点按钮：streamRoadmap（onStatus 显示 loading 文案）→ 拿到 roadmap JSON
4. 按 roadmap.stages[].space 依次解锁 4 个传送门（第一版可全部开放）
5. 玩家进入 Library：libraryRetrieve({task_id}) → 展示资料卡
6. 玩家进入 Professor Office：streamProfessorChat({task_id}) → 答疑
7. 玩家进入 Lab：labGuidance({task_id}) → 步骤清单
8. 每完成一个任务：updateProgress(task_id, "done") → 3D 场景里任务状态同步
```

**ready 信号说明**：后端给出 `ready=true` 表示目标已澄清，可自动衔接生成路线；但 `streamRoadmap` 本身不依赖 ready——**给澄清区加一个"直接生成路线"按钮**作为兜底，演示现场最稳。

### 2.1 Quest 编排模式（第二阶段推荐，一条线走完整产品）

除了按空间分别调接口，后端提供了状态机编排，前端只需反复调 `advanceQuest`：

```ts
// 1. 首次：带学生目标（内部走 Scholar 澄清）
let r = await xuni.advanceQuest(
  { session_id, message: "我有 PyTorch 基础，每天 3 小时，想跑通文生图 Demo" },
  {
    onQuest: (status, msg) => {
      // status: clarifying → quest_ready → library → professor → lab → project_ready
      movePlayerTo(status);       // 驱动 3D 角色/镜头移动
      showSpaceHint(msg);
    },
    onToken: (d) => appendChat(d),
    onRoadmap: (rm) => renderRoadmap(rm),
    onReferences: (refs) => renderReferenceCards(refs),
    onLabGuidance: (g) => renderSteps(g),
    onProject: (card) => showProjectCard(card),   // 最终成果弹窗
  },
);
// 2. 若 r.status === "clarifying"（模型还要追问），带补充信息再调一次
// 3. 之后玩家每完成当前空间交互（读完资料/研讨完），无 message 再调 advanceQuest 即可推进
```

- 状态 ↔ 场景映射：`library`→Library、`professor`→Professor Office、`lab`→X Lab、`project_ready`→Project Card 弹窗；
- `getQuest(session_id)` 可随时查当前状态与已完成任务，刷新页面后用它恢复场景；
- Memory 是自动的（画像提取/卡点记录），想在 UI 里展示"AI 记得你"，调 `recallMemory(session_id)`。

## 3. SSE 事件 → UI 的推荐写法

| 事件 | UI 行为 |
|---|---|
| `token` `{delta}` | 追加到对话气泡（打字机效果） |
| `status` `{stage}` | 路线图生成中的 loading 文案 |
| `roadmap` `{roadmap}` | 渲染路线图（4 个阶段 + 任务列表） |
| `ready` `{ready}` | `true` 时显示"生成路线"按钮 |
| `references` `{references}` | 渲染"参考资料"卡片列表（title/url 可点击） |
| `quest` `{status, message}` | Quest 空间切换：驱动角色/镜头移动到对应 3D 场景 |
| `lab_guidance` `{guidance}` | Lab 步骤清单 |
| `project` `{project}` | 弹出最终 Project Card（成果/技术栈/下一步） |
| `fallback` `{reason}` | 顶部 toast："演示模式"（后端 API 挂了，数据是预制的，流程不中断） |
| `error` `{message}` | 错误提示（仅当后端关闭了降级时出现） |
| `done` | 流结束（客户端在 done 后 resolve，业务层无需处理） |

打字机最小实现（React）：

```tsx
const [chat, setChat] = useState("");
await xuni.streamClarify({ session_id, message }, {
  onToken: (d) => setChat((prev) => prev + d),
});
```

取消流（玩家离开空间时）：`const ctrl = new AbortController();` 传给 `stream*` 第三个参数，离开时 `ctrl.abort()`。

## 4. 任务状态 → 3D 表现建议

`status: "pending" | "in_progress" | "done"`（由 `updateProgress` 更新，服务端持久化）：

| 状态 | 场景表现建议 |
|---|---|
| pending | 任务图标灰色、未解锁 |
| in_progress | 角色所在空间的任务高亮、可交互 |
| done | 任务点亮 + 完成粒子/音效，解锁下一空间传送门 |

恢复现场：进入游戏后调 `getSession(session_id)`，快照里有完整 `roadmap`（含每个任务 status），**刷新页面/重进场景直接按快照渲染，不丢进度**。

## 5. 联调 checklist（9/21 验收前逐条勾）

- [ ] 进入场景 → `createSession` → 拿到 session_id
- [ ] X Gate 对话流式打字，`ready=true` 后能生成路线
- [ ] 路线图渲染：4 个阶段、任务卡片、空间顺序 gate→library→professor_office→lab
- [ ] 进入 Library 能拿到资料列表，点卡片能开 URL
- [ ] Professor 对话流式，回复与当前任务相关
- [ ] Lab 拿到步骤/产出物清单
- [ ] 完成任务 → 场景任务状态点亮 → 刷新页面后状态保持（getSession / getQuest 恢复）
- [ ] Quest 编排：advanceQuest 能一路推进到 project_ready，quest 事件驱动场景切换
- [ ] Professor 回答后出现 references 资料卡；Lab 结束弹出 Project Card
- [ ] 断网/后端故障时：出现"演示模式"提示，流程仍能走完（fallback）
- [ ] 真机（手机）联调：HOST=0.0.0.0 + API_TOKEN（见根 README「路演接入」）

## 6. 常见坑

1. **CORS 报错看不到具体信息**：先确认后端 `HOST` 配置与访问地址一致；浏览器跨域时 401/404 会被吞成"跨域错误"，先用 curl 验证接口本身。
2. **别用 EventSource**：后端 SSE 是 POST 发起的，浏览器 EventSource 只支持 GET。用客户端封装的 fetch 流式。
3. **`sample-roadmap.json` 的结构和线上完全一致**：可以先拿它做场景渲染，后端随时可换真实数据，前端零改动。
4. **演示现场网络不稳**：后端 `.env` 设 `MOCK_MODE=true` 即走预制数据（不依赖 DeepSeek/网络），前端代码一行不用改。
