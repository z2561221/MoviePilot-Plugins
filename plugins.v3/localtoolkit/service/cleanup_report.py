"""清理库存报告的 HTML 排版与单条 Telegram 消息长度控制。"""

from __future__ import annotations

from datetime import datetime
from html import escape

from ..model.library_cleanup import CleanupCandidate, CleanupResult, CleanupVerification

BODY_LIMIT = 2400
FOOTER_LIMIT = 1100
REPORT_TITLE = "周期清理报告"


def _length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _escaped(value: object, limit: int = 80) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ")
    if len(text) > limit:
        text = f"{text[:limit - 1]}…"
    return escape(text, quote=False)


def _movie_name(movie: CleanupCandidate) -> str:
    return _escaped(movie.title or movie.code or movie.movie_id or "未知")


def build_report(
    config: dict,
    result: CleanupResult,
    summary: str,
    checked_at: datetime,
    *,
    phase: str = "",
    verification: CleanupVerification | None = None,
    cycle_stats: dict | None = None,
    precheck_errors: list[tuple[CleanupCandidate, str]] | None = None,
) -> str:
    """生成固定上半部分与可更新底部，始终保留完整 HTML 标签。"""
    favorite_labels = {"all": "收藏不限", "fav": "已收藏", "unfav": "未收藏"}
    played_labels = {"all": "观看不限", "played": "已看过", "unplayed": "未看过"}
    lines = ["<b>筛选条件</b>"]
    for condition in result.conditions:
        lines.append(
            f"{_escaped(condition.title)}：{favorite_labels[condition.favorite]} + "
            f"{played_labels[condition.played]} + 超过 {condition.days_threshold} 天"
        )
    lines.extend([
        "", "<b>检查结果</b>",
        f"{'本轮检查' if phase else '符合条件'}：{result.qualified_count} 部",
        f"自动删除：{'已开启' if config.get('auto_delete', False) else '未开启'}",
    ])
    if summary and not phase:
        lines.append(_escaped(summary, 180))
    if result.qualified_movies:
        lines.extend(["", "<b>本轮清理名单</b>"])
        shown = 0
        for index, movie in enumerate(result.qualified_movies[:20], start=1):
            age = movie.age_days(checked_at)
            age_text = f"{age} 天" if age is not None else "未知"
            date_text = _escaped(movie.date_created[:10] if movie.date_created else "未知", 10)
            row = f"<b>{index:02d}. {_movie_name(movie)}</b>｜{age_text}｜{date_text}"
            if _length("\n".join([*lines, row])) > BODY_LIMIT - 60:
                break
            lines.append(row)
            shown += 1
        if shown < result.qualified_count:
            lines.append(f"另有 {result.qualified_count - shown} 部未展开")
    body = "\n".join(lines).rstrip()
    if not phase:
        return body
    footer = ["<b>本轮清理结果</b>"]
    if phase == "deleting":
        footer.append("⏳ 正在清理，完成后在此更新结果。")
    elif phase == "verifying":
        footer.append("⏳ 正在复核本轮媒体条目，请稍候。")
    elif verification is not None:
        counts = cycle_stats or {}
        footer.extend([
            f"本轮目标：{result.qualified_count} 部",
            f"确认移除：{len(verification.removed)} 部",
            f"条件变化跳过：{counts.get('skipped_count', 0)} 部",
            f"已不存在：{counts.get('already_absent_count', 0)} 部",
            f"仍然存在：{len(verification.remaining)} 部",
            f"无法核验：{counts.get('unknown_count', len(verification.unknown))} 部",
        ])
        if cycle_stats is not None:
            footer.append(f"计划剩余：{counts.get('queue_count', 0)} 部")
        anomalies = [
            (movie, label)
            for label, movies in (("仍然存在", verification.remaining), ("无法核验", verification.unknown))
            for movie in movies
        ]
        anomalies.extend(precheck_errors or [])
        shown = 0
        for movie, label in anomalies:
            row = f"• {_movie_name(movie)}：{_escaped(label)}"
            if _length("\n".join([*footer, row])) > FOOTER_LIMIT - 100:
                break
            footer.append(row)
            shown += 1
        if shown < len(anomalies):
            footer.append(f"另有 {len(anomalies) - shown} 部异常项目未展开")
        complete = not verification.remaining and not counts.get("unknown_count", len(verification.unknown))
        completion = "✅ 本轮删除完毕" if verification.removed else "✅ 本轮检查完成"
        if counts.get("stopped"):
            completion = f"⏹ 本轮已停止，未处理 {counts.get('unprocessed_count', 0)} 部保留"
            complete = True
        footer.extend([
            "",
            completion if complete else "⚠️ 本轮清理未全部完成",
            "核验范围：媒体库条目",
        ])
    return f"{body}\n\n" + "\n".join(footer)
