/**
 * React 用法示例（需安装 react 类型）：
 *   npm i react @types/react
 * 在 3D 场景的 X Gate 交互面板中调用，供全栈同学参考接线方式。
 */
import { useState } from "react";
import { XUniversityClient, type ClarifyResult, type Roadmap } from "../xuni-client";

const xuni = new XUniversityClient("http://127.0.0.1:8000/api");

export function ScholarGatePanel() {
  const [sessionId, setSessionId] = useState<string>("");
  const [message, setMessage] = useState("");
  const [chat, setChat] = useState("");
  const [busy, setBusy] = useState(false);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);

  /** 进门时创建会话 */
  async function enterGate() {
    const { session_id } = await xuni.createSession({
      goal: "两周入门扩散模型，做出图像生成 Demo",
    });
    setSessionId(session_id);
  }

  /** 向 Scholar 发消息（SSE 流式，逐字追加） */
  async function send() {
    if (!sessionId || !message.trim() || busy) return;
    setBusy(true);
    setChat("");
    const result: ClarifyResult = await xuni.streamClarify(
      { session_id: sessionId, message },
      {
        onToken: (d) => setChat((prev) => prev + d),
        onFallback: (r) => console.warn("已降级演示模式:", r),
      },
    );
    setBusy(false);
    if (result.ready) {
      const { roadmap } = await xuni.streamRoadmap(
        { session_id: sessionId },
        { onRoadmap: setRoadmap },
      );
      console.log("路线图就绪:", roadmap.title);
    }
  }

  return (
    <div>
      <button onClick={enterGate} disabled={!!sessionId}>进入 X Gate</button>
      <input value={message} onChange={(e) => setMessage(e.target.value)} placeholder="告诉 Scholar 你的目标…" />
      <button onClick={send} disabled={busy || !sessionId}>{busy ? "思考中…" : "发送"}</button>
      <div style={{ whiteSpace: "pre-wrap", minHeight: 80 }}>{chat}</div>
      {roadmap && (
        <ul>
          {roadmap.stages.map((s) => (
            <li key={s.id}>{s.name} — {s.tasks.length} 个任务</li>
          ))}
        </ul>
      )}
    </div>
  );
}
