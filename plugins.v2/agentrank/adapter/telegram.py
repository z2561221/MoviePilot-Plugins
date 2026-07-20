"""AgentRank Telegram 交互目标适配器。"""

from typing import Optional


class TelegramTargetAdapter:
    """在没有独立身份绑定时安全禁用定向 Telegram 交互。"""

    @staticmethod
    def resolve_userid(_username: str) -> Optional[str]:
        """返回未绑定状态，使通知服务回退到非定向摘要。"""
        return None
