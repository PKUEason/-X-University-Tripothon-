# -*- coding: utf-8 -*-
"""从后端 mock 导出与契约同构的样例路线图 JSON，供前端脱离后端做场景渲染测试。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.mock_data import golden_path as mock  # noqa: E402

out = Path(__file__).resolve().parent.parent / "frontend" / "examples" / "sample-roadmap.json"

roadmap = mock.roadmap("我想用两周入门扩散模型，做出图像生成 Demo")
out.write_text(json.dumps(roadmap, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"written: {out} ({out.stat().st_size} bytes)")
print("stages:", [(s["space"], len(s["tasks"])) for s in roadmap["stages"]])
