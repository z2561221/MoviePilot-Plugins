"""只记录响应形状，禁止持久化模型正文、工具参数或原始异常。"""

from collections.abc import Mapping

from pydantic import ValidationError


def response_diagnostic(response, *, phase, forced, tools=()):
    """在 LangChain 解析之后、宿主文本提取之前记录有界统计。"""
    messages = getattr(response, "result", None)
    if not isinstance(messages, (list, tuple)):
        messages = [response]
    reasons = set()
    schema_errors = set()
    tool_map = {tool.name: tool for tool in tools}
    result = {
        "phase": phase,
        "forced_tool_choice": bool(forced),
        "message_count": len(messages),
        "tool_call_count": 0,
        "invalid_tool_call_count": 0,
        "unexpected_tool_call_count": 0,
        "text_chars": 0,
        "reasoning_chars": 0,
    }
    for message in messages:
        result["tool_call_count"] += len(getattr(message, "tool_calls", None) or [])
        result["invalid_tool_call_count"] += len(
            getattr(message, "invalid_tool_calls", None) or []
        )
        for call in getattr(message, "tool_calls", None) or []:
            tool = tool_map.get(call.get("name"))
            if tool is None:
                if tool_map:
                    result["unexpected_tool_call_count"] += 1
                continue
            schema = getattr(tool, "args_schema", None)
            if schema is not None and callable(getattr(schema, "model_validate", None)):
                try:
                    schema.model_validate(call.get("args"))
                except ValidationError as error:
                    schema_errors.update(validation_error_types(error))
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
    result["tool_schema_error_types"] = sorted(schema_errors)[:12]
    result["finish_reasons"] = sorted(reasons)
    return result


def validation_error_types(error):
    """仅保留内建错误类型，丢弃包含输入、字段名或异常文本的诊断。"""
    allowed = {
        "missing", "extra_forbidden", "string_type", "list_type", "dict_type",
        "model_type", "int_parsing", "float_parsing", "literal_error",
        "value_error", "too_short", "too_long",
    }
    return sorted({
        item["type"] if item["type"] in allowed else "other"
        for item in error.errors(include_input=False, include_url=False)
    })[:12]
