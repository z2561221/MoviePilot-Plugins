"""Telegram 异常通知的受控重试入口。"""

import logging
import re
import secrets
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from app.schemas.types import MessageType, NotificationChannel

from ..adapter.telegram import TelegramTargetAdapter
from ..model.telegram_retry import TelegramRetrySession
from .notification_type import resolve_notification_type
from .prompt import configured_agent_display_name
from .telegram_interaction import TelegramSelectionService

logger = logging.getLogger(__name__)


class TelegramRunRetryService:
    """管理一次性运行重试按钮，复用宿主消息渠道与后台运行入口。"""

    session_ttl_hours = 24

    def __init__(
        self,
        plugin: Any,
        repository: Any,
        config: dict[str, Any],
        retry_handler: Callable[[str], dict[str, Any]],
        target_adapter: Any = None,
        token_factory: Callable[[], str] | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ):
        """绑定通知归属、会话存储及可替换的后台任务入口。"""
        self._plugin = plugin
        self._repository = repository
        self._config = config
        self._retry_handler = retry_handler
        self._target_adapter = target_adapter or TelegramTargetAdapter()
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(7))
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()

    def _buttons(self, session: TelegramRetrySession) -> list[list[dict]]:
        """生成不携带画像信息且符合 Telegram 长度限制的按钮。"""
        callback = f"[PLUGIN]{self._plugin.__class__.__name__}|arr:{session.token}:r"
        if len(callback.encode("utf-8")) > 64:
            raise ValueError("telegram retry callback exceeds 64 bytes")
        return [[{"text": "🔄 重试", "callback_data": callback}]]

    def create_buttons(
        self,
        profile_id: str,
        username: str,
        run_id: str,
        message: str,
    ) -> list[list[dict]] | None:
        """为可接收 Telegram 的目标用户保存重试会话。"""
        mtype = resolve_notification_type(self._config, MessageType)
        if not TelegramSelectionService._notification_sources(mtype):
            return None
        userid = self._target_adapter.resolve_userid(username)
        if not profile_id or not userid:
            return None
        now = self._now_factory()
        session = TelegramRetrySession(
            token=self._token_factory(),
            profile_id=profile_id,
            username=username,
            telegram_userid=str(userid),
            run_id=str(run_id or ""),
            message=message,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=self.session_ttl_hours)).isoformat(),
        )
        buttons = self._buttons(session)
        with self._lock:
            self._repository.save_telegram_retry_session(session)
        return buttons

    def _reply(
        self,
        event_data: dict[str, Any],
        text: str,
        session: TelegramRetrySession = None,
        *,
        retryable: bool = False,
    ) -> None:
        """更新本人的原通知；未通过归属检查时只单独提示点击者。"""
        kwargs = {
            "channel": NotificationChannel.Telegram,
            "source": event_data.get("source"),
            "mtype": resolve_notification_type(self._config, MessageType),
            "title": configured_agent_display_name(
                self._config.get("agent_display_name")
            ),
            "text": text,
            "targets": {"telegram_userid": str(event_data.get("userid") or "")},
            "parse_mode": "plain",
            "save_history": False,
            "disable_web_page_preview": True,
        }
        if session is not None:
            kwargs.update(
                text=f"{session.message}\n重试：{text}",
                original_message_id=event_data.get("original_message_id"),
                original_chat_id=event_data.get("original_chat_id"),
                buttons=self._buttons(session) if retryable else [],
            )
        self._plugin.post_message(**kwargs)

    def _superseded(self, session: TelegramRetrySession) -> bool:
        """有较新运行结果时拒绝旧通知，避免重跑已经恢复的任务。"""
        history = self._repository.load_run_history(session.profile_id)
        if not history:
            return False
        latest = history[0]
        if session.run_id:
            return latest.run_id != session.run_id or latest.status in {
                "success",
                "recommendation_incomplete",
            }
        try:
            finished = datetime.fromisoformat(latest.finished_at)
            created = datetime.fromisoformat(session.created_at)
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return finished > created
        except (TypeError, ValueError):
            return False

    def handle_callback(self, event_data: dict[str, Any]) -> bool:
        """校验原接收人并原子领取一次重试，重复回调不再运行。"""
        event_data = event_data or {}
        match = re.fullmatch(
            r"arr:([A-Za-z0-9_-]{6,32}):r", str(event_data.get("text") or "")
        )
        channel = event_data.get("channel")
        if (
            not match
            or event_data.get("plugin_id") != self._plugin.__class__.__name__
            or getattr(channel, "value", channel) != NotificationChannel.Telegram.value
        ):
            return False
        with self._lock:
            session = self._repository.load_telegram_retry_session(match.group(1))
            if session is None:
                self._reply(
                    event_data, "本次重试已过期或已有新的运行通知，请使用最新通知。"
                )
                return True
            if str(event_data.get("userid") or "") != session.telegram_userid:
                self._reply(event_data, "这不是发送给你的运行通知，无法重试。")
                return True
            if session.status == "submitted":
                self._reply(event_data, "已受理，不会重复执行。", session)
                return True
            previous_status = session.status
            if session.is_expired(self._now_factory()):
                session.status = "expired"
            elif session.status == "open" and self._superseded(session):
                session.status = "stale"
            if session.status != "open":
                self._repository.save_telegram_retry_session(
                    session, expected_status=previous_status
                )
                self._reply(
                    event_data,
                    "本次通知已失效，请使用最新通知或在插件页面刷新。",
                    session,
                )
                return True
            session.status = "submitted"
            if not self._repository.save_telegram_retry_session(
                session, expected_status="open"
            ):
                self._reply(event_data, "已受理或已失效，不会重复执行。", session)
                return True
            try:
                result = self._retry_handler(session.profile_id)
            except Exception:
                logger.warning(
                    "AgentRank Telegram 重试受理失败 profile_id=%s",
                    session.profile_id,
                    exc_info=True,
                )
                result = {"accepted": False}
            if not result.get("accepted"):
                session.status = "open"
                self._repository.save_telegram_retry_session(
                    session, expected_status="submitted"
                )
                text = (
                    "该画像正在运行，请结束后再重试。"
                    if result.get("status") == "running"
                    else "暂未受理，请确认插件已启用后重试。"
                )
                self._reply(event_data, text, session, retryable=True)
                return True
            self._reply(event_data, "已提交，正在重新生成榜单。", session)
            return True
