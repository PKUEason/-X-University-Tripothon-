/**
 * 纯 TS 用法示例（无框架）：完整黄金路径一次走完。
 * 参与 tsc --noEmit 类型检查，可作为前端接入的参考骨架。
 */
import { XUniversityClient } from "../xuni-client";

const xuni = new XUniversityClient("http://127.0.0.1:8000/api");

async function goldenPathDemo(): Promise<void> {
  // 1. 创建会话（3D 世界进入 X Gate 时调用）
  const { session_id } = await xuni.createSession({
    goal: "我想用两周入门扩散模型，做出图像生成 Demo",
    nickname: "Eason",
  });
  console.log("session:", session_id);

  // 2. X Gate：与 Scholar 澄清目标（SSE 流式打字效果）
  let streamed = "";
  const clarify = await xuni.streamClarify(
    { session_id, message: "我有 PyTorch 基础，每天 3 小时" },
    {
      onToken: (delta) => (streamed += delta),
      onReady: (ready) => console.log("\n[ready]", ready),
      onFallback: (reason) => console.warn("[fallback]", reason),
    },
  );
  console.log("澄清文本:", streamed.slice(0, 40) + "…");
  console.log("澄清完成:", clarify.ready);

  // 3. Scholar 生成路线图（渲染 3D 任务节点 / 空间传送门）
  const { roadmap } = await xuni.streamRoadmap(
    { session_id },
    { onStatus: (s) => console.log("[status]", s) },
  );
  console.log("路线图:", roadmap.title);
  console.log("阶段:", roadmap.stages.map((s) => `${s.space}:${s.tasks.length}任务`).join(" -> "));

  // 4. Library：检索资料（v4 统一结果：results + sources）
  const lib = await xuni.libraryRetrieve({ session_id, query: "DDPM 扩散模型论文", top_k: 3 });
  console.log("图书馆资料:", lib.results.map((d) => `[${d.source}] ${d.title}`));
  console.log("检索渠道:", JSON.stringify(lib.sources));

  // 5. Professor Office：答疑（携带任务上下文）
  let professorText = "";
  const professor = await xuni.streamProfessorChat(
    { session_id, message: "请讲一下反向扩散过程", stage_id: "stage-3", task_id: "t-3-1" },
    { onToken: (d) => (professorText += d) },
  );
  console.log("\n教授回复字数:", professorText.length);

  // 6. Research Lab：实践指导
  const lab = await xuni.labGuidance({ session_id, task_id: "t-4-1" });
  console.log("实验步骤:", lab.steps.map((s) => s.title).join(" / "));

  // 7. 更新任务状态（驱动 3D 场景进度）
  await xuni.updateProgress(session_id, "t-1-1", "done");
  const snap = await xuni.getSession(session_id);
  console.log("任务状态持久化:", snap.roadmap?.stages[0].tasks[0].status);
}

goldenPathDemo().catch((err) => {
  console.error("调用失败:", err);
  throw err;
});
