"""扫描和清理的持续异常去重及恢复通知。"""

from datetime import datetime
from hashlib import sha256

from ..model.library_cleanup import parse_datetime

ALERT_DATA_KEY = "library_cleanup_alerts"
ALERT_INTERVAL_SECONDS = 24 * 60 * 60


class CleanupAlerts:
    """按操作持久化异常；成功发送才开始通知冷却。"""

    def __init__(self, plugin, config: dict, send):
        """复用当前插件的数据命名空间与通知路由。"""
        self.plugin = plugin
        self.config = config
        self.send = send

    def _load(self) -> dict:
        """忽略损坏的历史提醒状态。"""
        data = self.plugin.get_data(key=ALERT_DATA_KEY)
        return dict(data) if isinstance(data, dict) else {}

    def fail(
        self,
        operation: str,
        category: str,
        text: str,
        now: datetime,
        identities: list[str] | None = None,
    ) -> bool | None:
        """首次异常或通知冷却到期时发送，失败时保留后续重试机会。"""
        data = self._load()
        previous = data.get(operation)
        previous = previous if isinstance(previous, dict) else {}
        scope = tuple(str(self.config.get(key) or "") for key in
                      ("selected_server", "selected_library", "selected_user"))
        fingerprint = sha256(repr((scope, category)).encode("utf-8")).hexdigest()
        state = previous if previous.get("fingerprint") == fingerprint else {
            "fingerprint": fingerprint, "notified": False, "last_notified_at": "",
        }
        message = "删除前媒体状态持续无法核验" if category == "precheck_unavailable" else text
        state.update(
            active=True,
            message=message,
            category=category,
            identities=sorted({str(identity) for identity in (identities or []) if identity}),
        )
        last = parse_datetime(state.get("last_notified_at"))
        due = last is None or (now - last).total_seconds() >= ALERT_INTERVAL_SECONDS
        sent = None
        if due and self.config.get(f"{operation}_notify", True):
            title = "清理计划扫描异常" if operation == "scan" else "周期清理异常"
            sent = self.send(operation, title, text)
            if sent and getattr(sent, "confirmed", True):
                state.update(notified=True, last_notified_at=now.isoformat())
            elif sent:
                state["delivery_state"] = getattr(sent, "state", "queued")
        data[operation] = state
        self.plugin.save_data(key=ALERT_DATA_KEY, value=data)
        return sent

    def recover(self, operation: str, identities: list[str] | None = None) -> None:
        """仅在对应操作真实恢复后提醒一次，空计划和冷却跳过不算恢复。"""
        data = self._load()
        state = data.get(operation)
        if not isinstance(state, dict):
            return
        failed = {str(identity) for identity in state.get("identities", []) if identity}
        current = {str(identity) for identity in (identities or []) if identity}
        if failed and not failed.issubset(current):
            return
        state["active"] = False
        if state.get("notified") and self.config.get(f"{operation}_notify", True):
            title = "清理计划扫描恢复" if operation == "scan" else "周期清理恢复"
            if not self.send(operation, title, "本次访问与处理已恢复，后续继续按独立周期执行。"):
                data[operation] = state
                self.plugin.save_data(key=ALERT_DATA_KEY, value=data)
                return
        data.pop(operation, None)
        self.plugin.save_data(key=ALERT_DATA_KEY, value=data)

    def errors(self) -> dict:
        """返回仍在持续的操作异常供总览展示。"""
        return {
            operation: str(state.get("message") or "")
            for operation, state in self._load().items()
            if isinstance(state, dict) and state.get("active")
        }
