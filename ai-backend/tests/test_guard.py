"""成本与滥用防护：每日预算熔断、单 IP 限流、对外错误脱敏。

这三样是「把后端放到公网」时唯一真正管用的刹车——
前端 token 挡不住 curl，真正会被滥用的不是 DeepSeek 的 key（它从不进前端），
而是你的后端本身被当成免费代理刷额度。
"""
import logging

import pytest

from app.agents.llm import llm
from app.core import guard
from app.core.guard import BudgetExceeded, DailyBudget, RateLimiter, budget, public_error_message


@pytest.fixture(autouse=True)
def _clean_guard():
    """每个用例前后都清干净，避免单例状态互相串。"""
    budget.reset()
    guard.rate_limiter.reset()
    origin_limit, origin_rate = budget.limit, guard.rate_limiter.per_minute
    yield
    budget.reset()
    guard.rate_limiter.reset()
    budget.limit = origin_limit
    guard.rate_limiter.per_minute = origin_rate


# ---------------- DailyBudget ----------------
def test_budget_reserves_until_limit_then_blocks():
    b = DailyBudget(3)
    assert [b.try_reserve() for _ in range(3)] == [True, True, True]
    assert b.try_reserve() is False
    assert b.snapshot()["used"] == 3        # 被拒的那次不该计入 used


def test_budget_non_positive_limit_means_unlimited():
    b = DailyBudget(0)
    assert all(b.try_reserve() for _ in range(100))
    assert b.snapshot()["remaining"] is None


def test_budget_snapshot_fields():
    b = DailyBudget(10)
    for _ in range(4):
        b.try_reserve()
    b.reject()
    snap = b.snapshot()
    assert snap["limit"] == 10
    assert snap["used"] == 4
    assert snap["remaining"] == 6
    assert snap["rejected"] == 1
    assert snap["day"]


def test_budget_resets_on_new_day(monkeypatch):
    b = DailyBudget(2)
    b.try_reserve()
    b.try_reserve()
    assert b.try_reserve() is False

    import datetime as dt

    tomorrow = dt.date.today() + dt.timedelta(days=1)
    monkeypatch.setattr(guard, "_today", lambda: tomorrow)
    assert b.try_reserve() is True
    assert b.snapshot()["used"] == 1


def test_budget_limit_is_adjustable():
    b = DailyBudget(1)
    assert b.try_reserve() is True
    assert b.try_reserve() is False
    b.limit = 5
    assert b.try_reserve() is True


def test_budget_reserve_is_atomic_under_concurrency():
    """并发抢最后几个名额时不能超支。"""
    import threading

    b = DailyBudget(50)
    granted = []
    lock = threading.Lock()

    def worker():
        for _ in range(20):
            ok = b.try_reserve()
            with lock:
                granted.append(ok)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(granted) == 50
    assert b.snapshot()["used"] == 50


# ---------------- RateLimiter ----------------
def test_rate_limiter_allows_up_to_limit():
    rl = RateLimiter(3)
    assert [rl.check("1.2.3.4", now=0.0) for _ in range(3)] == [True, True, True]
    assert rl.check("1.2.3.4", now=0.0) is False


def test_rate_limiter_window_slides():
    rl = RateLimiter(2)
    assert rl.check("ip", now=0.0) is True
    assert rl.check("ip", now=1.0) is True
    assert rl.check("ip", now=2.0) is False
    # 61 秒后最早的请求滑出窗口
    assert rl.check("ip", now=61.0) is True


def test_rate_limiter_isolates_keys():
    rl = RateLimiter(1)
    assert rl.check("a", now=0.0) is True
    assert rl.check("b", now=0.0) is True
    assert rl.check("a", now=0.0) is False


def test_rate_limiter_non_positive_means_unlimited():
    rl = RateLimiter(0)
    assert all(rl.check("ip", now=0.0) for _ in range(500))


# ---------------- public_error_message ----------------
def test_budget_exceeded_message_passes_through():
    exc = BudgetExceeded("今日 AI 调用额度已用尽")
    assert public_error_message(exc) == "今日 AI 调用额度已用尽"


@pytest.mark.parametrize(
    "raw",
    [
        "Invalid api key provided: sk-abc123",
        "Authorization header rejected",
        "bad bearer token",
        "missing secret",
    ],
)
def test_sensitive_exception_text_is_masked(raw):
    out = public_error_message(RuntimeError(raw))
    assert "详情见服务端日志" in out
    assert "sk-abc123" not in out
    assert raw not in out


def test_normal_exception_keeps_brief_detail():
    out = public_error_message(RuntimeError("connection timeout after 30s"))
    assert out == "RuntimeError: connection timeout after 30s"


def test_long_exception_text_is_truncated():
    out = public_error_message(RuntimeError("x" * 500))
    assert len(out) <= len("RuntimeError: ") + 120


def test_empty_exception_message_returns_class_name():
    assert public_error_message(RuntimeError()) == "RuntimeError"


# ---------------- 与 LLM 客户端的集成 ----------------
def test_llm_chat_raises_budget_exceeded_without_network(monkeypatch):
    """预算耗尽时必须在发请求之前就抛错——否则照样花钱。"""
    budget.limit = 1
    budget.try_reserve()          # 占掉唯一名额

    def _should_not_be_called(*a, **k):
        raise AssertionError("预算耗尽后仍然调用了真实 API")

    monkeypatch.setattr(llm.client.chat.completions, "create", _should_not_be_called)

    with pytest.raises(BudgetExceeded):
        llm.chat([{"role": "user", "content": "hi"}])
    assert budget.snapshot()["rejected"] == 1


def test_llm_chat_reserves_before_calling(monkeypatch):
    """成功路径也要占位，否则预算永远用不完。"""
    budget.limit = 5
    monkeypatch.setattr(
        llm.client.chat.completions, "create", lambda **k: type("R", (), {"choices": []})()
    )
    llm.chat([{"role": "user", "content": "hi"}])
    assert budget.snapshot()["used"] == 1


def test_budget_exhaustion_degrades_to_mock_not_error(sse, session, live_mode):
    """核心承诺：额度刷爆后演示不中断，自动走黄金路径。"""
    budget.limit = 1
    budget.try_reserve()

    events = sse("/api/scholar/clarify", {"session_id": session, "message": "我想学扩散模型"})
    kinds = [e["event"] for e in events]

    assert "error" not in kinds
    assert "fallback" in kinds
    assert kinds[-1] == "done"
    assert "token" in kinds
    reason = events[kinds.index("fallback")]["payload"]["reason"]
    assert "额度" in reason


def test_budget_exhaustion_reports_error_when_fallback_disabled(sse, session, live_mode):
    live_mode.fallback_to_mock = False
    budget.limit = 1
    budget.try_reserve()

    events = sse("/api/scholar/clarify", {"session_id": session, "message": "你好"})
    kinds = [e["event"] for e in events]
    assert "error" in kinds
    assert "额度" in events[kinds.index("error")]["payload"]["message"]


# ---------------- 与 HTTP 层的集成 ----------------
def test_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(guard.rate_limiter, "per_minute", 3)
    guard.rate_limiter.reset()

    codes = [client.post("/api/session/create", json={}).status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429


def test_rate_limited_response_carries_cors_header(client, monkeypatch):
    """429 也要带 CORS 头，否则浏览器只报跨域、看不到限流提示。"""
    monkeypatch.setattr(guard.rate_limiter, "per_minute", 1)
    guard.rate_limiter.reset()

    client.post("/api/session/create", json={}, headers={"Origin": "https://app.example.com"})
    r = client.post("/api/session/create", json={}, headers={"Origin": "https://app.example.com"})
    assert r.status_code == 429
    assert "access-control-allow-origin" in r.headers
    assert r.headers.get("retry-after") == "60"


def test_rate_limit_does_not_apply_to_health(client, monkeypatch):
    """探活不能被限流挡住，否则监控会误报。"""
    monkeypatch.setattr(guard.rate_limiter, "per_minute", 1)
    guard.rate_limiter.reset()

    assert [client.get("/health").status_code for _ in range(5)] == [200] * 5


def test_health_exposes_budget_snapshot(client):
    body = client.get("/health").json()
    assert body["llm_budget"]["limit"] == budget.limit
    assert body["llm_budget"]["used"] == 0
    assert "rate_limit_per_minute" in body


def test_startup_logs_guard_configuration(caplog, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    with caplog.at_level(logging.INFO, logger="xuni"):
        with TestClient(app) as c:
            c.get("/health")
    assert any("成本防护" in r.getMessage() for r in caplog.records)
