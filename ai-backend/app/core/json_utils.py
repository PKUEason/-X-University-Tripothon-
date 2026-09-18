"""从模型输出中稳健地提取 JSON（容忍 Markdown 代码块、前后缀解释文字）。"""
import json
import re
from typing import Any, Optional


def _balanced_slice(text: str, open_ch: str, close_ch: str) -> Optional[str]:
    """从第一个 open_ch 开始做带字符串感知的括号配对，返回最外层切片。"""
    start = text.find(open_ch)
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    quote = ""
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str = True
            quote = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _try_loads(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except Exception:
        pass
    # 容忍尾逗号
    cleaned = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(cleaned)
    except Exception:
        return None


def extract_json(text: str) -> Optional[Any]:
    """优先整体解析，失败后依次尝试代码块 / 花括号 / 方括号配对切片。"""
    if not text:
        return None
    text = text.strip()
    result = _try_loads(text)
    if result is not None:
        return result

    fence = re.search(r"```(?:json|JSON)?\s*(.*?)```", text, re.S)
    if fence:
        result = _try_loads(fence.group(1).strip())
        if result is not None:
            return result

    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        slice_ = _balanced_slice(text, open_ch, close_ch)
        if slice_:
            result = _try_loads(slice_)
            if result is not None:
                return result
    return None
