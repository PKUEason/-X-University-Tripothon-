# -*- coding: utf-8 -*-
"""Professor references 质量对比：对关键词型 / 语义型问题走真实 SSE，
打印 references 召回的资料标题与回答开头，验证 hybrid 真语义是否让资料更贴题。

用法：python scripts/ref_compare.py [http://127.0.0.1:8000]
会真实调用 DeepSeek + embedding，消耗少量额度。
"""
import json
import sys

import httpx2 as httpx

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"

QUESTIONS = [
    ("关键词型", "请用一句话解释反向扩散"),
    ("语义型", "为什么加了噪声，最后还能还原出清晰的图"),
    ("语义型", "生成的图总是很糊、细节出不来，该从哪里下手"),
]


def ask(session: str, question: str):
    refs, answer, event = [], "", None
    with httpx.stream(
        "POST",
        BASE + "/api/professor/chat",
        json={"session_id": session, "message": question},
        timeout=120.0,
    ) as resp:
        for raw in resp.iter_lines():
            line = raw.strip()
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
                if event == "references":
                    refs = data.get("references", [])
                elif event == "token":
                    answer += data.get("delta", "")
    return refs, answer


def main() -> None:
    session = httpx.post(BASE + "/api/session/create", json={}).json()["session_id"]
    for tag, question in QUESTIONS:
        refs, answer = ask(session, question)
        print(f"\n[{tag}] Q：{question}")
        print(f"  references（{len(refs)}）：")
        for ref in refs:
            print(f"    - {ref['title']}  [{ref['type']}]")
        print(f"  回答开头：{answer.strip()[:60]}…")


if __name__ == "__main__":
    main()
