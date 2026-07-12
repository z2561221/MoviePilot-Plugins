"""Agent 榜单通知确认服务。"""

from typing import Any

from ..model.board import RecommendationBoard


class NotificationService:
    """只发送榜单摘要和 UI 操作指引，不建立订阅回调。"""

    def __init__(self, plugin: Any):
        """绑定插件通知扩展点。"""
        self._plugin = plugin

    def send_confirmation(self, username: str, board: RecommendationBoard) -> None:
        """向目标用户发送最多十条推荐摘要。"""
        lines = [
            f"{item.rank}. {item.title}｜{item.summary}"
            for item in board.recommendations[:10]
        ]
        text = "本轮 Agent 推荐已生成：\n" + "\n".join(lines)
        text += "\n\n请前往 Agent榜单中心手动订阅；此通知不会自动创建订阅。"
        self._plugin.post_message(
            title="Agent榜单中心推荐确认",
            text=text,
            username=username,
        )
