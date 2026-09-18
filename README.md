# X University — Tripothon 团队仓库

🌌 X University：走进一座未来大学，提出目标，让 AI 带着你学习、研究、协作，直到做出成果。

## 目录结构

```
.
├── ai-backend/          # AI 后端（FastAPI + DeepSeek + SSE + 记忆 + Mock 降级）← AI 侧
├── ...（其他模块由对应成员建立：3D 前端 / 设计 / 文档 等）
```

## ai-backend 快速开始

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

1. **`.env` 严禁提交**：它含真实 DeepSeek API key（付费额度）。本仓库 `.gitignore` 已忽略，
   任何人不准 `git add -f .env` / 改 `.gitignore` 放行。
2. **key 只存在于本地 `.env`**：协作者各自复制 `.env.example` 填写，或用私聊传递，不进 git。
3. 后端内置三重防护（每日 LLM 预算 / 单 IP 限流 / 异常脱敏），超预算自动降级 Mock，演示不中断。
4. 公网暴露（隧道/云主机）前：设置 `API_TOKEN` + 控制 `HOST`，详见 `ai-backend/README.md`「公网暴露前必读」。

## 协作方式

- `main` 分支直接协作（小型团队）；大改请先同步再推。
- 提交前自检：`git status` 确认无 `.env`、无 `node_modules/`、无 `data/*.db`。
