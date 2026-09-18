# X University · AI Backend

Tripothon 参赛项目「X University」的 AI 后端：学生进入 3D 未来大学后，由 **Scholar Agent** 澄清目标并生成学习路线，随后在 **Library / Professor Office / Research Lab** 三个空间中由不同 Agent 带学、带研、带做，直到产出成果。

- 模型：DeepSeek 官方 API（OpenAI 兼容），默认模型 `deepseek-flash`（V4 Flash），可切换 `deepseek-v4-pro`
- 框架：FastAPI + SSE 流式输出 + SQLite 会话记忆
- 内置 **mock 演示模式**与**故障自动降级**：断网、API 余额不足、超时时 Demo 不中断

---

## 1. 快速开始

```bash
# 1. 建议虚拟环境
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux

# 2. 安装依赖
pip install -r requirements.txt          # 日常开发：只约束直接依赖的上下界
# pip install -r requirements.lock.txt   # 路演/换机器：锁定全部版本，与验证基线完全一致

# 3. 配置（已提供 .env，密钥只放在 .env 中，切勿提交）
#    MOCK_MODE=true 可在无网络/无余额时跑完整黄金路径

# 4. 启动
python run.py
# 或：uvicorn app.main:app --reload
```

- 服务地址：http://127.0.0.1:8000
- 交互式文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

一键冒烟测试（另开终端，服务启动后执行）：

```bash
python scripts/smoke_test.py
```

### 依赖说明

- **HTTP 客户端全项目统一用 `httpx2`**。openai 3.x SDK 和 Starlette 的 `TestClient` 都已迁到 `httpx2`，
  本项目自己的 `scripts/smoke_test.py` 也用它。**不要再安装 `httpx`（0.x）**——否则 `site-packages`
  里会同时躺着两套客户端，排查问题时极易搞混（而且 `starlette.testclient` 检测到只有 `httpx` 时会发告警）。
- **`requirements.txt` 写 `>=x,<y` 而不是 `==`**：上界只用来挡跨大版本的静默漂移。
  曾经只写 `openai>=1.50`，实际被解析成 `3.14.1`（跨两个大版本）。要完全可复现的环境（路演当天、换机器）
  请用 `requirements.lock.txt`，它是「73 项测试 + 17 项冒烟全绿」的那套精确版本。

## 2. 环境变量（.env）

| 变量 | 说明 | 默认 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek 官方 API Key | 无（未配置时真实调用会失败并降级 mock） |
| `DEEPSEEK_BASE_URL` | API 地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 模型 ID | `deepseek-flash`（备选 `deepseek-v4-pro`） |
| `MOCK_MODE` | `true` 时全部走预制黄金路径 | `false` |
| `LLM_FALLBACK_TO_MOCK` | 真实调用失败时自动降级 mock | `true` |
| `DATA_DIR` | SQLite 数据目录 | `data` |
| `HOST` | 监听地址。`127.0.0.1` = 仅本机；手机/其他设备要连必须改 `0.0.0.0` | `127.0.0.1` |
| `PORT` | 监听端口 | `8000` |
| `RELOAD` | 热重载。路演时建议 `false`，避免文件变动触发重启 | `true` |
| `CORS_ORIGINS` | 允许的前端来源，逗号分隔；`*` 为全部（此时自动关闭 `allow_credentials`） | `*` |
| `API_TOKEN` | 可选鉴权。留空 = 不校验；设置后 `/api/*` 需带 `X-API-Token` 头 | 空（关闭） |
| `LLM_DAILY_CALL_LIMIT` | 每日真实 LLM 调用上限，超出**自动降级 mock**（不中断服务）；`0` = 不限 | `300` |
| `RATE_LIMIT_PER_MINUTE` | 单 IP 每分钟请求上限；`0` = 不限 | `120` |

> 演示建议：平时 `MOCK_MODE=false` 联调真实效果；路演当天若网络不稳，改 `MOCK_MODE=true`，走完全确定的黄金路径。

### 公网暴露前必读

**先把威胁模型摆正**：DeepSeek 的 key 只在服务器进程里，永远不会发给前端，所以「key 被偷」
基本不是主要风险（说明：本仓库为**私有团队仓库**，`.env` 已随仓库共享给协作者；严禁把它改为公开仓库，
比赛结束后请轮换 key）。真正的风险是
**你的后端被当成免费代理刷额度**：谁都能调，账单算你的。

所以防护要按这个顺序做：

**① 别急着上公网。** 本地 `127.0.0.1` 演示零风险。真要开隧道（ngrok / frp）或上云主机，
先读完下面三条。

**② 加一道门（鉴权）。**

```bash
# 生成一个随机 token，写进 .env 的 API_TOKEN
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

设置后：

- `/api/*` 全部要求请求头 `X-API-Token: <值>`（或 `Authorization: Bearer <值>`），否则返回 401；
- `/health` 与 `/docs` 不受影响，方便探活和调试；
- 前端只需在所有 `fetch` 里带上这个头（本地开发不设 `API_TOKEN` 时行为完全不变）。

**③ 装刹车（预算熔断 + 限流）。** 门挡不住 curl，刹车才是最后一道防线：

| 机制 | 行为 | 默认 |
|---|---|---|
| `LLM_DAILY_CALL_LIMIT` | 当天真实 LLM 调用达到上限后，**自动降级到 MOCK 黄金路径**——服务不中断，只是不再产生费用 | `300` 次 |
| `RATE_LIMIT_PER_MINUTE` | 单 IP 超过阈值返回 `429` + `Retry-After: 60`，`/health` 不受影响 | `120` 次/分钟 |

选「降级」而不是「拒绝」，是因为路演现场演示绝不能中断：额度被刷爆了，评委扫码依然能
走完整个流程，只是内容变成预制数据。这一点在 `tests/test_guard.py` 里有专门的回归测试。

**④ 盯住用量。** `/health` 直接暴露预算快照，随时能看出有没有人在刷：

```json
{ "llm_budget": { "day": "2026-09-17", "limit": 300, "used": 12, "remaining": 288, "rejected": 0 } }
```

**⑤ 给 key 设独立额度。** 在 DeepSeek 控制台为本项目单独建一个 key，额度与主账号隔离；
万一真出事，吊销它不影响别的项目。这是**唯一能兜住"前面全被绕过"的措施**，别省这一步。

> 关于 `API_TOKEN` 的诚实说明：token 写在前端等于公开，谁打开页面都能从 devtools 里看到。
> 它只能挡住「扫到端口就乱试」的人，挡不住有心人。真正的防线是**别把服务长期挂在公网**——
> 演示完就关隧道，或把 `HOST` 改回 `127.0.0.1`。
>
> 另外，`LLM_DAILY_CALL_LIMIT` 和 `RATE_LIMIT_PER_MINUTE` 都是**单进程内存**实现，重启即清零、
> 多实例不共享。路演和单机部署够用；要防有组织的滥用，得上 Redis + 网关层限流。

### 路演接入：手机 / 隧道

**第一道坎是监听地址**：服务默认只听 `127.0.0.1`，手机连你电脑的局域网 IP 会直接连不上——
跟鉴权没关系。先放开监听：

```bash
# 方式一：临时（单次启动有效）
HOST=0.0.0.0 python run.py

# 方式二：写进 .env（推荐，启动脚本不用改）
#   HOST=0.0.0.0
#   RELOAD=false
```

启动时会打印一张表，直接告诉你手机该访问哪个地址：

```
==============================================================
  X University AI Backend   model=deepseek-flash   mock=false
--------------------------------------------------------------
  本机访问    http://127.0.0.1:8000/docs
  局域网访问  http://192.168.1.23:8000/docs   <- 手机浏览器用这个
  接口鉴权    未启用
  热重载      开
==============================================================
```

**第二道坎是防火墙**：Windows 首次监听 `0.0.0.0` 会弹「允许访问」提示，要勾选专用网络；
如果当时点了取消，去「Windows 安全中心 → 防火墙和网络保护 → 允许应用通过防火墙」里放行 Python。

**第三道坎才是鉴权**。一旦监听 `0.0.0.0`（或走 ngrok / frp 隧道），同网段或公网上任何人都能
调用接口、烧你的 DeepSeek 额度。此时：

```bash
# 1. 生成 token，写进 .env 的 API_TOKEN
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```js
// 2. 前端加一个统一的请求封装，所有调用都走它（SSE 也一样）
const API_BASE = "http://192.168.1.23:8000/api";
const API_TOKEN = "刚才生成的那串";   // 本地未设 API_TOKEN 时留空即可

function api(path, init = {}) {
  return fetch(API_BASE + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(API_TOKEN ? { "X-API-Token": API_TOKEN } : {}),
      ...(init.headers || {}),
    },
  });
}
```

> 说句实在话：token 写在前端等于公开，只能挡住「扫到端口就乱试」的人，挡不住有心人。
> 真正的防线是**别把服务长期挂在公网**——演示完就关掉隧道，或把 `HOST` 改回 `127.0.0.1`。

如果 `CORS_ORIGINS` 配的不是 `*` 而是具体来源，记得把手机 / 前端的地址也加进去，
否则浏览器会拦在预检那一步。

## 3. 接口契约（前端对接看这里）

Base URL：`http://127.0.0.1:8000/api`

### 3.1 会话

**POST `/session/create`** → 创建会话
```json
// 请求
{ "goal": "我想用两周入门扩散模型，做出图像生成 Demo", "nickname": "Eason" }
// 响应
{ "session_id": "a1b2c3d4e5f6", "goal": "...", "nickname": "Eason" }
```

**GET `/session/{session_id}`** → 会话快照（goal / state / roadmap / 全部消息）

**POST `/session/{session_id}/progress`** → 更新任务状态
```json
{ "task_id": "t-1-1", "status": "done" }   // pending | in_progress | done
```

### 3.2 Scholar Agent（SSE 流式）

SSE 说明：响应为 `text/event-stream`，每条消息含 `event:` 与 `data:`（JSON 字符串）。

**POST `/scholar/clarify`** — 目标澄清对话
```json
{ "session_id": "...", "message": "我有 PyTorch 基础，每天 3 小时" }
```
事件序列：
| event | data 示例 | 说明 |
|---|---|---|
| `token` | `{"delta": "很好，"}` | 流式文本，前端逐字渲染 |
| `ready` | `{"ready": false}` | Scholar 是否认为目标已澄清；`true` 后前端可调用 roadmap |
| `fallback` | `{"reason": "..."}` | （仅降级时）真实 API 失败，已切 mock |
| `error` | `{"message": "..."}` | 不可恢复错误（关闭降级时） |
| `done` | `{"type":"done"}` | 结束 |

**POST `/scholar/roadmap`** — 生成路线图
```json
{ "session_id": "..." }
```
事件序列：`status`（进度文案，可做加载动画）→ `roadmap`（完整 JSON）→ `done`。

`roadmap` 事件 data 结构（**前端 3D 空间与任务节点直接按此渲染**）：
```json
{
  "roadmap": {
    "title": "两周入门扩散模型……",
    "summary": "……",
    "estimated_duration": "2 周（每天约 3 小时）",
    "stages": [
      {
        "id": "stage-1",
        "name": "X Gate · 目标确认",
        "space": "gate",
        "objective": "……",
        "tasks": [
          {
            "id": "t-1-1",
            "title": "基础自评与目标锁定",
            "description": "……",
            "space": "gate",
            "deliverable": "学习目标声明",
            "resources": [{ "title": "PyTorch 安装", "type": "tool", "url": "https://…" }],
            "status": "pending"
          }
        ]
      }
    ],
    "final_outcome": "可运行 Demo + 作品集 + 项目报告"
  }
}
```
- `space` 枚举固定为：`gate` / `library` / `professor_office` / `lab`，与 3D 场景一一对应；
- 阶段空间顺序固定为 gate → library → professor_office → lab；
- 任务 `status` 由 `/session/{id}/progress` 更新，可用于驱动场景中任务点亮/解锁。

### 3.3 Library

**POST `/library/retrieve`** — 资料检索（普通 JSON）
```json
{ "session_id": "...", "query": "DDPM 扩散模型论文", "top_k": 5 }
```
```json
{
  "documents": [{ "title": "...", "type": "paper", "url": "https://arxiv.org/…", "snippet": "……" }],
  "engine": "curated-v1",
  "notice": "Phase 1 精选语料；Phase 2 升级为向量 RAG + arXiv 实时检索"
}
```

### 3.4 AI Professor（SSE 流式）

**POST `/professor/chat`**
```json
{ "session_id": "...", "message": "请讲一下反向扩散过程",
  "stage_id": "stage-3", "task_id": "t-3-1" }
```
事件序列：`token`（多次）→ 可选 `fallback`/`error` → `done`。Professor 自动携带路线图与当前任务上下文。

### 3.5 Research Lab

**POST `/lab/guidance`** — 结构化实践指导（普通 JSON）
```json
{ "session_id": "...", "stage_id": "stage-4", "task_id": "t-4-1" }
```
```json
{
  "overview": "……",
  "steps": [{ "title": "准备环境", "detail": "……" }],
  "deliverables": ["可复现脚本", "作品集"],
  "pitfalls": ["首次下载模型数 GB，提前缓存"],
  "tools": ["diffusers", "transformers"]
}
```

## 4. 前端最小调用示例（SSE 用 fetch 读取）

```js
const resp = await fetch("http://127.0.0.1:8000/api/scholar/clarify", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ session_id, message }),
});
const reader = resp.body.getReader();
const decoder = new TextDecoder();
let buffer = "";
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  // 按行解析 "event: xxx" 与 "data: {...}"，JSON.parse(data) 后按 event 类型渲染
}
```
> 若前端用 EventSource 不便发 POST，可后续按需补 GET 版本；当前统一 POST + fetch 流式读取。

## 5. 测试

分三层，**日常改代码只跑第 1 层**（约 6 秒，不联网、不花钱、结果确定）：

```bash
# 1. 单元 + 契约 + 降级（pytest，全量 MOCK 模式，无需启动服务）
pip install -r requirements-dev.txt
pytest                      # 139 项

# 2. 端到端冒烟（需先 python run.py 起服务；会真实调用 DeepSeek）
python scripts/smoke_test.py

# 3. 演示彩排（改 .env 里 MOCK_MODE=true 后重启，再跑第 2 层）
```

| 测试文件 | 覆盖内容 |
|---|---|
| `tests/test_json_utils.py` | 从模型输出里抠 JSON：代码块、前后夹解释、尾逗号、字符串内的花括号 |
| `tests/test_scholar_units.py` | 流式 `<<<READY:>>>` 标记过滤（含跨 chunk 切断）、路线图规范化 + Pydantic 契约 |
| `tests/test_store.py` | SQLite 会话 / 消息 / 路线图 / 任务状态读写 |
| `tests/test_api_contract.py` | 8 个端点的状态码、SSE 事件序列、响应结构 |
| `tests/test_fallback.py` | 断网 / 超时 / 余额不足 / JSON 残缺时的降级路径（**演示保险，重点回归**） |
| `tests/test_librarian.py` | Library 检索契约、Phase 2 的 RAG 开关行为 |
| `tests/test_hardening.py` | CORS 收敛、API Token 开关、监听地址、lifespan 生命周期 |
| `tests/test_guard.py` | 每日预算熔断（含并发不超支）、单 IP 限流、对外错误脱敏 |

测试基座在 `tests/conftest.py`：导入 app 前注入 `MOCK_MODE=true`、临时 `DATA_DIR` 和空 API Key，
所以 pytest 既不会污染 `data/xuniversity.db`，也绝不会误打真实接口。

> 冒烟测试 `scripts/smoke_test.py` 已支持自定义地址：`python scripts/smoke_test.py http://127.0.0.1:8123`。

## 6. 目录结构

```
XUniversity/
├── run.py                     # 启动入口
├── requirements.txt           # 直接依赖（带上下界）
├── requirements.lock.txt      # 完整版本快照（路演/换机器复现用）
├── .env / .env.example
├── app/
│   ├── main.py                # FastAPI、CORS、可选 API Token 守卫、生命周期
│   ├── config.py              # 环境配置
│   ├── api/
│   │   ├── schemas.py         # 前后端契约（Pydantic）
│   │   └── routes.py          # HTTP/SSE 路由
│   ├── agents/
│   │   ├── llm.py             # DeepSeek 封装（chat / stream_text / chat_json）
│   │   ├── scholar.py         # Scholar：澄清 + 路线图（含 JSON 规范化/降级）
│   │   ├── professor.py       # AI Professor 答疑
│   │   ├── lab_mentor.py      # Lab 实践指导
│   │   └── librarian.py       # Library 检索（Phase 2 接 RAG）
│   ├── core/
│   │   ├── prompts.py         # 所有提示词（迭代效果只改这里）
│   │   ├── json_utils.py      # 稳健 JSON 提取
│   │   └── guard.py           # 成本防护：每日预算熔断 / 单 IP 限流 / 错误脱敏
│   ├── memory/store.py        # SQLite：会话/消息/路线图/任务状态
│   └── mock_data/golden_path.py  # 黄金路径预制数据（扩散模型主题）
├── tests/                     # pytest：单元 / 契约 / 降级（MOCK 模式，不联网）
│   ├── conftest.py            # 环境隔离基座 + 公共 fixture
│   ├── test_json_utils.py
│   ├── test_scholar_units.py
│   ├── test_store.py
│   ├── test_api_contract.py
│   ├── test_fallback.py
│   ├── test_librarian.py
│   ├── test_hardening.py
│   └── test_guard.py
├── pytest.ini
├── requirements-dev.txt       # 开发/测试依赖
├── scripts/smoke_test.py      # 端到端冒烟测试
└── data/                      # 运行时生成 xuniversity.db
```

## 7. Phase 2 / Phase 3 接入点

- **RAG（Library）**：`app/agents/librarian.py` 顶部已写明接入方案（切块 → embedding → Chroma/LanceDB → 召回 + rerank）。
  实现 `_retrieve_via_rag()` 后把模块顶部的 `RAG_ENABLED` 改为 `True` 即可切换；返回结构不变，前端无需改动。
  （未实现时该分支会主动抛 `NotImplementedError`，避免「以为切到了 RAG、其实还在吃精选语料」。）
- **Memory 升级**：`store.py` 接口与实现分离，可平滑换成 Redis/Postgres；路线图上下文拼装在 `core/prompts.py::build_context_block`；
- **多 Agent 协作**：以 `scholar.py` 为编排者，按 roadmap 的 stage/task 调度 librarian → professor → lab_mentor，前端也可按空间切换直接调对应端点；
- **工具调用**：在 `agents/` 下新增 tool（arXiv 检索、代码执行等），通过 DeepSeek function calling 接入；
- **稳定性**：所有真实调用均有 try/except + mock 降级；路演前把黄金路径在 `MOCK_MODE=true` 下彩排一遍即可零风险演示。
