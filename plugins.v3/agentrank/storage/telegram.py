"""Own Telegram selection, retry and pending-session persistence."""

import threading
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from ..model.telegram_pending import TelegramPendingSession
from ..model.telegram_retry import TelegramRetrySession
from ..model.telegram_selection import TelegramSelectionSession
from .data import PluginDataStore
from .locks import RepositoryLocks


class TelegramSessionStore:
    """Keep session behavior behind the shared data facility and namespace locks."""

    telegram_sessions_key = "telegram_selection_sessions"
    telegram_pending_sessions_key = "telegram_pending_sessions"
    telegram_pending_session_prefix = "telegram_pending_session"
    telegram_retry_sessions_key = "telegram_retry_sessions"

    def __init__(self, data: PluginDataStore, locks: RepositoryLocks) -> None:
        """Bind shared data access and the existing namespace-lock pool."""
        self._data = data
        self._locks = locks

    @property
    def _telegram_pending_lock(self) -> threading.RLock:
        return self._locks.lock("telegram_pending")

    @property
    def _telegram_retry_lock(self) -> threading.RLock:
        return self._locks.lock("telegram_retry")

    def load_telegram_retry_session(self, token: str) -> TelegramRetrySession | None:
        """按随机令牌恢复运行重试会话，损坏数据按失效处理。"""
        with self._telegram_retry_lock:
            raw = self._data.get_data(key=self.telegram_retry_sessions_key)
            value = raw.get(str(token)) if isinstance(raw, Mapping) else None
            if value is None:
                return None
            try:
                session = TelegramRetrySession.from_dict(value)
                return session if session.token == str(token) else None
            except (TypeError, ValueError):
                return None

    def save_telegram_retry_session(
        self,
        session: TelegramRetrySession,
        *,
        expected_status: str = "",
        expected_attempt: int | None = None,
    ) -> bool:
        """原子更新重试状态，每个画像仅保留最新通知并有界裁剪。"""
        with self._telegram_retry_lock:
            if expected_status or expected_attempt is not None:
                current = self.load_telegram_retry_session(session.token)
                if (
                    current is None
                    or current.profile_id != session.profile_id
                    or (expected_status and current.status != expected_status)
                    or (
                        expected_attempt is not None
                        and current.attempt != expected_attempt
                    )
                ):
                    return False
            raw = self._data.get_data(key=self.telegram_retry_sessions_key)
            retained: dict[str, Any] = {}
            for token, value in raw.items() if isinstance(raw, Mapping) else []:
                try:
                    current = TelegramRetrySession.from_dict(value)
                except (TypeError, ValueError):
                    continue
                if (
                    current.profile_id != session.profile_id
                    and not current.is_expired()
                ):
                    retained[str(token)] = current.to_dict()
            retained[session.token] = session.to_dict()
            self._data.save_data(
                key=self.telegram_retry_sessions_key,
                value=dict(list(retained.items())[-200:]),
            )
            return True

    def save_telegram_session(self, session: TelegramSelectionSession) -> None:
        """保存一个 Telegram 选择会话并裁剪过期记录。"""
        raw = self._data.get_data(key=self.telegram_sessions_key)
        sessions = dict(raw) if isinstance(raw, Mapping) else {}
        retained: dict[str, Any] = {}
        for token, value in sessions.items():
            try:
                current = TelegramSelectionSession.from_dict(value)
            except (TypeError, ValueError, KeyError):
                continue
            if not current.is_expired() or current.status == "processing":
                retained[str(token)] = current.to_dict()
        retained[session.token] = session.to_dict()
        self._data.save_data(key=self.telegram_sessions_key, value=retained)

    def load_telegram_session(self, token: str) -> TelegramSelectionSession | None:
        """按不可猜令牌读取 Telegram 选择会话。"""
        raw = self._data.get_data(key=self.telegram_sessions_key)
        if not isinstance(raw, Mapping):
            return None
        value = raw.get(str(token or "").strip())
        if value is None:
            return None
        try:
            return TelegramSelectionSession.from_dict(value)
        except (TypeError, ValueError, KeyError) as error:
            self._data.record_recovery(
                f"{self.telegram_sessions_key}:{token}",
                "ignored_corrupt_data",
                str(error),
            )
            return None

    @classmethod
    def _telegram_pending_session_key(cls, token: str) -> str:
        """返回单条 Telegram 待办会话的独立插件数据键。"""
        target = str(token or "").strip()
        if not target:
            raise ValueError("telegram pending token is required")
        return f"{cls.telegram_pending_session_prefix}:{quote(target, safe='')}"

    def _pending_session_from_value(
        self, value: Any, recovery_key: str
    ) -> TelegramPendingSession | None:
        """恢复单条 Telegram 待办会话，损坏数据记入恢复日志。"""
        try:
            return TelegramPendingSession.from_dict(value)
        except (TypeError, ValueError, KeyError) as error:
            self._data.record_recovery(
                recovery_key,
                "ignored_corrupt_item",
                str(error),
            )
            return None

    @staticmethod
    def _pending_session_score(session: TelegramPendingSession) -> tuple[int, ...]:
        """为重复会话选择消息身份更完整且仍可重试的记录。"""
        return (
            int(bool(session.message_id)),
            int(bool(session.chat_id)),
            int(bool(session.source)),
            int(session.status == "open"),
        )

    def _load_telegram_pending_session_map(
        self, *, migrate_legacy: bool = True
    ) -> dict[str, TelegramPendingSession]:
        """合并独立会话和全部旧共享记录，并按需完成原地迁移。"""
        sessions: dict[str, TelegramPendingSession] = {}
        dedicated_tokens = set()
        legacy_found = False
        entries = self._data.data_entries()
        if not any(key == self.telegram_pending_sessions_key for key, _ in entries):
            legacy = self._data.get_data(key=self.telegram_pending_sessions_key)
            if isinstance(legacy, Mapping):
                entries.append((self.telegram_pending_sessions_key, legacy))

        def retain(candidate: TelegramPendingSession, *, dedicated: bool) -> None:
            """按完整度与独立存储优先级保留同令牌的最佳会话。"""
            current = sessions.get(candidate.token)
            current_dedicated = candidate.token in dedicated_tokens
            selected = current is None or (
                self._pending_session_score(candidate),
                int(dedicated),
            ) > (self._pending_session_score(current), int(current_dedicated))
            if selected:
                sessions[candidate.token] = candidate
                if dedicated:
                    dedicated_tokens.add(candidate.token)
                else:
                    dedicated_tokens.discard(candidate.token)

        dedicated_prefix = f"{self.telegram_pending_session_prefix}:"
        for key, value in entries:
            if key == self.telegram_pending_sessions_key:
                if not isinstance(value, Mapping):
                    continue
                legacy_found = True
                for token, raw_session in value.items():
                    session = self._pending_session_from_value(
                        raw_session,
                        f"{self.telegram_pending_sessions_key}:{token}",
                    )
                    if session is not None:
                        retain(session, dedicated=False)
            elif key.startswith(dedicated_prefix):
                session = self._pending_session_from_value(value, key)
                if session is not None:
                    retain(session, dedicated=True)

        if migrate_legacy and legacy_found:
            for session in sessions.values():
                self._data.save_data(
                    key=self._telegram_pending_session_key(session.token),
                    value=session.to_dict(),
                )
            self._data.del_data(key=self.telegram_pending_sessions_key)
        return sessions

    def save_telegram_pending_session(self, session: TelegramPendingSession) -> None:
        """以独立数据键保存 Telegram 待确认会话并裁剪过期记录。"""
        if not isinstance(session, TelegramPendingSession):
            raise TypeError("session must be TelegramPendingSession")
        with self._telegram_pending_lock:
            sessions = self._load_telegram_pending_session_map()
            for current in sessions.values():
                if current.token != session.token and current.is_expired():
                    self._data.del_data(
                        key=self._telegram_pending_session_key(current.token)
                    )
            self._data.save_data(
                key=self._telegram_pending_session_key(session.token),
                value=session.to_dict(),
            )

    def load_telegram_pending_session(
        self, token: str
    ) -> TelegramPendingSession | None:
        """按不可猜令牌读取 Telegram 待确认会话。"""
        target = str(token or "").strip()
        if not target:
            return None
        with self._telegram_pending_lock:
            return self._load_telegram_pending_session_map().get(target)

    def delete_telegram_pending_session(self, token: str) -> bool:
        """删除一个未建立可靠消息身份的 Telegram 待办会话。"""
        target = str(token or "").strip()
        if not target:
            return False
        with self._telegram_pending_lock:
            sessions = self._load_telegram_pending_session_map()
            if target not in sessions:
                return False
            self._data.del_data(key=self._telegram_pending_session_key(target))
            return True

    def load_telegram_pending_sessions(
        self,
        profile_id: str,
        item_type: str,
        item_id: str,
        *,
        status: str = "open",
    ) -> list[TelegramPendingSession]:
        """按待办业务身份读取关联的 Telegram 交互会话。"""
        target = str(profile_id or "").strip()
        if not target:
            raise ValueError("profile_id is required")
        target_type = str(item_type or "").strip()
        target_id = str(item_id or "").strip()
        return [
            session
            for session in self.load_all_telegram_pending_sessions(status=status)
            if session.profile_id == target
            and session.item_type == target_type
            and session.item_id == target_id
        ]

    def load_all_telegram_pending_sessions(
        self, *, status: str = ""
    ) -> list[TelegramPendingSession]:
        """读取全部 Telegram 待办会话，供启动时跨端状态对账。"""
        target_status = str(status or "").strip()
        with self._telegram_pending_lock:
            values = self._load_telegram_pending_session_map().values()
            sessions = [
                session
                for session in values
                if not target_status or session.status == target_status
            ]
        return sorted(sessions, key=lambda item: (item.created_at, item.token))
