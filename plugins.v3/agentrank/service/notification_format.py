"""通知文本转义和 Telegram 长度预算。"""

import html
from typing import Any


def utf16_units(text: str) -> int:
    """按 Telegram 使用的 UTF-16 单元计数。"""
    return len(text.encode("utf-16-le")) // 2


def compact_html(value: Any, limit: int) -> str:
    """在转义后的长度预算内截断完整字符，保留完整 HTML 实体。"""
    text = " ".join(str(value or "").split())
    escaped = html.escape(text)
    if utf16_units(escaped) <= limit:
        return escaped
    if limit <= 0:
        return ""
    pieces = []
    remaining = limit - 1
    for char in text:
        escaped_char = html.escape(char)
        size = utf16_units(escaped_char)
        if size > remaining:
            break
        pieces.append(escaped_char)
        remaining -= size
    return "".join(pieces) + "…"


def caption_units(title: str, text: str, link: str = "") -> int:
    """保守计入宿主生成的标题、HTML 标记及详情链接。"""
    caption = f"<b>{html.escape(title)}</b>\n{text}"
    if link:
        caption += f'\n<a href="{html.escape(link, quote=True)}">查看详情</a>'
    return utf16_units(caption)
