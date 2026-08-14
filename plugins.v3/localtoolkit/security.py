"""工具中心敏感信息脱敏工具。"""

from __future__ import annotations

import re
from typing import Any


_KEY_VALUE_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|password|passwd|secret|cookie|authorization)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)(bearer\s+)([^\s,;]+)")
_URL_CREDENTIAL_PATTERN = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://)([^/@\s:]+):([^@/\s]+)@")


def redact_sensitive_text(value: Any) -> str:
    """隐藏异常、URL 和配置文本中的常见凭据。"""
    text = str(value or "")
    text = _URL_CREDENTIAL_PATTERN.sub(r"\1***:***@", text)
    text = _BEARER_PATTERN.sub(r"\1***", text)
    text = _KEY_VALUE_PATTERN.sub(r"\1\2***", text)
    return text


def safe_error_text(context: str = "操作") -> str:
    """返回适合 API、历史和通知展示的通用错误文案。"""
    return f"{context}失败，请查看插件日志"
