"""成本与滥用防护：每日 LLM 调用预算、单 IP 限流、对外错误脱敏。

设计取向：**超支时降级，不是拒绝服务。**
本项目已经有完整的 MOCK 降级链路，所以预算耗尽后自动走预制黄金路径——
路演现场即使额度被人刷爆，评委扫码依然能走完整个流程，只是不再产生费用。
这比直接返 429 更贴合「演示不能中断」这个硬需求。

局限（要清楚）：这些都是**单进程内存**实现，重启即清零，多实例之间不共享。
用于路演 / 单机部署足够；要真正防住有组织的滥用，需要 Redis + 网关层限流。
"""
import logging
import threading
import time
from collections import deque
from datetime import date, datetime

from app.config import settings

log = logging.getLogger("guard")


class BudgetExceeded(RuntimeError):
    """当日 LLM 调用预算已用尽。"""


def _today() -> date:
    return datetime.now().date()


class DailyBudget:
    """按服务器本地日期重置的调用计数器。limit <= 0 表示不限制。"""

    def __init__(self, limit: int) -> None:
        self._lock = threading.Lock()
        self._limit = limit
        self._day = _today()
        self._used = 0
        self._rejected = 0

    @property
    def limit(self) -> int:
        return self._limit

    @limit.setter
    def limit(self, value: int) -> None:
        self._limit = int(value)

    def _rollover(self) -> None:
        today = _today()
        if today != self._day:
            log.info("LLM 调用预算跨天重置：%s -> %s", self._day, today)
            self._day, self._used, self._rejected = today, 0, 0

    def try_reserve(self) -> bool:
        """原子地「检查并占位」。

        刻意做成一次操作而不是 allow() + record() 两步：并发下两步会有竞态，
        最后几个名额可能被多个请求同时抢到，导致超支。
        用在发起真实调用之前——宁可占位后调用失败（浪费 1 次额度），也不要超支。
        """
        if self._limit <= 0:
            return True
        with self._lock:
            self._rollover()
            if self._used >= self._limit:
                return False
            self._used += 1
            if self._used == int(self._limit * 0.8):
                log.warning("LLM 调用预算已用掉 80%%（%s/%s）", self._used, self._limit)
            return True

    def reject(self) -> None:
        with self._lock:
            self._rollover()
            self._rejected += 1

    def snapshot(self) -> dict:
        with self._lock:
            self._rollover()
            return {
                "day": self._day.isoformat(),
                "limit": self._limit,
                "used": self._used,
                "remaining": None if self._limit <= 0 else max(self._limit - self._used, 0),
                "rejected": self._rejected,
            }

    def reset(self) -> None:
        with self._lock:
            self._day = _today()
            self._used = 0
            self._rejected = 0


class RateLimiter:
    """单 IP 滑动窗口限流。per_minute <= 0 表示不限制。

    注意：走隧道（ngrok / frp）时所有请求的来源 IP 都是隧道本机，
    等于退化成全局限流——仍然能挡住失控循环，但区分不出具体客户端。
    """

    def __init__(self, per_minute: int) -> None:
        self._lock = threading.Lock()
        self._per_minute = per_minute
        self._hits: dict[str, deque[float]] = {}

    @property
    def per_minute(self) -> int:
        return self._per_minute

    @per_minute.setter
    def per_minute(self, value: int) -> None:
        self._per_minute = int(value)

    def check(self, key: str, now: float | None = None) -> bool:
        if self._per_minute <= 0:
            return True
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] > 60.0:
                q.popleft()
            if len(q) >= self._per_minute:
                return False
            q.append(now)
            # 桶太多时清理空桶，避免长期运行内存无限增长
            if len(self._hits) > 4096:
                for k in [k for k, v in self._hits.items() if not v]:
                    self._hits.pop(k, None)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# 这些词一旦出现在异常文案里，就不该原样透给客户端
_SENSITIVE_HINTS = ("api key", "apikey", "authorization", "bearer", "sk-", "secret")


def public_error_message(exc: BaseException) -> str:
    """把异常转成可以安全回给客户端的文案。

    为什么必须脱敏：各 Agent 的 error / fallback 事件会把文案经 SSE 直接推给浏览器，
    而 SDK 异常的字符串里可能带上请求 URL、请求体片段甚至凭据。完整信息只写服务端日志。
    """
    if isinstance(exc, BudgetExceeded):
        return str(exc)

    name = type(exc).__name__
    text = str(exc).strip()
    if not text:
        return name
    if any(hint in text.lower() for hint in _SENSITIVE_HINTS):
        log.warning("异常文案含敏感字样，已脱敏后再返回客户端：%s", text[:200])
        return f"{name}（详情见服务端日志）"
    # 截断，限制意外信息泄漏面
    return f"{name}: {text[:120]}"


# 进程内单例（与 app.memory.store 同样的做法）
budget = DailyBudget(settings.llm_daily_call_limit)
rate_limiter = RateLimiter(settings.rate_limit_per_minute)
