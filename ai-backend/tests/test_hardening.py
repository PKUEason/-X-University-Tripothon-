"""加固项回归：CORS 收敛、可选 API Token 鉴权、lifespan 生命周期。

这三项平时不影响功能，只在「把后端暴露出去」时才起作用，
所以最容易在后续改动中被无声改回去——用测试钉住。
"""
import logging
import warnings

import pytest
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

from app.config import Settings, settings
from app.main import app

EVIL = "https://evil.example.com"


def _cors_kwargs() -> dict:
    """取出 CORSMiddleware 实际被配置的参数（不靠猜，直接读注册表）。"""
    for mw in app.user_middleware:
        if getattr(mw, "cls", None) is CORSMiddleware:
            return mw.kwargs
    raise AssertionError("CORSMiddleware 未注册")


@pytest.fixture()
def token_on(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "s3cret-token-value")
    return "s3cret-token-value"


# ---------------- CORS ----------------
def test_cors_wildcard_drops_credentials(client):
    """回归：allow_origins=['*'] 配 allow_credentials=True 时，Starlette 会
    回显任意 Origin 并允许携带凭据，等于对全网开放。现在必须不带凭据头。"""
    r = client.get("/health", headers={"Origin": EVIL})
    assert r.headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-credentials" not in r.headers


def test_cors_methods_limited_to_get_post_delete(client):
    r = client.options(
        "/api/session/create",
        headers={"Origin": EVIL, "Access-Control-Request-Method": "POST"},
    )
    allow = r.headers.get("access-control-allow-methods", "")
    assert "POST" in allow
    assert "DELETE" in allow  # 删除会话/项目需要
    for verb in ("PUT", "PATCH"):
        assert verb not in allow


def test_cors_rejects_disallowed_method(client):
    r = client.options(
        "/api/session/create",
        headers={"Origin": EVIL, "Access-Control-Request-Method": "PUT"},
    )
    assert r.status_code == 400


def test_cors_middleware_config_is_introspectable():
    kwargs = _cors_kwargs()
    assert kwargs["allow_methods"] == ["GET", "POST", "DELETE"]
    # 默认 CORS_ORIGINS=*，凭据必须是关的
    assert kwargs["allow_credentials"] is False


@pytest.mark.parametrize(
    "raw,allow_all,expected",
    [
        ("*", True, ["*"]),
        ("https://a.com,https://b.com", False, ["https://a.com", "https://b.com"]),
        (" https://a.com , https://b.com ", False, ["https://a.com", "https://b.com"]),
        ("", False, []),
    ],
)
def test_cors_origin_parsing(monkeypatch, raw, allow_all, expected):
    monkeypatch.setattr(settings, "cors_origins", raw)
    assert settings.cors_allow_all is allow_all
    assert settings.cors_origin_list == expected


# ---------------- API Token ----------------
def test_token_disabled_by_default(client):
    assert settings.api_token == ""
    assert client.post("/api/session/create", json={}).status_code == 200
    assert client.get("/health").json()["auth_enabled"] is False


def test_api_rejects_missing_token(client, token_on):
    r = client.post("/api/session/create", json={})
    assert r.status_code == 401
    assert "API Token" in r.json()["detail"]


def test_api_rejects_wrong_token(client, token_on):
    r = client.post("/api/session/create", json={}, headers={"X-API-Token": "wrong"})
    assert r.status_code == 401


def test_api_accepts_header_token(client, token_on):
    r = client.post("/api/session/create", json={}, headers={"X-API-Token": token_on})
    assert r.status_code == 200


def test_api_accepts_bearer_token(client, token_on):
    r = client.post(
        "/api/session/create", json={}, headers={"Authorization": f"Bearer {token_on}"}
    )
    assert r.status_code == 200


def test_health_and_docs_bypass_token(client, token_on):
    assert client.get("/health").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_token_guard_still_returns_404_for_unknown_session(client, token_on):
    """鉴权通过后，业务错误码不能被鉴权层吞掉。"""
    r = client.post(
        "/api/scholar/roadmap", json={"session_id": "ghost"}, headers={"X-API-Token": token_on}
    )
    assert r.status_code == 404


def test_401_carries_cors_headers(client, token_on):
    """401 必须带 CORS 头，否则浏览器只会报跨域错误、看不到真正的鉴权提示。

    这依赖中间件注册顺序：CORS 要包在鉴权外层。
    """
    r = client.post("/api/session/create", json={}, headers={"Origin": EVIL})
    assert r.status_code == 401
    assert "access-control-allow-origin" in r.headers


def test_health_reports_auth_enabled(client, token_on):
    assert client.get("/health").json()["auth_enabled"] is True


# ---------------- lifespan ----------------
def test_startup_uses_lifespan_not_deprecated_on_event():
    """回归：@app.on_event('startup') 在新版 FastAPI 已 deprecated，启动会告警。"""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with TestClient(app) as c:
            assert c.get("/health").status_code == 200
    offenders = [str(w.message) for w in caught if "on_event" in str(w.message)]
    assert not offenders, f"仍有 on_event 弃用告警：{offenders}"


def test_lifespan_runs_startup_and_shutdown():
    """with TestClient 会走完整生命周期，两次进出都应正常（不抛异常）。"""
    with TestClient(app) as c:
        assert c.get("/health").json()["status"] == "ok"
    with TestClient(app) as c:
        assert c.get("/health").json()["status"] == "ok"


# ---------------- 监听地址 ----------------
@pytest.mark.parametrize(
    "host,exposed",
    [
        ("127.0.0.1", False),
        ("localhost", False),
        ("::1", False),
        ("0.0.0.0", True),
        ("192.168.1.23", True),
    ],
)
def test_exposed_to_network(monkeypatch, host, exposed):
    monkeypatch.setattr(settings, "host", host)
    assert settings.exposed_to_network is exposed


def test_settings_reads_listen_env(monkeypatch):
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9001")
    monkeypatch.setenv("RELOAD", "false")
    s = Settings()
    assert s.host == "0.0.0.0"
    assert s.port == 9001
    assert s.reload is False
    assert s.exposed_to_network is True


def test_invalid_port_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("PORT", "not-a-number")
    assert Settings().port == 8000


def test_blank_host_falls_back_to_loopback(monkeypatch):
    monkeypatch.setenv("HOST", "   ")
    assert Settings().host == "127.0.0.1"


def test_lan_ip_returns_usable_address():
    """启动横幅要用它提示手机访问地址，不能返回空值。"""
    from run import lan_ip

    ip = lan_ip()
    assert ip and ip.count(".") == 3


# ---------------- 启动告警的时机 ----------------
def _startup_warnings(caplog) -> list[str]:
    with caplog.at_level(logging.WARNING, logger="xuni"):
        with TestClient(app) as c:
            assert c.get("/health").status_code == 200
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == "xuni" and r.levelno >= logging.WARNING
    ]


def test_local_demo_has_no_startup_warning(caplog, monkeypatch):
    """本机演示不该刷 WARNING——告警只在真正暴露时才有意义。"""
    monkeypatch.setattr(settings, "host", "127.0.0.1")
    monkeypatch.setattr(settings, "api_token", "")
    assert _startup_warnings(caplog) == []


def test_warns_when_exposed_without_token(caplog, monkeypatch):
    monkeypatch.setattr(settings, "host", "0.0.0.0")
    monkeypatch.setattr(settings, "api_token", "")
    warnings_ = _startup_warnings(caplog)
    assert any("API_TOKEN 为空" in m for m in warnings_)


def test_no_token_warning_when_exposed_with_token(caplog, monkeypatch):
    monkeypatch.setattr(settings, "host", "0.0.0.0")
    monkeypatch.setattr(settings, "api_token", "configured")
    warnings_ = _startup_warnings(caplog)
    assert not any("API_TOKEN 为空" in m for m in warnings_)
