# X University · 3D Campus + Agent

按设计师 Figma 方向重建的霓虹浮岛校园，保留 Three.js 实时渲染，连接团队 FastAPI 后端与其 `XUniversityClient`。当前包含完整校园前端，并整合团队 arXiv 检索提交 `0b5c1fd`；无需依赖仓库外的 Alpha 文件。

## 启动

需要 Node.js 20.12+、Python 3.10+。首次安装，在团队仓库根目录执行：

```sh
python3 -m venv ai-backend/.venv
ai-backend/.venv/bin/python -m pip install -r ai-backend/requirements.lock.txt
npm --prefix campus-frontend ci
npm --prefix campus-frontend run dev
```

macOS 的系统 Python 3.9 不满足后端要求，请用自己安装的 Python 3.10+ 运行首条命令。Windows 使用 `.venv\Scripts\python.exe`。

浏览器打开 http://127.0.0.1:4176 。前后端仅监听回环地址；脚本同时启动后端 8000 与校园 4176。Ctrl+C 退出。已经手动启动后端时，只执行 `npm --prefix campus-frontend start`。API 地址可用 `XUNI_BACKEND_URL` 在服务端配置。

后端沿用团队已有 `.env`。API key 和 `API_TOKEN` 只由服务端读取，不写进前端或浏览器存储；本地代理为请求添加已有 API_TOKEN。切换到后端演示模式：`MOCK_MODE=true npm --prefix campus-frontend run dev`，页面会显示“后端演示模式”。真实请求失败触发的降级会显示“含降级示例”。不要将静态构建目录直接发布后声称 Agent 已部署：它需要同源 `/api` 代理和正在运行的后端。

## 体验

首次进入先选择男生或女生并填写昵称。左侧可预览原创学生角色；针织衫、书包、运动鞋取代旧军人模型，校园中的行走/奔跑保留。

1. 入学后打开“我的项目”：新建一个项目，或选择已有项目。已有单会话自动迁移为一个项目。
2. 每个项目独立走自己的目标澄清、资料检索、教授研讨、实验室方案和行动卡阶段。不需要完成项目 A 才能开始项目 B。
3. 顶部“我的项目”和左侧当前项目名称都能打开项目列表，显示每个项目的阶段与实际任务完成数量。
4. 切换项目只切换工作内容，人物留在当前空间；点击任务卡可走向该项目下一站。输入草稿也分别保留。
5. Student 资料跨项目共用；点击顶部昵称修改角色与昵称。新建后端会话会携带昵称，角色性别只用于本地人物外观。
6. 刷新后先看到大世界主页，保留资料与上次选中的项目。Agent 正在回复时暂时禁用切换/新建，防止串写。

项目列表、角色、昵称和草稿保存在当前浏览器，各项目的对话/阶段结果保存在本机后端。当前没有账号登录和跨设备项目同步。

任务清单的勾选由用户明确操作，生成方案不会将真实学习/实验任务自动标成完成。项目卡是研究或实施方案，不是已执行实验或已生成可运行代码的证明。

地图按钮是步行引导；WASD 可中断。对话框内输入暂停人物移动。重复进入空间不会重复生成阶段产物。新建项目保留全部已有项目，可随时切回。

## 接入与交接

- `src/service.js`：会话控制、SDK 调用、流式回调、故障恢复。
- `src/app.js`：空间与 Agent 面板、任务/资料/项目卡展示。
- `src/student.js`：原创学生模型、预览与程序化行走动画。
- `src/campus.js` / `world.js`：碰撞、当前位置寻路、第一/第三人称与总览镜头。
- `src/neon-scene.js` / `atmosphere.js`：浮岛建筑、城市天际线、日夜环境、材质与辉光。
- `src/shell.js` / `glass.css`：主页、玻璃导航、环形菜单与响应式视觉。
- `server.mjs`：白名单静态资源 + 同源 API 代理，不服务 `.env`、源码仓库或数据库。
- `build.mjs`：从团队 TypeScript SDK 编译浏览器模块，不复制一套手写 API 协议。
- [接入说明](docs/INTEGRATION.md)：后端增量、状态映射与边界。
- [验证记录](docs/VERIFICATION.md)：实际验证结果。

```sh
npm --prefix campus-frontend test
npm --prefix campus-frontend run build
ai-backend/.venv/bin/python -m pytest ai-backend/tests -q
```

校园建筑已替换为原创程序化霓虹浮岛，学生人物仍为程序模型，未达到参考图中的精修角色资产质量。首页使用设计师 Figma 中的原始背景图片和 SVG 图标；可行走世界为实时三维几何。素材说明见 `public/credits.html`，本轮设计映射与验收边界见 [视觉重建记录](docs/VISUAL-REDESIGN.md)。

## 视觉与视角

底部切换主页、总览、第三人称和第一人称。WASD / 方向键移动，Shift 奔跑，拖动环视，第三人称滚轮调节距离，E 互动。M 打开环形目的地菜单；点击目的地从人物当前位置导航。夜间按钮改变实时场景灯光，不改变主页的原始背景图。

设置提供三档画质及减少动态效果。流畅模式关闭阴影和辉光。默认画质合并静态几何并实例化周围城市。首页及资料卡使用真实 DOM 文本，Agent Markdown 继续经过允许列表转换。

## 独立后台运行（2026-10-03）

为避免服务依赖临时终端会话，可在仓库根目录运行 `npm --prefix campus-frontend run dev:background`。仍使用原地址 http://127.0.0.1:4176/ 和原项目数据库；不会设置开机自启。重复启动会检查现有进程与端口，不会占用第二组端口。

`npm --prefix campus-frontend run dev:status` 查看状态；`npm --prefix campus-frontend run dev:stop` 停止。运行日志在本地忽略目录 `campus-frontend/.local/server.log`。

### arXiv 论文检索（2026-10-04）

已整合团队提交 `0b5c1fd` 的 arXiv 接口与解析器。Library 将本地资料和相关论文分开展示，论文包含作者、年份、摘要节选和来源链接。`retrieval_version=3` 会使旧缓存进入图书馆时按当前项目更新。arXiv 结果保存到对应项目，重新检索不推进已有阶段。

- 后端开关：`ARXIV_ENABLED=true`、`ARXIV_TIMEOUT=8.0`、`ARXIV_TOP_K=3`。使用 HTTPS、缓存与串行限速；失败不会伪造论文。
- 常见主题有明确的中英关键词映射（AI 硬件、柔性机器人、扩散模型、机器人视觉）；其他中文主题会提示填写英文检索词。这不是通用语义翻译。
- 用户可以在 Library 编辑论文关键词，逗号分隔多个短语；使用短语 OR 查询，不修改项目目标。本地资料仍按当前项目目标过滤。
- API 新增 `arxiv_query` 可选输入；返回 `arxiv_query`、`arxiv_papers`、`arxiv_status`（ok / failed / disabled / mock / needs_query）。`ok` 且空列表表示无命中；演示模式不冒充真实搜索。
- 当前不含网页教程搜索；Professor 沿用本地资料检索，尚未自动引用外部论文。

### 内容卡片与 Markdown

Agent 面板将项目背景、最新回复、待回答问题、下一步操作和实际任务分区展示，旧消息可展开。正文通过 Marked 分词后渲染为安全 DOM；运行 `npm run sdk` 时同时生成 `src/markdown-vendor.js`。仅格式化和分组展示，不修改服务端消息。问题识别使用有限规则，未匹配的问题保留在正文。Markdown 中的任务复选符号仅表示原文内容，实际任务进度仍由单独的任务控件操作。

### 图书馆 Blender 样板

底部 **图书馆样板** 可直接查看新建筑的全貌、正面、侧面和阅读大厅。拖动旋转，滚轮缩放；“走进图书馆”从角色当前位置继续寻路。该视图与校园使用同一个 GLB，切换观察视角不会移动角色。

源模型、可复现建模脚本及范围说明见 [art/library/README.md](art/library/README.md)。本轮只精修图书馆；上层楼梯为视觉结构，步行仍限一层。

### Campus architecture update

Professor, X Lab and X Gate now use authored Blender models in the same material family as Libpedia. Open **建筑细节** and choose a building for exterior/interior inspection. Sources and reproducible exports: [`art/campus/README.md`](art/campus/README.md). Ground-floor navigation and Agent interaction locations are retained.
