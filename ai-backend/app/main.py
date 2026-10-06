"""FastAPI 入口。

启动：python run.py  或  uvicorn app.main:app --reload
文档：http://127.0.0.1:8000/docs
"""
import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import router
from app.config import settings
from app.core.guard import budget, rate_limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("xuni")


@asynccontextmanager
async def lifespan(app: FastAPI):
    exposed = settings.exposed_to_network
    log.info(
        "X University backend started | model=%s mock=%s listen=%s:%s",
        settings.model, settings.mock_mode, settings.host, settings.port,
    )
    # 只在真正对外监听时才告警：本机演示（127.0.0.1）不该刷 WARNING。
    if settings.api_token:
        log.info("接口鉴权已启用：/api/* 需携带 X-API-Token（或 Authorization: Bearer）")
    elif exposed:
        log.warning(
            "HOST=%s 已对外监听，但 API_TOKEN 为空——同网段任何人都能调用接口、消耗 DeepSeek 额度。"
            "请在 .env 设置 API_TOKEN（生成：python -c \"import secrets; print(secrets.token_urlsafe(32))\"）。",
            settings.host,
        )
    else:
        log.info("接口鉴权未启用（API_TOKEN 为空）；当前仅监听 %s，本机演示无风险。", settings.host)

    if settings.cors_allow_all:
        if exposed:
            log.warning("CORS 允许全部来源（CORS_ORIGINS=*），已自动关闭 allow_credentials。")
        else:
            log.info("CORS 允许全部来源（CORS_ORIGINS=*），仅本机监听，无实际暴露面。")

    log.info(
        "成本防护 | 每日 LLM 调用上限=%s（超出自动降级 mock） | 单 IP 限流=%s 次/分钟",
        budget.limit if budget.limit > 0 else "不限",
        rate_limiter.per_minute if rate_limiter.per_minute > 0 else "不限",
    )
    if exposed and budget.limit <= 0 and rate_limiter.per_minute <= 0:
        log.warning(
            "已对外监听，但预算与限流都未启用（LLM_DAILY_CALL_LIMIT / RATE_LIMIT_PER_MINUTE 为 0），"
            "额度被刷时没有任何刹车。"
        )
    yield
    log.info("X University backend stopped")


app = FastAPI(title="X University AI Backend", version=__version__, lifespan=lifespan)


def _bearer_token(header: str | None) -> str:
    """从 `Authorization: Bearer xxx` 中取出 token。"""
    if not header:
        return ""
    scheme, _, value = header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" else ""


def _token_matches(supplied: str) -> bool:
    """常量时间比较，避免用响应耗时逐字符猜 token。"""
    return secrets.compare_digest(supplied.encode("utf-8"), settings.api_token.encode("utf-8"))


# ---------- 可选 API Token 守卫 ----------
# 注册顺序有讲究：本装饰器必须写在 add_middleware(CORSMiddleware) 之前。
# Starlette 每次 add_middleware 都往栈顶插、后注册的在外层，
# 这样 CORS 会包住鉴权，401 响应也带得上 CORS 头，浏览器才读得到错误信息。
@app.middleware("http")
async def api_token_guard(request: Request, call_next):
    # 未配置 token 时完全放行；/health、/docs 等非 /api 路径不拦。
    if not settings.api_token or not request.url.path.startswith("/api"):
        return await call_next(request)

    supplied = request.headers.get("x-api-token") or _bearer_token(
        request.headers.get("authorization")
    )
    if not supplied or not _token_matches(supplied):
        return JSONResponse(status_code=401, content={"detail": "缺少或错误的 API Token"})
    return await call_next(request)


# 单 IP 限流。注册在 token 守卫之后，因此它更靠外层：
# 未通过鉴权的洪水请求也会被限流，不会绕过这层直接打进来。
@app.middleware("http")
async def rate_limit_guard(request: Request, call_next):
    if not request.url.path.startswith("/api"):
        return await call_next(request)
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.check(client_ip):
        log.warning("触发限流：%s 超过 %s 次/分钟", client_ip, rate_limiter.per_minute)
        return JSONResponse(
            status_code=429,
            content={"detail": "请求过于频繁，请稍后再试"},
            headers={"Retry-After": "60"},
        )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # allow_origins=["*"] 与 allow_credentials=True 在规范上互斥：Starlette 会退化成
    # 「回显任意 Origin + 允许携带凭据」，等于对全网开放。本服务不用 Cookie 鉴权，
    # 因此通配来源时关掉凭据；配置了具体来源才开启。
    allow_credentials=not settings.cors_allow_all,
    # 端点使用 GET / POST / DELETE（见 api/routes.py：DELETE 用于删除会话/项目）。
    # 不放开 PUT / PATCH。
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": __version__,
        "model": settings.model,
        "mock_mode": settings.mock_mode,
        "fallback_to_mock": settings.fallback_to_mock,
        "api_key_configured": bool(settings.api_key),
        "auth_enabled": bool(settings.api_token),
        # 成本监控：用来看今天还剩多少额度、有没有人在刷
        "llm_budget": budget.snapshot(),
        "rate_limit_per_minute": rate_limiter.per_minute,
    }
