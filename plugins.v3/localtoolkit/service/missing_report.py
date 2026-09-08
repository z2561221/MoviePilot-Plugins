"""缺集报告的分组排版与单条消息预算。"""

from __future__ import annotations

import re
from html import escape

REPORT_LIMIT = 3200


def _safe_text(value: object, limit: int = 72) -> str:
    """折叠换行、限制字段长度并转义动态 HTML 文本。"""
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        text = text[:limit - 1] + "…"
    return escape(text, quote=False)


def _episode_ranges(episodes: list[int]) -> str:
    """合并连续缺集并明确提示未展示的区间。"""
    values = sorted(set(episodes))
    if not values:
        return ""
    ranges = []
    start = end = values[0]
    for episode in values[1:]:
        if episode == end + 1:
            end = episode
            continue
        ranges.append(str(start) if start == end else f"{start}~{end}")
        start = end = episode
    ranges.append(str(start) if start == end else f"{start}~{end}")
    text = ", ".join(ranges[:8])
    if len(ranges) > 8:
        text += f"（另有 {len(ranges) - 8} 个区间）"
    return text


def build_missing_report(results: list[dict], summary: str) -> str:
    """按路径、剧集和季度渲染完整条目，保留总数及截断提示。"""
    groups: dict[str, list[dict]] = {}
    for item in results:
        groups.setdefault(str(item.get("path") or "未命名路径"), []).append(item)
    lines = [_safe_text(summary, 160)]
    shown = 0
    for path, items in groups.items():
        first = True
        for item in items:
            if item.get("status") == "not_exists":
                row = "路径不存在，未能扫描。"
            elif item.get("missing"):
                title = re.sub(r"\s*\[tmdb(id)?=[^\]]*\]", "", str(item.get("title") or "未命名剧集"))
                row = (
                    f"<b>{_safe_text(title)} · S{int(item.get('season') or 1):02d}</b>\n"
                    f"缺集：{_episode_ranges(item['missing'])}"
                )
            else:
                row = "未发现缺集。"
            addition = ["", f"<b>{_safe_text(path)}</b>", row] if first else ["", row]
            candidate = "\n".join([*lines, *addition])
            if len(candidate.encode("utf-16-le")) // 2 > REPORT_LIMIT - 100:
                lines.extend(["", f"另有 {len(results) - shown} 项未展开，请查看插件详情。"])
                return "\n".join(lines)
            lines.extend(addition)
            shown += 1
            first = False
    if not results:
        lines.extend(["", "未发现缺集。"])
    return "\n".join(lines)
