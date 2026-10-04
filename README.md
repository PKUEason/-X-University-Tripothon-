# X University — Tripothon 团队仓库

🌌 X University：走进一座未来大学，提出目标，让 AI 带着你学习、研究、协作，直到做出成果。

## 目录结构

```
.
├── ai-backend/          # AI 后端（FastAPI + DeepSeek + SSE + 记忆 + Mock 降级）← AI 侧
├── campus-frontend/     # Three.js 校园 + 真实 Agent 联调入口
├── ...（其他模块由对应成员建立：3D 前端 / 设计 / 文档 等）
```

## ai-backend 快速开始

3D 场景接入版：[启动与体验说明](campus-frontend/README.md)。完成依赖安装后，在根目录运行 `npm --prefix campus-frontend run dev`，打开 http://127.0.0.1:4176 。

```bash
cd ai-backend
python -m venv .venv && .venv\Scripts\activate        # Windows
pip install -r requirements.lock.txt                  # 精确复现（或 requirements.txt）
python run.py                                          # 默认 127.0.0.1:8000，打开 http://127.0.0.1:8000/docs
```

- 接口契约 / 环境变量 / 测试 / 路演接入：见 `ai-backend/README.md`
- 前端 SDK + 3D 对接指南：见 `ai-backend/frontend/INTEGRATION.md`
- 首次运行需本地创建 `.env`（复制 `.env.example` 并填入 DeepSeek key，见下）

## ⚠️ API 安全红线（重要）

1. **`.env` 已随仓库共享**（含真实 DeepSeek key）：本仓库为**私有团队仓库**，clone 后开箱即用、
   无需自备 key，直接 `python run.py` 即可测试对话。
2. **严禁把这个仓库改为公开**；新增协作者要谨慎（能 clone 的人都能看到 key）。**比赛结束后
   必须在 DeepSeek 平台吊销并轮换 key**（git 历史里的旧 key 无法真正删除）。
3. **`.env` 的后续改动不会自动进 git**（`.gitignore` 仍忽略，需显式 `git add -f` 才更新）——
   正常开发改本地 `.env` 不影响仓库。
4. 后端内置三重防护（每日 LLM 预算 / 单 IP 限流 / 异常脱敏），超预算自动降级 Mock，演示不中断。
5. 公网暴露（隧道/云主机）前：设置 `API_TOKEN` + 控制 `HOST`，详见 `ai-backend/README.md`「公网暴露前必读」。

## 协作方式

- `main` 分支直接协作（小型团队）；大改请先同步再推。
- 提交前自检：`git status` 确认无 `.env`、无 `node_modules/`、无 `data/*.db`。
