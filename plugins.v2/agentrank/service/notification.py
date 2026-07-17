"""Agent 榜单通知确认服务。"""

import logging
from typing import Any

from app.schemas.types import NotificationType

from ..model.board import RecommendationBoard


logger = logging.getLogger(__name__)


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
        reason = _compact_text(getattr(item, "reason", ""), 32) or summary
        lines.extend(
            [
                f"{int(item.rank):02d} │ {title}",
                f"   │ 推荐：{reason}",
                f"   │ 简介：{summary}",
            ]
        )
    return "```\n" + "\n".join(lines) + "\n```"


class NotificationService:
    """优先发送 Telegram 自选订阅卡片，并保留摘要降级。"""

    def __init__(self, plugin: Any, interaction_service: Any = None):
        """绑定插件通知扩展点与可选 Telegram 交互服务。"""
        self._plugin = plugin
        self._interaction_service = interaction_service

    def send_confirmation(self, username: str, board: RecommendationBoard) -> None:
        """发送海报轮播；用户未绑定 Telegram 时降级为摘要。"""
        if self._interaction_service is not None:
            try:
                if self._interaction_service.start(username, board):
                    return
            except Exception:
                # Telegram 交互异常不得阻断榜单通知的摘要降级路径。
                logger.exception(
                    "AgentRank Telegram 交互通知失败，回退摘要 user=%s", username
                )
        ranking = _format_ranking_block(board)
        text = f"本轮 Agent 推荐已生成，共 {len(board.recommendations[:10])} 条：\n\n{ranking}"
        text += "\n\n请前往 **Agent榜单中心** 手动订阅；此通知不会自动创建订阅。"
        self._plugin.post_message(
            mtype=NotificationType.Subscribe,
            title="Agent榜单中心推荐确认",
            text=text,
            username=username,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )

    def send_failure(
        self,
        username: str,
        status: str,
        run_id: str,
        message: str,
        old_board_preserved: bool,
    ) -> None:
        """向目标用户发送一次简洁的 Agent 运行异常通知。"""
        reason = _compact_text(message, 240) or "未知异常"
        lines = [
            f"状态：{_compact_text(status, 48)}",
            f"运行 ID：{_compact_text(run_id, 64) or '未生成'}",
            f"原因：{reason}",
            "旧榜单：已保留" if old_board_preserved else "旧榜单：无可用数据",
        ]
        self._plugin.post_message(
            mtype=NotificationType.Subscribe,
            title="Agent榜单中心运行异常",
            text="\n".join(lines),
            username=username,
        )
