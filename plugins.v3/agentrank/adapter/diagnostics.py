"""只记录响应形状，禁止持久化模型正文、工具参数或原始异常。"""

from collections.abc import Mapping


def response_diagnostic(response, *, phase, forced):
    """在 LangChain 解析之后、宿主文本提取之前记录有界统计。"""
    messages = getattr(response, "result", None)
    if not isinstance(messages, (list, tuple)):
        messages = [response]
    reasons = set()
    result = {
        "phase": phase,
        "forced_tool_choice": bool(forced),
        "message_count": len(messages),
        "tool_call_count": 0,
        "invalid_tool_call_count": 0,
        "text_chars": 0,
        "reasoning_chars": 0,
    }
    for message in messages:
        result["tool_call_count"] += len(getattr(message, "tool_calls", None) or [])
        result["invalid_tool_call_count"] += len(
            getattr(message, "invalid_tool_calls", None) or []
        )
        content = getattr(message, "content", "")
        if isinstance(content, str):
            result["text_chars"] += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, str):
                    result["text_chars"] += len(block)
                elif isinstance(block, Mapping):
                    key = "reasoning_chars" if block.get("type") in {
                        "reasoning", "thinking", "reasoning_text"
                    } else "text_chars"
                    value = block.get("text", block.get("thinking", ""))
                    if isinstance(value, str):
                        result[key] += len(value)
        additional = getattr(message, "additional_kwargs", None) or {}
        reasoning = additional.get("reasoning_content", "")
        if isinstance(reasoning, str):
            result["reasoning_chars"] += len(reasoning)
        metadata = getattr(message, "response_metadata", None) or {}
        reason = metadata.get("finish_reason", metadata.get("stop_reason"))
        reasons.add(reason if isinstance(reason, str) and reason in {
            "stop", "length", "tool_calls", "function_call", "content_filter",
            "end_turn", "max_tokens", "tool_use", "stop_sequence"
        } else "unknown")
    result["finish_reasons"] = sorted(reasons)
    return result
