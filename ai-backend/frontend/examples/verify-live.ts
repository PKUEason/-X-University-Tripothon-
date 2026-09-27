/**
 * 运行时连通性验证（真实调用 DeepSeek，会消耗少量额度）。
 * 运行：node --experimental-strip-types examples/verify-live.ts
 * 前置：后端已启动（python run.py，端口 8000）
 */
import { XUniversityClient } from "../xuni-client/client";

async function main(): Promise<void> {
  const xuni = new XUniversityClient("http://127.0.0.1:8000/api");

  const { session_id } = await xuni.createSession({
    goal: "我想用两周入门扩散模型，做出图像生成 Demo",
    nickname: "verify",
  });
  console.log("[1/7] 会话创建 OK:", session_id);

  let text = "";
  const first = await xuni.streamClarify(
    { session_id, message: "我想学扩散模型" },
    { onToken: (d) => (text += d), onFallback: (r) => console.warn("[fallback]", r) },
  );
  // 真实模式第一轮通常是追问基础，ready=false 属正常
  console.log(`[2/7] 澄清第一轮 OK: ready=${first.ready}, fallback=${first.fallback}, 文本${text.length}字`);

  let text2 = "";
  const second = await xuni.streamClarify(
    { session_id, message: "有 PyTorch 基础，每天 3 小时，想跑通文生图" },
    { onToken: (d) => (text2 += d) },
  );
  console.log(`     澄清第二轮 OK: ready=${second.ready}, fallback=${second.fallback}, 文本${text2.length}字`);

  const { roadmap, fallback } = await xuni.streamRoadmap({ session_id }, { onStatus: (s) => console.log("      status:", s) });
  console.log(`[3/7] 路线图 OK: fallback=${fallback}, 标题=${roadmap.title}`);
  console.log("      阶段:", roadmap.stages.map((s) => `${s.space}(${s.tasks.length})`).join(" → "));

  const lib = await xuni.libraryRetrieve({ session_id, query: "DDPM", top_k: 2 });
  console.log(`[4/7] 图书馆 OK: ${lib.documents.length} 条, engine=${lib.engine}`);

  let pt = "";
  const professor = await xuni.streamProfessorChat(
    { session_id, message: "请用一句话解释反向扩散", task_id: "t-3-1" },
    { onToken: (d) => (pt += d) },
  );
  console.log(`[5/7] Professor OK: fallback=${professor.fallback}, 回复${pt.length}字`);

  const lab = await xuni.labGuidance({ session_id, task_id: "t-4-1" });
  console.log(`[6/7] Lab OK: ${lab.steps.length} 步骤, degraded=${lab.degraded ?? false}`);

  await xuni.updateProgress(session_id, "t-1-1", "done");
  const snap = await xuni.getSession(session_id);
  const firstTask = snap.roadmap?.stages[0].tasks[0];
  console.log(`[7/7] 进度 OK: t-1-1 status=${firstTask?.status}, 消息数=${snap.messages.length}`);

  if (!second.ready || !roadmap.stages.length || !pt || !lab.steps.length || firstTask?.status !== "done") {
    throw new Error("有环节未达到预期");
  }
  console.log("[7/8] 基础链路全部通过");

  // ---------- 8. Quest 编排全流程（多 Agent + Project Card + Memory） ----------
  const questSession = await xuni.createSession({ goal: "Quest 编排验证", nickname: "quest" });
  const qid = questSession.session_id;
  let current = "created";
  let questResult = await xuni.advanceQuest(
    { session_id: qid, message: "我想用两周跑通扩散模型文生图 Demo" },
    {
      onQuest: (s, m) => { current = s; console.log("      quest →", s, "|", m); },
      onProject: (p) => console.log("      project card:", p.title),
    },
  );
  // 第一轮可能仍需追问（真实模型行为不固定）
  if (current === "clarifying") {
    questResult = await xuni.advanceQuest(
      { session_id: qid, message: "有 PyTorch 基础，每天 3 小时" },
      { onQuest: (s) => (current = s) },
    );
  }
  // 之后一路推进到 project_ready
  let guard = 0;
  while (current !== "project_ready" && guard++ < 8) {
    questResult = await xuni.advanceQuest({ session_id: qid }, { onQuest: (s) => (current = s) });
  }
  const mem = await xuni.recallMemory(qid);
  console.log(`[8/8] Quest 编排 OK: status=${current}, 记忆 ${mem.memories.length} 条`);

  if (current !== "project_ready" || !questResult.project) {
    throw new Error("Quest 编排未走通或缺少 Project Card");
  }
  console.log("\n全部通过 ✓ SDK ↔ 后端 ↔ DeepSeek 真实链路正常（含多 Agent 编排）");
}

main().catch((err) => {
  console.error("验证失败:", err);
  process.exitCode = 1;
});
