"""测试基座：环境隔离 + 公共 fixture。

关键点：必须在 import app 之前写好环境变量。
app/config.py 在模块导入时就会读取 .env（load_dotenv 默认不覆盖已有环境变量），
所以这里先注入，保证测试永远跑在「临时数据库 + MOCK 模式 + 空 API Key」上，
既不污染 data/xuniversity.db，也不会误打真实 DeepSeek 接口。
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TMP_DIR = tempfile.mkdtemp(prefix="xuni-test-")
os.environ["MOCK_MODE"] = "true"
os.environ["LLM_FALLBACK_TO_MOCK"] = "true"
os.environ["DATA_DIR"] = _TMP_DIR
os.environ["DEEPSEEK_API_KEY"] = ""
# 测试套件会在几秒内发出上百个请求，全部来自同一个测试客户端 IP，
# 必然打满限流。这里关掉，需要验证限流的用例自己临时打开。
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def tmp_data_dir() -> str:
    return _TMP_DIR


@pytest.fixture()
def client():
    """同步 TestClient；with 语法会触发 startup 事件。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def session(client) -> str:
    """建好一个会话，返回 session_id。"""
    r = client.post("/api/session/create", json={"goal": "我想用两周入门扩散模型，做出图像生成 Demo"})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


@pytest.fixture()
def live_mode():
    """临时关掉 MOCK，走真实 LLM 分支（配合 monkeypatch 伪造 LLM 行为）。"""
    origin_mock, origin_fallback = settings.mock_mode, settings.fallback_to_mock
    settings.mock_mode = False
    yield settings
    settings.mock_mode = origin_mock
    settings.fallback_to_mock = origin_fallback


def parse_sse(raw: str) -> list[dict]:
    """把 SSE 文本解析成 [{"event": ..., "payload": {...}}]。"""
    events: list[dict] = []
    event, data = None, []
    for line in raw.splitlines():
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


@pytest.fixture()
def sse(client):
    """POST 一个 SSE 端点，返回解析后的事件列表。"""

    def _post(path: str, payload: dict) -> list[dict]:
        with client.stream("POST", path, json=payload) as resp:
            assert resp.status_code == 200, f"{path} -> {resp.status_code}"
            raw = resp.read().decode("utf-8")
        return parse_sse(raw)

    return _post
