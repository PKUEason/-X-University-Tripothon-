# 场景与 Agent 接入

依据：飞书产品定义 revision 59（2026-10-01 重新读取正文和五张嵌入表）、团队后端提交 803a1433。用户授权将本地模拟场景接入 Agent。本轮未编辑产品定义、未向队友发送消息。

| 前端空间/动作 | 实际后端调用 | 输出与恢复 |
|---|---|---|
| X Gate 提交目标 | createSession → advanceQuest(message) | 服务端 session_id、澄清对话、quest_ready |
| X Gate 继续回复 | 路线生成前 advanceQuest(message)；已有路线 streamClarify | ready 后仍可澄清；已有路线和阶段保留 |
| 生成路线 | advanceQuest(expected_status=quest_ready) | roadmap 与 library 状态 |
| Library 进入 | advanceQuest(expected_status=library) | 资料持久化；professor 表示下一阶段，人物仍留在 Library 阅读 |
| Library 重新检索 | libraryRetrieve(query="") | 后端使用当前项目目标与补充，保存新结果，不重置当前阶段 |
| Office 进入或追问 | streamProfessorChat(task_id, stage_id) | 流式回复、参考资料、教授结果持久化 |
| 用户确认研讨完成 | advanceQuest(expected_status=professor) | lab 状态，并步行前往实验室 |
| Lab 生成方案 | advanceQuest(expected_status=lab) | Lab guidance、Project Card、project_ready |
| 实际任务勾选 | updateProgress | 服务端任务状态，不随方案生成自动完成 |
| 刷新/恢复 | getSession + getQuest | 服务端是任务和阶段结果的权威来源 |
| 删除项目 | deleteSession → DELETE /session/{session_id} | 确认后清理该项目后端记录；成功后移除浏览器记录，其他项目保留 |

`office` 对应后端 `professor_office`；Plaza 是导航空间，没有额外 Agent。Quest 状态变化不强迫玩家立即离开当前空间。

## 必要后端增量

1. 原 orchestrator 在 professor 阶段仅变更状态。本轮由前端明确调用真实 Professor 对话后，允许用户确认进入 Lab。
2. `memory/artifacts.py` 保存 Library、Professor、Lab 阶段结果；`getQuest` 添加可选字段返回。Professor、Lab、Project Card 读取此前结果。
3. Quest 请求添加可选 `request_id` 和 `expected_status`，旧客户端仍兼容。成功请求重放相同事件，旧状态请求不推进；生成失败保留原阶段。
4. Project Card 标记为 `project_plan`，约束提示词不宣称代码或实验已经执行。失败示例显式返回 `degraded` 并发 fallback；持久化降级标记供恢复时展示。
5. SDK 流解析遇到坏数据/回调异常不再静默丢弃；取消不再伪装为成功。继续消费内部 done 后的 Quest 事件，等整个流完成才读取服务端快照。

## 运行边界

- 请求互斥锁限当前单进程本地服务；多 worker 部署需数据库/分布式事务保护。
- 不自动重试推进请求；连接异常先读回服务端，再由用户操作。浏览器会话使用独立存储键，不会把旧 mock 进度当真实会话。
- 学习资料当前来自后端维护的语料与检索，不等于全网搜索。来源链接可打开，但前端不宣称每一条都已经人工核验。
- 2026-10-02 起资料结果带 retrieval_version=2，显示实际检索需求和覆盖说明。目前语料仅覆盖扩散模型、柔性机器人；无对应主题时返回空结果。旧版结果先提示重新检索，避免继续展示未按项目主题核验的资料。
- 本地账号密钥、数据库、生成的 SDK 和验证截图不进入提交。既有受 Git 跟踪的 `.env` 未修改。
- 当前包含学生模型、校园场景和交互卡片调整；尚未建设社交、账号或多人系统，也未公开部署。

## 学生资料与多项目（2026-10-01）

以一个后端 session 表示一个项目，沿用现有 API，不引入伪造的全局项目状态。工作区存储键为 xuni-campus-workspace-v2：profile、activeProjectId、projects。每个项目分别持有 session_id、阶段、路线、资料/对话/行动卡、降级标记及输入草稿。旧 xuni-connected-campus-v1 自动迁移，源记录保留。

选择当前项目后重新读其后端快照；新建项目只有在第一次提交目标时才建立后端 session，并传入 nickname。头像与性别留在前端，角色在校园内的位置不因项目切换而跳变。当前项目流式请求尚未结束时禁止切换与新建，防止回复写入其他项目。

人物替换为 student.js 生成的原创圆润学生模型，保留碰撞、镜头与移动控制，使用关节旋转完成步行/奔跑。性别预览与校园共用同一模型工厂。

2026-10-03 更新：角色改为成人比例的风格化网格，预览支持拖动。导航使用当前位置与扩展障碍角点的可见图，直接通行时不绕行；手动进入空间只更新位置，导航到达或用户主动互动才打开 Agent 面板。画面偏好使用 xuni-campus-settings-v1，探索记录使用 xuni-campus-explored，与项目任务完成状态分开。

本轮增加学生视觉与多项目能力，替代前述单线入口的范围描述。项目列表仍以本浏览器为边界，未实现账号、跨设备同步或多人项目协作。

## 当前资料接口（2026-10-04）

`retrieval_version=3`：本地资料与 `arxiv_papers` 分区返回；`arxiv_status` 区分成功、失败、禁用、演示和需要英文检索词，`arxiv_query` 支持前端编辑。旧 v2 资料会在进入 Library 时刷新。自动映射仅覆盖明确列出的常见主题；Professor 当前仍使用本地资料。
