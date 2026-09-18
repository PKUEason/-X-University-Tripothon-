"""端到端冒烟测试：python scripts/smoke_test.py [base_url]

覆盖：健康检查 → 建会话 → Scholar 澄清(SSE) → 路线图(SSE) → Library 检索
     → Professor 答疑(SSE) → Lab 指导 → 任务进度 → 会话快照

HTTP 客户端统一用 httpx2（openai SDK 与 Starlette TestClient 也都用 httpx2），
不要再引入 httpx，否则环境里会同时存在两套客户端。
"""
import json
import sys

import httpx2 as httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PASS, FAIL = 0, 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def parse_sse(text: str) -> list[dict]:
    events, event, data = [], None, []
    for line in text.splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].strip())
        elif line == "":
            if event:
                try:
                    payload = json.loads("".join(data))
                except json.JSONDecodeError:
                    payload = {"raw": "".join(data)}
                events.append({"event": event, "payload": payload})
            event, data = None, []
    return events


def main():
    print(f"== Smoke test against {BASE} ==")
    r = httpx.get(f"{BASE}/health", timeout=10)
    check("GET /health", r.status_code == 200, r.text)
    print("       health:", r.json())

    r = httpx.post(f"{BASE}/api/session/create", json={"goal": "我想用两周入门扩散模型，做出图像生成 Demo"}, timeout=10)
    check("POST /api/session/create", r.status_code == 200, r.text)
    sid = r.json()["session_id"]

    with httpx.stream("POST", f"{BASE}/api/scholar/clarify",
                      json={"session_id": sid, "message": "我有 PyTorch 基础，每天 3 小时，想跑通文生图"},
                      timeout=120) as resp:
        text = resp.read().decode()
    events = parse_sse(text)
    kinds = [e["event"] for e in events]
    check("clarify SSE 有 token", "token" in kinds, str(kinds))
    check("clarify SSE 有 ready", "ready" in kinds, str(kinds))
    check("clarify SSE 以 done 结束", kinds[-1] == "done", str(kinds[-3:]))

    with httpx.stream("POST", f"{BASE}/api/scholar/roadmap", json={"session_id": sid}, timeout=180) as resp:
        text = resp.read().decode()
    events = parse_sse(text)
    roadmap_events = [e for e in events if e["event"] == "roadmap"]
    check("roadmap SSE 返回路线图", len(roadmap_events) == 1, str([e["event"] for e in events]))
    if roadmap_events:
        rm = roadmap_events[0]["payload"]["roadmap"]
        spaces = [s["space"] for s in rm["stages"]]
        check("路线图 4 个阶段", len(rm["stages"]) == 4, str(spaces))
        check("空间顺序 gate→library→professor_office→lab",
              spaces == ["gate", "library", "professor_office", "lab"], str(spaces))
        task_count = sum(len(s["tasks"]) for s in rm["stages"])
        check("路线图含任务节点", task_count >= 5, f"tasks={task_count}")
        first_task = rm["stages"][0]["tasks"][0]["id"]
    else:
        first_task = "t-1-1"

    r = httpx.post(f"{BASE}/api/library/retrieve",
                   json={"session_id": sid, "query": "DDPM 扩散模型论文", "top_k": 3}, timeout=30)
    check("library 返回资料", r.status_code == 200 and len(r.json().get("documents", [])) > 0, r.text[:200])

    with httpx.stream("POST", f"{BASE}/api/professor/chat",
                      json={"session_id": sid, "message": "请讲一下反向扩散过程", "task_id": "t-3-1"},
                      timeout=120) as resp:
        text = resp.read().decode()
    events = parse_sse(text)
    kinds = [e["event"] for e in events]
    check("professor SSE 有 token", "token" in kinds, str(kinds))
    check("professor SSE 以 done 结束", kinds[-1] == "done", str(kinds[-3:]))

    r = httpx.post(f"{BASE}/api/lab/guidance", json={"session_id": sid, "task_id": "t-4-1"}, timeout=120)
    body = r.json()
    check("lab 返回 steps/deliverables",
          r.status_code == 200 and len(body.get("steps", [])) >= 3 and body.get("deliverables"),
          str(body)[:200])

    r = httpx.post(f"{BASE}/api/session/{sid}/progress",
                   json={"task_id": first_task, "status": "done"}, timeout=10)
    check("更新任务进度", r.status_code == 200 and r.json().get("ok"), r.text)

    r = httpx.get(f"{BASE}/api/session/{sid}", timeout=10)
    snap = r.json()
    check("会话快照含 roadmap", bool(snap.get("roadmap")), "")
    check("会话快照含 messages", len(snap.get("messages", [])) >= 4, f"msgs={len(snap.get('messages', []))}")
    done = any(t["id"] == first_task and t["status"] == "done"
               for s in snap["roadmap"]["stages"] for t in s["tasks"])
    check("进度已持久化", done, "")

    print(f"\n== {PASS} passed, {FAIL} failed ==")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
