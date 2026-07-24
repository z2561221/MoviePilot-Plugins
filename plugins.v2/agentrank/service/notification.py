"""Agent 榜单通知确认服务。"""

import logging
import re
from typing import Any

from app.schemas.types import NotificationType

from ..model.board import RecommendationBoard


logger = logging.getLogger(__name__)


STATUS_LABELS = {
    "playback_unavailable": "播放数据不可用",
    "emby_unavailable": "Emby 不可用",
    "permission_error": "权限不足",
    "transient_error": "临时错误",
    "configuration_error": "配置错误",
    "sample_insufficient": "播放样本不足",
    "candidate_insufficient": "候选数量不足",
    "recommendation_incomplete": "推荐榜单不足",
    "profile_agent_failed": "画像 Agent 调用失败",
    "profile_validation_failed": "画像输出校验失败",
    "profile_save_failed": "画像保存失败",
    "candidate_failed": "候选采集失败",
    "candidate_filter_failed": "候选过滤失败",
    "candidate_snapshot_failed": "候选快照失败",
    "ranking_agent_failed": "排序 Agent 调用失败",
    "ranking_validation_failed": "排序输出校验失败",
    "ranking_save_failed": "榜单保存失败",
    "subscription_partial_failed": "部分订阅失败",
    "validation_failed": "输出校验失败",
    "agent_failed": "Agent 调用失败",
    "failed": "运行失败",
}


def _safe_notice_text(value: Any) -> str:
    """移除异常消息中的地址、凭据与稳定 Emby 身份细节。"""
    text = str(value or "")
    text = re.sub(r"https?://[^\s,;]+", "[地址已隐藏]", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b",
        "[地址已隐藏]",
        text,
    )
    text = re.sub(r"\bemby:[^\s,;]+", "[Emby身份已隐藏]", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b(?:api[_ -]?key|token|password|authorization|user[_ -]?id|userid|host|address|base[_ -]?url)\s*[:=]\s*[^\s,;]+",
        "[敏感信息已隐藏]",
        text,
        flags=re.IGNORECASE,
    )
    return text


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
                if self._interaction_service.start(board.profile_id, username, board):
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
        reason = _compact_text(_safe_notice_text(message), 240) or "未知异常"
        lines = [
            f"状态：{STATUS_LABELS.get(str(status or ''), _compact_text(status, 48))}",
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
