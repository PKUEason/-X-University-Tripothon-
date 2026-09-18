# xuni-client · X University 前端 AI SDK

给 3D 前端（Three.js / React / 任意 TS 工程）对接 AI 后端的类型安全客户端。**纯 TS + fetch，零第三方运行时依赖**。

## 目录

```
frontend/
├── xuni-client/
│   ├── types.ts      # 契约类型（与后端 app/api/schemas.py 同步）
│   ├── client.ts     # XUniversityClient：全部接口封装 + SSE 流式解析
│   └── index.ts      # 统一出口
├── examples/
│   ├── usage.ts          # 纯 TS 完整黄金路径示例（参与 tsc 检查）
│   └── react-example.tsx # React 组件接线示例
├── package.json          # typecheck 脚本
└── tsconfig.json
```

## 使用

```bash
# 类型检查（开发期随时跑）
cd frontend
npm install        # 只需 typescript
npm run typecheck
```

```ts
import { XUniversityClient } from "./xuni-client"; // 或按你的工程导入路径

const xuni = new XUniversityClient("http://127.0.0.1:8000/api");

// 创建会话
const { session_id } = await xuni.createSession({ goal: "两周入门扩散模型" });

// Scholar 澄清（SSE 流式）
const r = await xuni.streamClarify(
  { session_id, message: "我有 PyTorch 基础" },
  { onToken: (d) => appendText(d), onReady: (ok) => console.log("澄清完成", ok) },
);

// 路线图（渲染 3D 空间与任务节点）
const { roadmap } = await xuni.streamRoadmap({ session_id }, { onStatus: setLoading });
roadmap.stages.forEach((s) => console.log(s.space, s.tasks.length));

// 其它
await xuni.libraryRetrieve({ session_id, query: "DDPM" });
await xuni.streamProfessorChat({ session_id, message: "讲讲反向扩散", task_id: "t-3-1" });
await xuni.labGuidance({ session_id, task_id: "t-4-1" });
await xuni.updateProgress(session_id, "t-1-1", "done");
```

## API 一览

| 方法 | 后端端点 | 说明 |
|---|---|---|
| `createSession(input?)` | POST /session/create | 返回 session_id |
| `getSession(id)` | GET /session/{id} | 快照：roadmap/messages/state |
| `updateProgress(id, taskId, status)` | POST /session/{id}/progress | pending / in_progress / done |
| `streamClarify(input, handlers?, signal?)` | POST /scholar/clarify (SSE) | token / ready / fallback / error |
| `streamRoadmap(input, handlers?, signal?)` | POST /scholar/roadmap (SSE) | status / roadmap / fallback / error |
| `libraryRetrieve(input)` | POST /library/retrieve | 普通 JSON |
| `streamProfessorChat(input, handlers?, signal?)` | POST /professor/chat (SSE) | token / fallback / error |
| `labGuidance(input)` | POST /lab/guidance | 结构化 JSON |

- 所有 `stream*` 方法在收到 `done` 事件时 resolve，返回聚合结果（文本 / 路线图 / 降级标记）；
- `handlers` 全部可选，可只传 `onToken` 做流式渲染；
- 传 `AbortSignal` 可中途取消（如用户离开空间）；
- 非 2xx 响应抛 `ApiError`（含后端的 `detail`，如 `404 session 不存在`、`422 状态非法`）。

## 与后端同步约定

- 后端契约以 `app/api/schemas.py` 为准；`types.ts` 是它的 TS 镜像，字段名/枚举保持一一对应；
- 后端变更契约时：改 `schemas.py` → 同步改 `types.ts` → `npm run typecheck` 兜底；
- SSE 事件：`event:` 行是事件名，`data:` 行是 JSON 字符串（内含 `type` 字段，与事件名一致，可任取其一）。

## 注意事项

- 开发期后端跑 `python run.py`，前端默认 base 为 `http://127.0.0.1:8000/api`；换端口改构造函数参数；
- 生产/演示环境如跨域，后端已开 CORS（`CORS_ORIGINS=*`），无需代理；浏览器跨域建议用 Vite/Webpack dev proxy 或同源部署；
- `fallback` 事件表示后端已自动降级到演示数据（如 API 余额不足/断网），UI 可提示"演示模式"，流程不中断。
