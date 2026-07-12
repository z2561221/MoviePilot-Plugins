"""Agent 榜单通知确认服务。"""

from typing import Any

from ..model.board import RecommendationBoard


def _compact_text(value: Any, limit: int) -> str:
    """压缩通知字段中的空白并限制长度，避免榜单列被异常文本撑开。"""
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _format_ranking_block(board: RecommendationBoard) -> str:
    """将最多十条推荐格式化为 Telegram 友好的等宽 Markdown 代码块。"""
    lines = []
    for item in board.recommendations[:10]:
        title = _compact_text(item.title, 42) or "未命名条目"
        summary = _compact_text(item.summary, 64) or "暂无推荐摘要"
        lines.extend(
            [
                f"{int(item.rank):02d} │ {title}",
                f"   │ {summary}",
            ]
        )
    return "```\n" + "\n".join(lines) + "\n```"


class NotificationService:
    """只发送榜单摘要和 UI 操作指引，不建立订阅回调。"""

    def __init__(self, plugin: Any):
        """绑定插件通知扩展点。"""
        self._plugin = plugin

    def send_confirmation(self, username: str, board: RecommendationBoard) -> None:
        """向目标用户发送最多十条推荐摘要。"""
        ranking = _format_ranking_block(board)
        text = f"本轮 Agent 推荐已生成，共 {len(board.recommendations[:10])} 条：\n\n{ranking}"
        text += "\n\n请前往 **Agent榜单中心** 手动订阅；此通知不会自动创建订阅。"
        self._plugin.post_message(
            title="Agent榜单中心推荐确认",
            text=text,
            username=username,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )
