"""全局配置：从 .env / 环境变量读取。"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


class Settings:
    def __init__(self) -> None:
        self.api_key: str = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        # 官方模型 ID：deepseek-flash（V4 Flash）/ deepseek-v4-pro
        self.model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip()
        self.mock_mode: bool = _bool("MOCK_MODE")
        self.fallback_to_mock: bool = _bool("LLM_FALLBACK_TO_MOCK", "true")
        self.data_dir: Path = BASE_DIR / os.getenv("DATA_DIR", "data")
        # 可选鉴权：为空表示不校验（仅适合本地演示）。公网暴露前务必设置。
        self.api_token: str = os.getenv("API_TOKEN", "").strip()
        self.cors_origins: str = os.getenv("CORS_ORIGINS", "*")
        # 监听地址。默认 127.0.0.1 = 只有本机能访问；
        # 手机 / 其他设备要连进来，必须改成 0.0.0.0（见 README「路演接入」）。
        self.host: str = os.getenv("HOST", "127.0.0.1").strip() or "127.0.0.1"
        self.port: int = _int("PORT", 8000)
        self.reload: bool = _bool("RELOAD", "true")
        # 成本防护：每日 LLM 调用上限（<=0 不限制）与单 IP 每分钟请求上限（<=0 不限制）。
        # 超预算不会中断服务，而是自动降级到 mock（见 app/core/guard.py）。
        self.llm_daily_call_limit: int = _int("LLM_DAILY_CALL_LIMIT", 300)
        # 默认给得比较宽：它的目标是拦住失控循环/脚本刷接口，不是给正常演示设卡。
        # 注意走隧道时所有用户共享一个来源 IP，等于全局限流，别调太小。
        self.rate_limit_per_minute: int = _int("RATE_LIMIT_PER_MINUTE", 120)

        # ---------- 向量 RAG（第二阶段升级） ----------
        # RAG 检索模式：hybrid（BM25+向量 RRF 融合，默认）/ vector（仅向量）/ bm25（仅关键词）
        self.rag_mode: str = os.getenv("RAG_MODE", "hybrid").strip().lower()
        # Embedding 后端：
        #   auto（默认，按下面顺序探测）/ api（OpenAI 兼容端点）/ fastembed（本地 ONNX，可选依赖）
        #   hash（零依赖确定性哈希，测试/兜底）/ none（关闭向量路）
        self.embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "auto").strip().lower()
        self.embedding_base_url: str = os.getenv("EMBEDDING_BASE_URL", "").strip().rstrip("/")
        self.embedding_api_key: str = os.getenv("EMBEDDING_API_KEY", "").strip()
        # 硅基流动（免费 BGE）示例：BAAI/bge-m3；OpenAI：text-embedding-3-small
        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3").strip()
        # fastembed 本地模型（仅 EMBEDDING_PROVIDER=fastembed 时使用）
        self.embedding_local_model: str = os.getenv(
            "EMBEDDING_LOCAL_MODEL", "BAAI/bge-small-zh-v1.5"
        ).strip()

        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def exposed_to_network(self) -> bool:
        """是否监听在非回环地址上（意味着同网段 / 公网可访问）。"""
        return self.host not in ("127.0.0.1", "localhost", "::1")

    @property
    def cors_allow_all(self) -> bool:
        return self.cors_origins.strip() == "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_allow_all:
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
