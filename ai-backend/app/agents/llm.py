"""DeepSeek 官方 API 封装（OpenAI 兼容协议）。

- chat():      普通/流式对话，返回文本或流式迭代器
- chat_json(): 强制 JSON 输出，解析失败自动带错误信息重试一次
所有异常向上抛出，由各 Agent 决定是否降级到 mock。
"""
import logging
from typing import Any, Iterator, Optional

from openai import OpenAI

from app.config import settings
from app.core.guard import BudgetExceeded, budget
from app.core.json_utils import extract_json

log = logging.getLogger("llm")


class EmptyResponseError(RuntimeError):
    """The provider ended a stream without a visible answer."""


class LLMClient:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.api_key or "missing-key", base_url=settings.base_url)
        self.model = settings.model

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        response_format: Optional[dict[str, str]] = None,
    ) -> Any:
        # 所有真实调用都从这里出去，所以预算检查放在这一个收口上即可。
        # 超限时抛 BudgetExceeded，由各 Agent 既有的 try/except 降级到 mock，
        # 调用方无需感知（这也是为什么选抛异常而不是返回 None）。
        if not budget.try_reserve():
            budget.reject()
            log.warning("当日 LLM 调用预算已用尽（上限 %s 次），本次请求降级到 mock", budget.limit)
            raise BudgetExceeded(
                f"今日 AI 调用额度已用尽（上限 {budget.limit} 次），已自动切换为演示模式"
            )

        kwargs: dict[str, Any] = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )
        if response_format:
            kwargs["response_format"] = response_format
        return self.client.chat.completions.create(**kwargs)

    def stream_text(self, messages, temperature=0.7, max_tokens=2048) -> Iterator[str]:
        stream = self.chat(messages, temperature=temperature, max_tokens=max_tokens, stream=True)
        has_text = False
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                has_text = has_text or bool(delta.content.strip())
                yield delta.content
        if not has_text:
            raise EmptyResponseError("模型未返回回答正文，请重试")

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        retries: int = 1,
    ) -> dict[str, Any]:
        # DeepSeek JSON Output 模式：强制模型返回合法 JSON（不带 Markdown 围栏/解释文字），
        # 大幅降低解析失败率。要求 prompt 中出现 "json" 字样（两个 JSON 类提示词均已包含）。
        attempt_messages = list(messages)
        last_error = "未知错误"
        raw_text = ""
        for attempt in range(retries + 1):
            try:
                raw = self.chat(
                    attempt_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False,
                    response_format={"type": "json_object"},
                )
            except Exception as exc:
                # 模型不支持 json_object 时（例如个别供应商兼容层），退化为普通输出，
                # 仍然走 extract_json 容错解析，不让 JSON 模式变成新的故障点。
                log.warning("response_format=json_object 不受支持，退回普通输出：%s", exc)
                raw = self.chat(
                    attempt_messages, temperature=temperature, max_tokens=max_tokens, stream=False
                )
            # 兼容 ChatCompletion 对象与纯文本响应，统一取文本
            if hasattr(raw, "choices") and raw.choices:
                raw_text = raw.choices[0].message.content or ""
            elif isinstance(raw, str):
                raw_text = raw
            else:
                raw_text = str(raw)
            data = extract_json(raw_text)
            if isinstance(data, dict):
                return data
            last_error = "模型输出中未找到合法 JSON 对象"
            log.warning("chat_json parse failed (attempt %s): %s", attempt + 1, last_error)
            attempt_messages = list(messages) + [
                {"role": "assistant", "content": (raw_text or "")[:1500]},
                {
                    "role": "user",
                    "content": "你上一条回复无法被解析为 JSON。请严格只输出一个合法 JSON 对象，"
                    "不要输出 Markdown 代码块、注释或任何解释文字。",
                },
            ]
        raise RuntimeError(f"JSON 解析失败：{last_error}；原始输出前 200 字：{raw_text[:200]!r}")


llm = LLMClient()
