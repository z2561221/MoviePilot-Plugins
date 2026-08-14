"""基于 MoviePilot 插件数据接口的稳定画像身份存储仓库。"""

import copy
import threading
import uuid
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Tuple, Type, TypeVar
from urllib.parse import quote

from ..model.archive import ArchiveFeedback
from ..model.analysis import RecommendationAnalysis
from ..model.board import RecommendationBoard
from ..model.candidate import Candidate, backfill_media_identity_payload
from ..model.candidate_snapshot import CandidateSnapshot
from ..model.conversation import (
    ConversationCommand,
    ConversationMessage,
    ConversationThread,
)
from ..model.feedback import (
    BoardConsumption,
    FeedbackAppendResult,
    FeedbackEvent,
    FeedbackEventPointer,
    FeedbackEventSegment,
    FeedbackLedgerIndex,
    ShortTermSignal,
)
from ..model.feedback_queue import FeedbackQueueJob
from ..model.feedback_decision import MemoryProposal, PendingQuestion
from ..model.feedback_understanding import FeedbackUnderstandingRecord
from ..model.memory import (
    MemoryProjectionResult,
    PreferenceMemory,
    PreferenceMemoryItem,
)
from ..model.outcome import OutcomeAttribution
from ..model.profile import UserProfile
from ..model.profile_preferences import ProfilePreferences
from ..model.playback import PlaybackSnapshot
from ..model.policy import PolicySnapshot
from ..model.run import AdaptiveFingerprints, LearningHealth, RecommendationRun
from ..model.telegram_selection import TelegramSelectionSession
from ..model.telegram_pending import TelegramPendingSession


ModelType = TypeVar("ModelType")


class AgentRankRepository:
    """统一封装 AgentRank 的 profile_id 隔离键与容错读取。"""

    _board_archive_lock = threading.RLock()
    _telegram_pending_lock = threading.RLock()
    _feedback_locks_guard = threading.Lock()
    _feedback_locks: Dict[str, threading.RLock] = {}
    recovery_log_key = "agentrank_recovery_log"
    telegram_sessions_key = "telegram_selection_sessions"
    telegram_pending_sessions_key = "telegram_pending_sessions"
    telegram_pending_session_prefix = "telegram_pending_session"
    board_history_prefix = "board_history"
    playback_snapshot_prefix = "playback_snapshot"
    candidate_snapshot_index_prefix = "candidate_snapshot_index"
    confirmation_prefix = "full_reset_confirmation"
    learning_profile_prefixes = (
        "board_consumption",
        "short_term_signals",
        "adaptive_fingerprints",
        "learning_health",
        "feedback_queue",
        "memory_proposals",
        "pending_questions",
        "conversation",
        "conversation_messages",
        "conversation_reads",
        "policy_snapshot",
        "attribution",
        "agent_analysis",
    )

    def __init__(
        self,
        plugin: Any,
        history_limit: int = 50,
        feedback_segment_size: int = 100,
        candidate_snapshot_limit: int = 20,
        feedback_event_limit: int = 1000,
    ):
        """绑定插件数据接口并设置历史、快照和反馈保留上限。"""
        self._plugin = plugin
        self._history_limit = max(1, min(int(history_limit), 200))
        self._feedback_segment_size = max(
            1, min(int(feedback_segment_size), 1000)
        )
        self._candidate_snapshot_limit = max(
            1, min(int(candidate_snapshot_limit), 500)
        )
        self._feedback_event_limit = max(
            1, min(int(feedback_event_limit), 100000)
        )

    @staticmethod
    def _scope(value: str, field_name: str) -> str:
        """校验并转义画像 ID 或运行标识，避免键空间碰撞。"""
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{field_name} is required")
        return quote(text, safe="@._-")

    def _profile_key(self, prefix: str, profile_id: str) -> str:
        """生成带新命名空间的 profile_id 持久化键。"""
        return f"{prefix}:profile:{self._scope(profile_id, 'profile_id')}"

    def _candidate_key(self, run_id: str, profile_id: str) -> str:
        """生成按运行和 profile_id 双重隔离的候选快照键。"""
        return (
            f"candidate_snapshot:profile:{self._scope(profile_id, 'profile_id')}:"
            f"run:{self._scope(run_id, 'run_id')}"
        )

    def _candidate_index_key(self, profile_id: str) -> str:
        """生成按 profile 隔离的候选快照索引键。"""
        return self._profile_key(self.candidate_snapshot_index_prefix, profile_id)

    def _board_history_key(self, profile_id: str) -> str:
        """生成按 profile 隔离的历史榜单快照键。"""
        return self._profile_key(self.board_history_prefix, profile_id)

    def _confirmation_key(self, profile_id: str) -> str:
        """生成彻底重置一次性确认记录键。"""
        return self._profile_key(self.confirmation_prefix, profile_id)

    def _feedback_index_key(self, profile_id: str) -> str:
        """生成按 profile_id 隔离的反馈账本索引键。"""
        return self._profile_key("feedback_event_index", profile_id)

    def _feedback_segment_key(self, profile_id: str, segment_id: int) -> str:
        """生成按 profile_id 和段号隔离的反馈事件段键。"""
        if int(segment_id) <= 0:
            raise ValueError("segment_id must be positive")
        return (
            f"feedback_event_segment:profile:{self._scope(profile_id, 'profile_id')}:"
            f"segment:{int(segment_id):08d}"
        )

    def _learning_key(self, prefix: str, profile_id: str) -> str:
        """生成未来学习辅助存储的 profile 键。"""
        if prefix not in self.learning_profile_prefixes:
            raise ValueError("unknown learning storage prefix")
        return self._profile_key(prefix, profile_id)

    @classmethod
    def _feedback_lock(cls, profile_id: str) -> threading.RLock:
        """取得跨仓库实例共享的 profile 级反馈写锁。"""
        scope = cls._scope(profile_id, "profile_id")
        with cls._feedback_locks_guard:
            lock = cls._feedback_locks.get(scope)
            if lock is None:
                lock = threading.RLock()
                cls._feedback_locks[scope] = lock
            return lock

    @contextmanager
    def profile_data_guard(self, profile_id: str) -> Iterator[None]:
        """串行化 profile 级候选、反馈、记忆和重置写入。"""
        with self._feedback_lock(profile_id):
            yield

    def _mark_retention_failure(self, profile_id: str, data_kind: str) -> None:
        """把保留裁剪失败标记到运行态，不影响已写入的用户事实。"""
        status = getattr(self._plugin, "_data_lifecycle_status", None)
        if not isinstance(status, dict):
            return
        profiles = status.setdefault("profiles", [])
        item = next(
            (
                entry
                for entry in profiles
                if isinstance(entry, dict)
                and str(entry.get("profile_id") or "") == str(profile_id)
            ),
            None,
        )
        if item is None:
            item = {
                "profile_id": str(profile_id),
                "status": "failed",
                "pruned": {},
                "message": "数据保留维护失败，已保留现有数据",
            }
            profiles.append(item)
        item["status"] = "failed"
        item["message"] = "数据保留维护失败，已保留现有数据"
        failures = item.setdefault("retention_failures", [])
        if data_kind not in failures:
            failures.append(str(data_kind))
        status["status"] = "partial_failed"

    @contextmanager
    def board_archive_guard(self, profile_id: str) -> Iterator[None]:
        """串行化榜单提交与归档反馈，避免读改写竞态。"""
        self._scope(profile_id, "profile_id")
        with self._board_archive_lock:
            yield

    @contextmanager
    def feedback_action_guard(self, profile_id: str) -> Iterator[None]:
        """按固定锁顺序串行化榜单、归档与反馈事件复合动作。"""
        with self._board_archive_lock, self._feedback_lock(profile_id):
            yield

    def _record_recovery(self, key: str, action: str, detail: str = "") -> None:
        """记录迁移或损坏数据恢复证据，且不因日志损坏而失败。"""
        try:
            history = self._plugin.get_data(key=self.recovery_log_key)
            history = list(history) if isinstance(history, list) else []
        except Exception:
            history = []
        history.append(
            {
                "key": key,
                "action": action,
                "detail": detail,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._plugin.save_data(key=self.recovery_log_key, value=history[-100:])

    def _atomic_raw_update(
        self,
        *,
        updates: Mapping[str, Any] = None,
        delete_keys: Iterable[str] = (),
        recovery_key: str,
        action: str,
    ) -> None:
        """原子应用一组插件数据变更，失败时逐键恢复旧状态。"""
        safe_updates = dict(updates or {})
        safe_deletes = [
            str(key) for key in dict.fromkeys(delete_keys or ()) if key not in safe_updates
        ]
        touched = list(safe_updates) + safe_deletes
        old_values = {key: self._plugin.get_data(key=key) for key in touched}
        try:
            for key, value in safe_updates.items():
                self._plugin.save_data(key=key, value=value)
            for key in safe_deletes:
                self._plugin.del_data(key=key)
            for key, value in safe_updates.items():
                if self._plugin.get_data(key=key) != value:
                    raise ValueError(f"profile data readback mismatch: {key}")
            for key in safe_deletes:
                if self._plugin.get_data(key=key) is not None:
                    raise ValueError(f"profile data delete readback mismatch: {key}")
        except Exception as error:
            rollback_errors: List[str] = []
            for key in reversed(touched):
                try:
                    self._restore_raw(key, old_values[key])
                except Exception as rollback_error:
                    rollback_errors.append(f"{key}: {rollback_error}")
            detail = type(error).__name__
            if rollback_errors:
                detail = f"{detail}; rollback_failed={len(rollback_errors)}"
            try:
                self._record_recovery(recovery_key, action, detail)
            except Exception:
                pass
            if rollback_errors:
                raise RuntimeError(
                    "profile data update and rollback both failed"
                ) from error
            raise

    def _load_model(
        self,
        key: str,
        model_type: Type[ModelType],
    ) -> Optional[ModelType]:
        """容错读取新命名空间模型，不触碰旧 username 键。"""
        value = self._plugin.get_data(key=key)
        if value is None:
            return None
        try:
            model = model_type.from_dict(value)
        except (TypeError, ValueError, KeyError) as error:
            self._record_recovery(key, "ignored_corrupt_data", str(error))
            return None
        return model

    def _load_scoped_model(
        self,
        key: str,
        model_type: Type[ModelType],
        profile_id: str,
    ) -> Optional[ModelType]:
        """读取并校验载荷 profile_id 与请求作用域完全一致。"""
        model = self._load_model(key, model_type)
        if model is None:
            return None
        stored_profile_id = str(getattr(model, "profile_id", "") or "")
        if stored_profile_id != str(profile_id):
            self._record_recovery(
                key,
                "ignored_cross_profile_data",
                stored_profile_id,
            )
            return None
        return model

    def save_profile(self, profile: UserProfile) -> None:
        """保存当前用户画像快照。"""
        self._plugin.save_data(
            key=self._profile_key("profile_snapshot", profile.profile_id),
            value=profile.to_dict(),
        )

    def load_profile(self, profile_id: str) -> Optional[UserProfile]:
        """读取当前用户画像；损坏或不存在时返回空。"""
        return self._load_scoped_model(
            self._profile_key("profile_snapshot", profile_id), UserProfile, profile_id
        )

    def save_profile_preferences(self, preferences: ProfilePreferences) -> None:
        """保存当前用户人工画像标签偏好。"""
        self._plugin.save_data(
            key=self._profile_key("profile_preferences", preferences.profile_id),
            value=preferences.to_dict(),
        )

    def load_profile_preferences(self, profile_id: str) -> ProfilePreferences:
        """读取人工画像标签偏好；不存在或损坏时返回空偏好。"""
        preferences = self._load_scoped_model(
            self._profile_key("profile_preferences", profile_id),
            ProfilePreferences,
            profile_id,
        )
        return preferences or ProfilePreferences(profile_id=profile_id)

    def load_conversation_thread(
        self, profile_id: str
    ) -> Optional[ConversationThread]:
        """读取按 profile 隔离的 CinePilot Agent 对话线程。"""
        return self._load_scoped_model(
            self._learning_key("conversation", profile_id),
            ConversationThread,
            profile_id,
        )

    def load_conversation_records(
        self, profile_id: str, *, strict: bool = False
    ) -> Tuple[List[ConversationMessage], List[ConversationCommand]]:
        """读取对话消息与命令；严格模式拒绝损坏或未知记录。"""
        target = str(profile_id or "").strip()
        self._scope(target, "profile_id")
        key = self._learning_key("conversation_messages", target)
        raw = self._plugin.get_data(key=key)
        if raw is None:
            return [], []
        if not isinstance(raw, list):
            self._record_recovery(
                key, "ignored_corrupt_data", "conversation records must be a list"
            )
            if strict:
                raise ValueError("conversation records are corrupt")
            return [], []
        messages: List[ConversationMessage] = []
        commands: List[ConversationCommand] = []
        for item in raw:
            if not isinstance(item, Mapping):
                self._record_recovery(
                    key, "ignored_corrupt_item", "conversation record must be a mapping"
                )
                if strict:
                    raise ValueError("conversation record is corrupt")
                continue
            try:
                record_type = str(item.get("record_type") or "")
                if record_type == "conversation_message":
                    record = ConversationMessage.from_dict(item)
                    messages.append(record)
                elif record_type == "conversation_command":
                    record = ConversationCommand.from_dict(item)
                    commands.append(record)
                else:
                    raise ValueError("conversation record type is unknown")
                if record.profile_id != target:
                    raise ValueError("conversation record profile mismatch")
            except (TypeError, ValueError, KeyError) as error:
                self._record_recovery(key, "ignored_corrupt_item", str(error))
                if strict:
                    raise ValueError("conversation record is corrupt") from error
        return messages, commands

    def load_conversation_read_marker(
        self, profile_id: str, actor_id: str
    ) -> Optional[str]:
        """读取一个 MP 用户在指定画像下最后已读的 Agent 回复 ID。"""
        target = str(profile_id or "").strip()
        actor = self._scope(actor_id, "actor_id")
        key = self._learning_key("conversation_reads", target)
        raw = self._plugin.get_data(key=key)
        if raw is None:
            return None
        if not isinstance(raw, Mapping):
            self._record_recovery(
                key, "ignored_corrupt_data", "conversation reads must be a mapping"
            )
            return None
        value = raw.get(actor)
        if not isinstance(value, Mapping):
            return None
        message_id = value.get("message_id")
        return str(message_id or "")[:128]

    def save_conversation_read_marker(
        self, profile_id: str, actor_id: str, message_id: str
    ) -> None:
        """保存一个 MP 用户在指定画像下最后已读的 Agent 回复 ID。"""
        target = str(profile_id or "").strip()
        actor = self._scope(actor_id, "actor_id")
        marker = str(message_id or "").strip()[:128]
        key = self._learning_key("conversation_reads", target)
        with self._feedback_lock(target):
            raw = self._plugin.get_data(key=key)
            values = dict(raw) if isinstance(raw, Mapping) else {}
            values[actor] = {
                "message_id": marker,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._atomic_raw_update(
                updates={key: values},
                recovery_key=key,
                action="conversation_read_marker_write_failed",
            )

    def save_conversation_state(
        self,
        thread: ConversationThread,
        messages: Iterable[ConversationMessage],
        commands: Iterable[ConversationCommand],
        *,
        limit: int = 200,
        action: str = "conversation_write_failed",
    ) -> None:
        """原子替换线程与有界记录，并保留失败草稿和待确认命令。"""
        if not isinstance(thread, ConversationThread):
            raise TypeError("thread must be ConversationThread")
        message_values = list(messages or ())
        command_values = list(commands or ())
        if any(
            not isinstance(item, ConversationMessage)
            or item.profile_id != thread.profile_id
            or item.thread_id != thread.thread_id
            for item in message_values
        ):
            raise ValueError("conversation messages do not match thread")
        if any(
            not isinstance(item, ConversationCommand)
            or item.profile_id != thread.profile_id
            or item.thread_id != thread.thread_id
            for item in command_values
        ):
            raise ValueError("conversation commands do not match thread")
        keep_limit = max(1, min(int(limit), 100000))
        protected_message_ids = {
            item.message_id
            for item in message_values
            if item.status in {"draft", "processing", "failed"}
            or item.message_id == thread.last_message_id
        }
        protected_command_ids = {
            item.command_id
            for item in command_values
            if item.status == "pending_confirmation"
            or item.command_id in thread.pending_command_ids
        }
        optional_records = [
            *[
                item
                for item in message_values
                if item.message_id not in protected_message_ids
            ],
            *[
                item
                for item in command_values
                if item.command_id not in protected_command_ids
            ],
        ]
        optional_slots = max(
            0,
            keep_limit - len(protected_message_ids) - len(protected_command_ids),
        )
        selected_optional = optional_records[-optional_slots:] if optional_slots else []
        selected_ids = {
            getattr(item, "message_id", "") or getattr(item, "command_id", "")
            for item in selected_optional
        }
        retained_messages = [
            item
            for item in message_values
            if item.message_id in protected_message_ids
            or item.message_id in selected_ids
        ]
        retained_commands = [
            item
            for item in command_values
            if item.command_id in protected_command_ids
            or item.command_id in selected_ids
        ]
        records = sorted(
            [*retained_messages, *retained_commands],
            key=lambda item: (
                item.created_at,
                getattr(item, "message_id", "") or getattr(item, "command_id", ""),
            ),
        )
        thread_key = self._learning_key("conversation", thread.profile_id)
        records_key = self._learning_key("conversation_messages", thread.profile_id)
        self._atomic_raw_update(
            updates={
                thread_key: thread.to_dict(),
                records_key: [item.to_dict() for item in records],
            },
            recovery_key=records_key,
            action=action,
        )

    def prune_conversation_records(self, profile_id: str, limit: int) -> int:
        """裁剪已完成对话记录并永久保留待确认命令与失败草稿。"""
        target = str(profile_id or "").strip()
        keep_limit = max(1, min(int(limit), 100000))
        with self._feedback_lock(target):
            thread = self.load_conversation_thread(target)
            messages, commands = self.load_conversation_records(target, strict=True)
            before = len(messages) + len(commands)
            if thread is None or before <= keep_limit:
                return 0
            self.save_conversation_state(
                thread,
                messages,
                commands,
                limit=keep_limit,
                action="conversation_prune_failed",
            )
            retained_messages, retained_commands = self.load_conversation_records(
                target, strict=True
            )
            return max(0, before - len(retained_messages) - len(retained_commands))

    def load_outcome_attributions(
        self, profile_id: str, *, strict: bool = False
    ) -> List[OutcomeAttribution]:
        """读取 profile 隔离的结果归因；严格模式拒绝覆盖损坏数据。"""
        target = str(profile_id or "").strip()
        key = self._learning_key("attribution", target)
        raw = self._plugin.get_data(key=key)
        if raw is None:
            return []
        if not isinstance(raw, list):
            self._record_recovery(
                key, "ignored_corrupt_data", "outcome attribution must be a list"
            )
            if strict:
                raise ValueError("outcome attribution data is corrupt")
            return []
        records: List[OutcomeAttribution] = []
        for value in raw:
            try:
                record = OutcomeAttribution.from_dict(value)
                if record.profile_id != target:
                    raise ValueError("outcome attribution profile_id mismatch")
            except (TypeError, ValueError, KeyError) as error:
                self._record_recovery(key, "ignored_corrupt_item", str(error))
                if strict:
                    raise ValueError("outcome attribution item is corrupt") from error
                continue
            records.append(record)
        return records

    def save_outcome_attributions(
        self,
        profile_id: str,
        records: Iterable[OutcomeAttribution],
        *,
        limit: int = 500,
    ) -> None:
        """原子保存有界归因列表并拒绝重复 ID 或跨 profile 数据。"""
        target = str(profile_id or "").strip()
        values = list(records or ())
        if any(
            not isinstance(item, OutcomeAttribution) or item.profile_id != target
            for item in values
        ):
            raise ValueError("outcome attribution profile scope mismatch")
        attribution_ids = [item.attribution_id for item in values]
        if len(set(attribution_ids)) != len(attribution_ids):
            raise ValueError("outcome attribution ids must be unique")
        keep_limit = max(1, min(int(limit), 100000))
        retained = values[-keep_limit:]
        key = self._learning_key("attribution", target)
        self._atomic_raw_update(
            updates={key: [item.to_dict() for item in retained]},
            recovery_key=key,
            action="outcome_attribution_save_failed",
        )

    def save_playback_snapshot(self, snapshot: PlaybackSnapshot) -> None:
        """保存按用户隔离的播放画像快照。"""
        self._plugin.save_data(
            key=self._profile_key(self.playback_snapshot_prefix, snapshot.profile_id),
            value=snapshot.to_dict(),
        )

    def load_playback_snapshot(self, profile_id: str) -> Optional[PlaybackSnapshot]:
        """读取播放画像快照；损坏或不存在时返回空。"""
        return self._load_scoped_model(
            self._profile_key(self.playback_snapshot_prefix, profile_id),
            PlaybackSnapshot,
            profile_id,
        )

    def _load_board_consumptions(self, profile_id: str) -> List[BoardConsumption]:
        """读取当前 profile 的榜单消费记录并忽略损坏或串 profile 数据。"""
        key = self._learning_key("board_consumption", profile_id)
        raw = self._plugin.get_data(key=key)
        values = list(raw.values()) if isinstance(raw, Mapping) else raw
        if not isinstance(values, list):
            if raw is not None:
                self._record_recovery(
                    key, "ignored_corrupt_data", "consumption must be a list"
                )
            return []
        result: List[BoardConsumption] = []
        for value in values:
            try:
                current = BoardConsumption.from_dict(value)
                if current.profile_id != str(profile_id):
                    raise ValueError("board consumption profile mismatch")
            except (TypeError, ValueError, KeyError) as error:
                self._record_recovery(key, "ignored_corrupt_item", str(error))
                continue
            result.append(current)
        return result

    def load_board_consumptions(
        self, profile_id: str, *, limit: Optional[int] = None
    ) -> List[BoardConsumption]:
        """读取当前 profile 最近的榜单消费记录。"""
        with self._feedback_lock(profile_id):
            items = self._load_board_consumptions(profile_id)
        items.sort(
            key=lambda item: (
                item.last_interaction_at or item.exposed_at,
                item.run_id,
                item.board_revision,
            ),
            reverse=True,
        )
        return items[: max(0, int(limit))] if limit is not None else items

    def load_board_consumption(
        self, profile_id: str, run_id: str, board_revision: int
    ) -> Optional[BoardConsumption]:
        """按 run_id 与 board revision 读取一条榜单消费记录。"""
        target_run = str(run_id or "").strip()
        target_revision = max(1, int(board_revision or 1))
        for item in self.load_board_consumptions(profile_id):
            if item.run_id == target_run and item.board_revision == target_revision:
                return item
        return None

    def save_board_consumption(self, consumption: BoardConsumption) -> BoardConsumption:
        """幂等保存榜单消费记录并保留有界历史。"""
        if not isinstance(consumption, BoardConsumption):
            raise TypeError("consumption must be BoardConsumption")
        profile_id = consumption.profile_id
        key = self._learning_key("board_consumption", profile_id)
        with self._feedback_lock(profile_id):
            items = self._load_board_consumptions(profile_id)
            replaced = False
            retained: List[BoardConsumption] = []
            for item in items:
                if (
                    item.run_id == consumption.run_id
                    and item.board_revision == consumption.board_revision
                ):
                    if not replaced:
                        retained.append(consumption)
                        replaced = True
                else:
                    retained.append(item)
            if not replaced:
                retained.append(consumption)
            retained.sort(
                key=lambda item: (
                    item.last_interaction_at or item.exposed_at,
                    item.run_id,
                    item.board_revision,
                ),
                reverse=True,
            )
            self._plugin.save_data(
                key=key,
                value=[item.to_dict() for item in retained[: self._history_limit]],
            )
        return consumption

    def record_board_exposure(
        self,
        profile_id: str,
        run_id: str,
        board_revision: int,
        candidate_ids: Iterable[Any],
        observed_at: str,
    ) -> BoardConsumption:
        """记录一次真实页面曝光；同一榜单 revision 重复上报保持幂等。"""
        target = str(profile_id or "").strip()
        current = self.load_board_consumption(target, run_id, board_revision)
        if current is None:
            current = BoardConsumption(
                profile_id=target,
                run_id=str(run_id or "").strip(),
                board_revision=board_revision,
            )
        return self.save_board_consumption(
            current.with_exposure(candidate_ids, observed_at)
        )

    def record_board_detail_opened(
        self,
        profile_id: str,
        run_id: str,
        board_revision: int,
        candidate_id: str,
        observed_at: str,
    ) -> BoardConsumption:
        """幂等记录当前榜单某个候选的详情打开。"""
        target = str(profile_id or "").strip()
        current = self.load_board_consumption(target, run_id, board_revision)
        if current is None:
            current = BoardConsumption(
                profile_id=target,
                run_id=str(run_id or "").strip(),
                board_revision=board_revision,
            )
        return self.save_board_consumption(
            current.with_detail_opened(candidate_id, observed_at)
        )

    def record_board_interaction(
        self,
        profile_id: str,
        run_id: str,
        board_revision: int,
        kind: str,
        observed_at: str,
    ) -> BoardConsumption:
        """记录榜单上的结果交互状态，不改变反馈事件语义。"""
        target = str(profile_id or "").strip()
        current = self.load_board_consumption(target, run_id, board_revision)
        if current is None:
            current = BoardConsumption(
                profile_id=target,
                run_id=str(run_id or "").strip(),
                board_revision=board_revision,
            )
        return self.save_board_consumption(
            current.with_interaction(kind, observed_at)
        )

    def _load_short_term_signals(self, profile_id: str) -> List[ShortTermSignal]:
        """读取当前 profile 的短期信号并过滤损坏数据。"""
        key = self._learning_key("short_term_signals", profile_id)
        raw = self._plugin.get_data(key=key)
        if not isinstance(raw, list):
            if raw is not None:
                self._record_recovery(
                    key, "ignored_corrupt_data", "signals must be a list"
                )
            return []
        result: List[ShortTermSignal] = []
        for value in raw:
            try:
                signal = ShortTermSignal.from_dict(value)
                if signal.profile_id != str(profile_id):
                    raise ValueError("short-term signal profile mismatch")
            except (TypeError, ValueError, KeyError) as error:
                self._record_recovery(key, "ignored_corrupt_item", str(error))
                continue
            result.append(signal)
        return result

    def load_short_term_signals(
        self, profile_id: str, *, limit: Optional[int] = None
    ) -> List[ShortTermSignal]:
        """读取当前 profile 的短期偏好信号。"""
        with self._feedback_lock(profile_id):
            items = self._load_short_term_signals(profile_id)
        if limit is None:
            return items
        return items[-max(0, int(limit)) :]

    def append_short_term_signal(
        self, signal: ShortTermSignal
    ) -> Tuple[ShortTermSignal, bool]:
        """按幂等键追加短期信号，重复上报不重复计数。"""
        if not isinstance(signal, ShortTermSignal):
            raise TypeError("signal must be ShortTermSignal")
        profile_id = signal.profile_id
        key = self._learning_key("short_term_signals", profile_id)
        with self._feedback_lock(profile_id):
            items = self._load_short_term_signals(profile_id)
            for item in items:
                if item.idempotency_key == signal.idempotency_key:
                    if item.to_dict() != signal.to_dict():
                        raise ValueError("short-term signal idempotency conflict")
                    return item, False
            items.append(signal)
            self._plugin.save_data(
                key=key,
                value=[
                    item.to_dict()
                    for item in items[-max(1, self._history_limit * 10) :]
                ],
            )
        return signal, True

    def load_adaptive_fingerprints(
        self, profile_id: str
    ) -> Optional[AdaptiveFingerprints]:
        """读取当前 profile 最近一次生成门控指纹。"""
        return self._load_scoped_model(
            self._learning_key("adaptive_fingerprints", profile_id),
            AdaptiveFingerprints,
            profile_id,
        )

    def save_adaptive_fingerprints(
        self, fingerprints: AdaptiveFingerprints
    ) -> AdaptiveFingerprints:
        """保存来源、偏好和榜单消费三类门控指纹。"""
        if not isinstance(fingerprints, AdaptiveFingerprints):
            raise TypeError("fingerprints must be AdaptiveFingerprints")
        self._plugin.save_data(
            key=self._learning_key("adaptive_fingerprints", fingerprints.profile_id),
            value=fingerprints.to_dict(),
        )
        return fingerprints

    def load_learning_health(self, profile_id: str) -> Optional[LearningHealth]:
        """读取最近一次持久化的学习健康度摘要。"""
        return self._load_scoped_model(
            self._learning_key("learning_health", profile_id),
            LearningHealth,
            profile_id,
        )

    def build_learning_health(self, profile_id: str) -> LearningHealth:
        """根据当前事实动态汇总学习健康度，不把数据少误判为故障。"""
        target = str(profile_id or "").strip()
        signals = self.load_short_term_signals(target)
        consumptions = self.load_board_consumptions(target)
        memory = self.load_preference_memory(target)
        proposals = self.load_memory_proposals(target)
        questions = self.load_pending_questions(target)
        understandings = self.load_feedback_understandings(target)
        attributions = self.load_outcome_attributions(target)
        stage_counts: Dict[str, int] = {}
        for record in attributions:
            stage = str(record.state or "").strip()
            if stage:
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
        effective = [item for item in signals if item.kind != "rotation"]
        last_effective = max(
            (item.observed_at for item in effective if item.observed_at),
            default="",
        )
        pending_count = sum(
            str(item.status or "") in {"pending", "open", "awaiting_confirmation"}
            for item in [*proposals, *questions]
        )
        attention_required = bool(effective and not understandings)
        attention_reason = (
            "近期有效反馈尚未形成可回读的理解记录" if attention_required else ""
        )
        if not stage_counts:
            coverage = "none"
        elif any(
            stage_counts.get(stage, 0) == 0
            for stage in ("subscription_observed", "playback_observed")
        ):
            coverage = "partial"
        else:
            coverage = "complete"
        health = LearningHealth(
            profile_id=target,
            short_term_signal_count=len(signals),
            confirmed_memory_count=len(memory.active_items()),
            pending_count=pending_count,
            processed_count=len(understandings),
            exposure_count=sum(item.exposure_count for item in consumptions),
            effective_feedback_count=len(effective),
            last_effective_feedback_at=last_effective,
            attribution_stage_counts=stage_counts,
            attribution_coverage=coverage,
            attention_required=attention_required,
            attention_reason=attention_reason,
            legacy_baseline=not signals and not consumptions,
        )
        self.save_learning_health(health)
        return health

    def save_learning_health(self, health: LearningHealth) -> LearningHealth:
        """保存可公开投影的学习健康度摘要。"""
        if not isinstance(health, LearningHealth):
            raise TypeError("health must be LearningHealth")
        self._plugin.save_data(
            key=self._learning_key("learning_health", health.profile_id),
            value=health.to_dict(),
        )
        return health

    def save_board(self, board: RecommendationBoard) -> None:
        """保存当前用户榜单。"""
        board_key = self._profile_key("recommendation_board", board.profile_id)
        history_key = self._board_history_key(board.profile_id)
        with self._board_archive_lock, self._feedback_lock(board.profile_id):
            self._atomic_raw_update(
                updates={
                    board_key: board.to_dict(),
                    history_key: self._board_history_after_save(board),
                },
                recovery_key=board_key,
                action="recommendation_board_write_failed",
            )

    def load_board(self, profile_id: str) -> Optional[RecommendationBoard]:
        """读取当前用户榜单；损坏或不存在时返回空。"""
        return self._load_scoped_model(
            self._profile_key("recommendation_board", profile_id),
            RecommendationBoard,
            profile_id,
        )

    def _board_history_after_save(
        self, board: RecommendationBoard
    ) -> List[Dict[str, Any]]:
        """基于当前原始快照生成幂等的历史榜单列表。"""
        key = self._board_history_key(board.profile_id)
        raw_history = self._plugin.get_data(key=key)
        if raw_history is None:
            history: List[Any] = []
        elif isinstance(raw_history, list):
            history = list(raw_history)
        else:
            self._record_recovery(
                key, "ignored_corrupt_data", "board history must be a list"
            )
            history = []
        run_id = str(board.run_id or "").strip()
        if run_id and board.recommendations:
            has_snapshot = any(
                isinstance(item, Mapping)
                and str(item.get("profile_id") or "").strip() == board.profile_id
                and str(item.get("run_id") or "").strip() == run_id
                for item in history
            )
            if not has_snapshot:
                # 深拷贝避免测试替身或宿主缓存继续持有可变 board 引用。
                history.insert(0, copy.deepcopy(board.to_dict()))
        return history[: self._history_limit]

    def load_board_history(self, profile_id: str) -> List[RecommendationBoard]:
        """容错读取当前用户的历史榜单快照。"""
        target = str(profile_id or "").strip()
        key = self._board_history_key(target)
        value = self._plugin.get_data(key=key)
        if value is None:
            return []
        if not isinstance(value, list):
            self._record_recovery(
                key, "ignored_corrupt_data", "board history must be a list"
            )
            return []
        result: List[RecommendationBoard] = []
        for item in value[: self._history_limit]:
            try:
                board = RecommendationBoard.from_dict(item)
                if board.profile_id != target:
                    raise ValueError("board history profile_id mismatch")
            except (TypeError, ValueError, KeyError) as error:
                self._record_recovery(key, "ignored_corrupt_item", str(error))
                continue
            result.append(board)
        return result

    def save_archive(self, archive: ArchiveFeedback) -> None:
        """保存当前用户忽略归档。"""
        self._plugin.save_data(
            key=self._profile_key("archive", archive.profile_id), value=archive.to_dict()
        )

    def load_archive(self, profile_id: str) -> ArchiveFeedback:
        """读取当前用户归档；不存在或损坏时返回空归档。"""
        archive = self._load_scoped_model(
            self._profile_key("archive", profile_id), ArchiveFeedback, profile_id
        )
        return archive or ArchiveFeedback(profile_id=profile_id)

    def _load_feedback_index(
        self, profile_id: str, *, strict: bool = False
    ) -> FeedbackLedgerIndex:
        """读取反馈索引；查询时容错，写入前则拒绝覆盖损坏数据。"""
        key = self._feedback_index_key(profile_id)
        value = self._plugin.get_data(key=key)
        if value is None:
            return FeedbackLedgerIndex.empty(profile_id)
        try:
            index = FeedbackLedgerIndex.from_dict(value)
            if index.profile_id != str(profile_id):
                raise ValueError("feedback ledger index profile_id mismatch")
            return index
        except (TypeError, ValueError, KeyError) as error:
            self._record_recovery(key, "ignored_corrupt_data", str(error))
            if strict:
                raise ValueError("feedback ledger index is corrupt") from error
            return FeedbackLedgerIndex.empty(profile_id)

    def _load_feedback_segment(
        self,
        profile_id: str,
        segment_id: int,
        *,
        strict: bool = False,
    ) -> Optional[FeedbackEventSegment]:
        """读取一个反馈事件段并校验其 profile 与段号。"""
        key = self._feedback_segment_key(profile_id, segment_id)
        value = self._plugin.get_data(key=key)
        if value is None:
            return None
        try:
            segment = FeedbackEventSegment.from_dict(value)
            if segment.profile_id != str(profile_id):
                raise ValueError("feedback event segment profile_id mismatch")
            if segment.segment_id != int(segment_id):
                raise ValueError("feedback event segment id mismatch")
            return segment
        except (TypeError, ValueError, KeyError) as error:
            self._record_recovery(key, "ignored_corrupt_data", str(error))
            if strict:
                raise ValueError("feedback event segment is corrupt") from error
            return None

    def _find_feedback_event(
        self,
        index: FeedbackLedgerIndex,
        idempotency_key: str,
        *,
        strict: bool = False,
    ) -> Optional[FeedbackEvent]:
        """按索引指针回读幂等键对应的原始事件。"""
        pointer = index.idempotency.get(str(idempotency_key))
        if pointer is None:
            return None
        segment = self._load_feedback_segment(
            index.profile_id, pointer.segment_id, strict=strict
        )
        if segment is not None:
            for event in segment.events:
                if (
                    event.sequence == pointer.sequence
                    and event.idempotency_key == idempotency_key
                ):
                    return event
        detail = f"missing idempotent event at sequence {pointer.sequence}"
        self._record_recovery(
            self._feedback_index_key(index.profile_id),
            "ignored_broken_idempotency_pointer",
            detail,
        )
        if strict:
            raise ValueError(detail)
        return None

    def _enforce_feedback_retention(
        self, profile_id: str, index: FeedbackLedgerIndex
    ) -> None:
        """在事件提交后尽力执行保留上限，并显式标记维护失败。"""
        event_count = sum(reference.event_count for reference in index.segments)
        if event_count <= self._feedback_event_limit:
            return
        try:
            self.prune_feedback_events(profile_id, self._feedback_event_limit)
        except Exception:
            self._mark_retention_failure(profile_id, "feedback_events")

    def append_feedback_event(self, event: FeedbackEvent) -> FeedbackAppendResult:
        """幂等追加反馈事件，并标记调用方是否应触发后续学习。"""
        if not isinstance(event, FeedbackEvent):
            raise TypeError("event must be FeedbackEvent")
        if event.is_persisted:
            raise ValueError("only draft feedback events can be appended")
        profile_id = event.profile_id
        with self._feedback_lock(profile_id):
            index_key = self._feedback_index_key(profile_id)
            old_index = self._plugin.get_data(key=index_key)
            index = self._load_feedback_index(profile_id, strict=True)
            existing = self._find_feedback_event(
                index, event.idempotency_key, strict=True
            )
            if existing is not None:
                self._enforce_feedback_retention(profile_id, index)
                return FeedbackAppendResult(event=existing, created=False)

            last_reference = index.segments[-1] if index.segments else None
            creates_segment = not (
                last_reference is not None
                and last_reference.event_count < self._feedback_segment_size
            )
            if not creates_segment:
                segment_id = last_reference.segment_id
                segment = self._load_feedback_segment(
                    profile_id, segment_id, strict=True
                )
                if segment is None:
                    raise ValueError("feedback ledger references a missing segment")
            else:
                segment_id = last_reference.segment_id + 1 if last_reference else 1
                segment = FeedbackEventSegment(
                    profile_id=profile_id,
                    segment_id=segment_id,
                )

            segment_key = self._feedback_segment_key(profile_id, segment_id)
            old_segment = self._plugin.get_data(key=segment_key)
            if creates_segment and old_segment is not None:
                self._record_recovery(
                    segment_key,
                    "preserved_orphan_feedback_segment",
                    "segment exists without an index reference",
                )
                raise ValueError("unindexed feedback event segment already exists")
            persisted = event.assign_persistence(
                event_id=uuid.uuid4().hex,
                sequence=index.next_sequence,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            updated_segment = segment.append(persisted)
            updated_index = index.with_event(updated_segment, persisted)

            try:
                self._plugin.save_data(
                    key=segment_key,
                    value=updated_segment.to_dict(),
                )
                verified_segment = self._load_feedback_segment(
                    profile_id, segment_id, strict=True
                )
                if (
                    verified_segment is None
                    or verified_segment.events[-1] != persisted
                ):
                    raise ValueError("feedback event segment readback mismatch")

                self._plugin.save_data(key=index_key, value=updated_index.to_dict())
                verified_index = self._load_feedback_index(profile_id, strict=True)
                verified_event = self._find_feedback_event(
                    verified_index, event.idempotency_key, strict=True
                )
                if verified_event != persisted:
                    raise ValueError("feedback ledger index readback mismatch")
            except Exception as error:
                rollback_errors: List[str] = []
                for key, value in (
                    (index_key, old_index),
                    (segment_key, old_segment),
                ):
                    try:
                        self._restore_raw(key, value)
                    except Exception as rollback_error:
                        rollback_errors.append(f"{key}: {rollback_error}")
                if rollback_errors:
                    self._record_recovery(
                        index_key,
                        "feedback_ledger_rollback_failed",
                        "; ".join(rollback_errors),
                    )
                    raise RuntimeError(
                        "feedback ledger append and rollback both failed"
                    ) from error
                raise
            self._enforce_feedback_retention(profile_id, updated_index)
            return FeedbackAppendResult(event=persisted, created=True)

    def load_feedback_event(
        self, profile_id: str, idempotency_key: str
    ) -> Optional[FeedbackEvent]:
        """按幂等键读取原事件；损坏指针不会生成替代事件。"""
        target_key = str(idempotency_key or "").strip()
        if not target_key:
            raise ValueError("idempotency_key is required")
        with self._feedback_lock(profile_id):
            index = self._load_feedback_index(profile_id)
            return self._find_feedback_event(index, target_key)

    def load_feedback_events(
        self,
        profile_id: str,
        *,
        after_sequence: int = 0,
        limit: Optional[int] = None,
    ) -> List[FeedbackEvent]:
        """按 sequence 顺序读取一个 profile 的反馈事件。"""
        cursor = max(0, int(after_sequence))
        requested_limit = None if limit is None else max(0, int(limit))
        if requested_limit == 0:
            return []
        with self._feedback_lock(profile_id):
            index = self._load_feedback_index(profile_id)
            result: List[FeedbackEvent] = []
            for reference in index.segments:
                segment = self._load_feedback_segment(
                    profile_id, reference.segment_id
                )
                if segment is None:
                    continue
                try:
                    actual_reference = segment.to_reference()
                    if actual_reference != reference:
                        raise ValueError("feedback segment reference mismatch")
                except ValueError as error:
                    self._record_recovery(
                        self._feedback_segment_key(profile_id, reference.segment_id),
                        "ignored_corrupt_data",
                        str(error),
                    )
                    continue
                for stored_event in segment.events:
                    if stored_event.sequence <= cursor:
                        continue
                    result.append(stored_event)
                    if requested_limit is not None and len(result) >= requested_limit:
                        return result
            return result

    def _load_preference_memory(
        self, profile_id: str, *, strict: bool = False
    ) -> PreferenceMemory:
        """读取确认态偏好记忆；新键缺失时返回空 schema。"""
        key = self._profile_key("preference_memory", profile_id)
        value = self._plugin.get_data(key=key)
        if value is None:
            return PreferenceMemory.empty(profile_id)
        try:
            memory = PreferenceMemory.from_dict(value)
            if memory.profile_id != str(profile_id):
                raise ValueError("preference memory profile_id mismatch")
            return memory
        except (TypeError, ValueError, KeyError) as error:
            self._record_recovery(key, "ignored_corrupt_data", str(error))
            if strict:
                raise ValueError("preference memory is corrupt") from error
            return PreferenceMemory.empty(profile_id)

    def load_preference_memory(self, profile_id: str) -> PreferenceMemory:
        """读取当前 profile 的确认态偏好记忆。"""
        with self._feedback_lock(profile_id):
            return self._load_preference_memory(profile_id)

    def load_policy_snapshot(self, profile_id: str) -> Optional[PolicySnapshot]:
        """读取当前 profile 最近一次经过校验的版本化策略快照。"""
        target = str(profile_id or "").strip()
        self._scope(target, "profile_id")
        with self._feedback_lock(target):
            return self._load_scoped_model(
                self._learning_key("policy_snapshot", target),
                PolicySnapshot,
                target,
            )

    def save_policy_snapshot(
        self,
        snapshot: PolicySnapshot,
        *,
        expected_memory_revision: int,
    ) -> Optional[PolicySnapshot]:
        """仅在确认记忆 revision 未变化时原子替换策略快照。"""
        if not isinstance(snapshot, PolicySnapshot):
            raise TypeError("snapshot must be PolicySnapshot")
        target = snapshot.profile_id
        with self._feedback_lock(target):
            memory = self._load_preference_memory(target, strict=True)
            if memory.memory_revision != int(expected_memory_revision):
                return None
            if snapshot.memory_revision != memory.memory_revision:
                raise ValueError("policy snapshot memory_revision mismatch")
            key = self._learning_key("policy_snapshot", target)
            existing_raw = self._plugin.get_data(key=key)
            if existing_raw is not None:
                try:
                    existing = PolicySnapshot.from_dict(existing_raw)
                    if existing.profile_id != target:
                        raise ValueError("policy snapshot profile_id mismatch")
                except (TypeError, ValueError, KeyError) as error:
                    self._record_recovery(
                        key, "replaced_corrupt_policy_snapshot", str(error)
                    )
                    existing = None
                if (
                    existing is not None
                    and existing.policy_version == snapshot.policy_version
                ):
                    return existing
            self._atomic_raw_update(
                updates={key: snapshot.to_dict()},
                recovery_key=key,
                action="policy_snapshot_write_failed",
            )
            stored = self._load_scoped_model(key, PolicySnapshot, target)
            if stored != snapshot:
                raise ValueError("policy snapshot readback mismatch")
            return stored

    def project_preference_memory(
        self,
        profile_id: str,
        items: List[PreferenceMemoryItem],
        *,
        expected_revision: int,
        source_event_sequence: int,
    ) -> MemoryProjectionResult:
        """以 profile 锁和 CAS 投影确认记忆，拒绝乱序覆盖。"""
        proposed = list(items or [])
        with self._feedback_lock(profile_id):
            key = self._profile_key("preference_memory", profile_id)
            old_memory = self._plugin.get_data(key=key)
            memory = self._load_preference_memory(profile_id, strict=True)
            result = memory.project(
                proposed,
                expected_revision=expected_revision,
                source_event_sequence=source_event_sequence,
            )
            if not result.applied:
                return result
            try:
                self._plugin.save_data(key=key, value=result.memory.to_dict())
                stored = self._load_preference_memory(profile_id, strict=True)
                if stored != result.memory:
                    raise ValueError("preference memory readback mismatch")
            except Exception:
                self._restore_raw(key, old_memory)
                raise
            return result

    def initialize_additive_storage(self, profile_id: str) -> List[str]:
        """原子创建缺失的新账本与记忆空 schema，不改写旧业务数据。"""
        with self._feedback_lock(profile_id):
            index_key = self._feedback_index_key(profile_id)
            memory_key = self._profile_key("preference_memory", profile_id)
            old_index = self._plugin.get_data(key=index_key)
            old_memory = self._plugin.get_data(key=memory_key)

            if old_index is not None:
                self._load_feedback_index(profile_id, strict=True)
            if old_memory is not None:
                self._load_preference_memory(profile_id, strict=True)

            created: List[str] = []
            try:
                if old_index is None:
                    empty_index = FeedbackLedgerIndex.empty(profile_id)
                    self._plugin.save_data(key=index_key, value=empty_index.to_dict())
                    if self._load_feedback_index(profile_id, strict=True) != empty_index:
                        raise ValueError("feedback ledger migration readback mismatch")
                    created.append("feedback_event_index")
                if old_memory is None:
                    empty_memory = PreferenceMemory.empty(profile_id)
                    self._plugin.save_data(key=memory_key, value=empty_memory.to_dict())
                    if self._load_preference_memory(profile_id, strict=True) != empty_memory:
                        raise ValueError("preference memory migration readback mismatch")
                    created.append("preference_memory")
            except Exception as error:
                rollback_errors: List[str] = []
                for key, value in (
                    (index_key, old_index),
                    (memory_key, old_memory),
                ):
                    try:
                        self._restore_raw(key, value)
                    except Exception as rollback_error:
                        rollback_errors.append(f"{key}: {rollback_error}")
                detail = type(error).__name__
                if rollback_errors:
                    detail = f"{detail}; rollback_failed={len(rollback_errors)}"
                self._record_recovery(
                    self._profile_key("storage_migration", profile_id),
                    "profile_storage_migration_failed",
                    detail,
                )
                if rollback_errors:
                    raise RuntimeError(
                        "profile storage migration and rollback both failed"
                    ) from error
                raise
            return created

    @staticmethod
    def _backfill_identity_items(items: Any) -> Tuple[Any, int, int]:
        """补全候选或榜单条目身份，非映射项目保持原样。"""
        if not isinstance(items, list):
            return items, 0, 0
        migrated: List[Any] = []
        updated = 0
        unresolved = 0
        for item in items:
            if not isinstance(item, Mapping):
                migrated.append(item)
                continue
            payload, changed, missing = backfill_media_identity_payload(item)
            migrated.append(payload)
            updated += int(changed)
            unresolved += int(missing)
        return migrated, updated, unresolved

    @classmethod
    def _backfill_board_payload(cls, value: Any) -> Tuple[Any, int, int]:
        """复制榜单载荷并补全推荐条目的媒体身份。"""
        if not isinstance(value, Mapping):
            return value, 0, 0
        payload = copy.deepcopy(dict(value))
        recommendations, updated, unresolved = cls._backfill_identity_items(
            payload.get("recommendations")
        )
        if updated:
            payload["recommendations"] = recommendations
        return payload, updated, unresolved

    @classmethod
    def _backfill_snapshot_payload(cls, value: Any) -> Tuple[Any, int, int]:
        """补全候选快照身份并按新内容重新封存哈希。"""
        if not isinstance(value, Mapping):
            return value, 0, 0
        payload = copy.deepcopy(dict(value))
        candidates, updated, unresolved = cls._backfill_identity_items(
            payload.get("candidates")
        )
        if not updated:
            return payload, 0, unresolved
        payload["candidates"] = candidates
        if not unresolved:
            payload["schema_version"] = 4
            snapshot = CandidateSnapshot(
                profile_id=payload.get("profile_id"),
                run_id=payload.get("run_id"),
                profile_version=dict(payload.get("profile_version") or {}),
                retrieval_plan=dict(payload.get("retrieval_plan") or {}),
                candidates=candidates,
                source_stats=dict(payload.get("source_stats") or {}),
                exclusion_counts=dict(payload.get("exclusion_counts") or {}),
                generated_at=str(payload.get("generated_at") or ""),
                schema_version=4,
            ).seal()
        else:
            payload["schema_version"] = min(
                3, int(payload.get("schema_version") or 1)
            )
            snapshot = CandidateSnapshot.from_dict(payload)
        return snapshot.to_dict(), updated, unresolved

    def migrate_media_identities(self, profile_id: str) -> Dict[str, int]:
        """原子迁移旧榜单、榜单历史和候选快照身份，不删除未解析数据。"""
        target = str(profile_id or "").strip()
        if not target:
            raise ValueError("profile_id is required")
        board_key = self._profile_key("recommendation_board", target)
        history_key = self._board_history_key(target)
        updates: Dict[str, Any] = {}
        updated_count = 0
        unresolved_count = 0

        raw_board = self._plugin.get_data(key=board_key)
        board, updated, unresolved = self._backfill_board_payload(raw_board)
        updated_count += updated
        unresolved_count += unresolved
        if updated:
            updates[board_key] = board

        raw_history = self._plugin.get_data(key=history_key)
        if isinstance(raw_history, list):
            migrated_history: List[Any] = []
            history_changed = False
            for item in raw_history:
                migrated, updated, unresolved = self._backfill_board_payload(item)
                migrated_history.append(migrated)
                updated_count += updated
                unresolved_count += unresolved
                history_changed = history_changed or bool(updated)
            if history_changed:
                updates[history_key] = migrated_history

        for reference in self._candidate_index_entries(target, reconcile=False):
            key = self._candidate_key(reference["run_id"], target)
            raw_snapshot = self._plugin.get_data(key=key)
            snapshot, updated, unresolved = self._backfill_snapshot_payload(raw_snapshot)
            updated_count += updated
            unresolved_count += unresolved
            if updated:
                updates[key] = snapshot

        if updates:
            self._atomic_raw_update(
                updates=updates,
                recovery_key=self._profile_key("media_identity_migration", target),
                action="media_identity_migration_failed",
            )
            for key, expected in updates.items():
                if self._plugin.get_data(key=key) != expected:
                    raise ValueError("media identity migration readback mismatch")
        return {
            "identity_updated_count": updated_count,
            "identity_unresolved_count": unresolved_count,
            "identity_storage_count": len(updates),
        }

    def _load_candidate_index(
        self, profile_id: str, *, strict: bool = False
    ) -> Dict[str, Any]:
        """读取候选快照索引；损坏索引不会被静默重建。"""
        key = self._candidate_index_key(profile_id)
        value = self._plugin.get_data(key=key)
        if value is None:
            return {"profile_id": str(profile_id), "snapshots": [], "schema_version": 1}
        try:
            if not isinstance(value, Mapping):
                raise ValueError("candidate snapshot index must be a mapping")
            if str(value.get("profile_id") or "") != str(profile_id):
                raise ValueError("candidate snapshot index profile_id mismatch")
            snapshots = value.get("snapshots") or []
            if not isinstance(snapshots, list):
                raise ValueError("candidate snapshot index snapshots must be a list")
            normalized = []
            seen = set()
            for item in snapshots:
                if not isinstance(item, Mapping):
                    raise ValueError("candidate snapshot index entry is invalid")
                run_id = str(item.get("run_id") or "").strip()
                if not run_id or run_id in seen:
                    raise ValueError("candidate snapshot index run_id is invalid")
                seen.add(run_id)
                normalized.append(
                    {
                        "run_id": run_id,
                        "generated_at": str(item.get("generated_at") or ""),
                    }
                )
            return {
                "profile_id": str(profile_id),
                "snapshots": normalized,
                "schema_version": int(value.get("schema_version") or 1),
            }
        except (TypeError, ValueError, KeyError) as error:
            self._record_recovery(key, "ignored_corrupt_data", str(error))
            if strict:
                raise ValueError("candidate snapshot index is corrupt") from error
            return {"profile_id": str(profile_id), "snapshots": [], "schema_version": 1}

    def _candidate_index_entries(
        self, profile_id: str, *, reconcile: bool = False
    ) -> List[Dict[str, str]]:
        """返回索引条目，并可用仍在运行历史中的 run_id 补齐旧快照。"""
        with self._feedback_lock(profile_id):
            index = self._load_candidate_index(profile_id, strict=True)
            entries = list(index["snapshots"])
            known = {item["run_id"] for item in entries}
            history = self.load_run_history(profile_id)
            board = self.load_board(profile_id)
            run_ids = [run.run_id for run in reversed(history)]
            if board is not None:
                run_ids.extend(
                    item
                    for item in (board.previous_run_id, board.run_id)
                    if item
                )
            changed = False
            for run_id in run_ids:
                run_id = str(run_id or "").strip()
                if not run_id or run_id in known:
                    continue
                snapshot = self.load_candidate_snapshot_record(run_id, profile_id)
                if snapshot is None:
                    continue
                entries.append(
                    {"run_id": run_id, "generated_at": snapshot.generated_at}
                )
                known.add(run_id)
                changed = True
            if changed and reconcile:
                updated = {
                    "profile_id": str(profile_id),
                    "snapshots": entries,
                    "schema_version": 1,
                }
                self._atomic_raw_update(
                    updates={self._candidate_index_key(profile_id): updated},
                    recovery_key=self._candidate_index_key(profile_id),
                    action="candidate_snapshot_index_reconcile_failed",
                )
            return entries

    def candidate_snapshot_references(
        self, profile_id: str, *, reconcile: bool = False
    ) -> List[Dict[str, str]]:
        """返回候选快照引用；仅生命周期裁剪会显式补写旧索引。"""
        return self._candidate_index_entries(profile_id, reconcile=reconcile)

    def save_candidate_snapshot(self, snapshot: CandidateSnapshot) -> None:
        """首次保存候选快照并原子登记 profile 级索引。"""
        if not isinstance(snapshot, CandidateSnapshot):
            raise TypeError("snapshot must be CandidateSnapshot")
        profile_id = snapshot.profile_id
        key = self._candidate_key(snapshot.run_id, profile_id)
        index_key = self._candidate_index_key(profile_id)
        with self._feedback_lock(profile_id):
            if self._plugin.get_data(key=key) is not None:
                raise ValueError("candidate snapshot already exists")
            payload = snapshot.to_dict()
            CandidateSnapshot.from_dict(payload)
            indexed_entries = self._candidate_index_entries(profile_id, reconcile=False)
            if any(item["run_id"] == snapshot.run_id for item in indexed_entries):
                raise ValueError("candidate snapshot index already contains run_id")
            all_entries = [
                *indexed_entries,
                {"run_id": snapshot.run_id, "generated_at": snapshot.generated_at},
            ]
            retained_entries = all_entries[-self._candidate_snapshot_limit :]
            retained_ids = {item["run_id"] for item in retained_entries}
            delete_keys = [
                self._candidate_key(item["run_id"], profile_id)
                for item in all_entries[: -self._candidate_snapshot_limit]
                if item["run_id"] not in retained_ids
            ]
            updated_index = {
                "profile_id": profile_id,
                "snapshots": retained_entries,
                "schema_version": 1,
            }
            self._atomic_raw_update(
                updates={key: payload, index_key: updated_index},
                delete_keys=delete_keys,
                recovery_key=key,
                action="candidate_snapshot_write_failed",
            )
            verified = self.load_candidate_snapshot_record(snapshot.run_id, profile_id)
            if verified is None or verified.content_hash != snapshot.content_hash:
                raise ValueError("candidate snapshot readback mismatch")

    def load_candidate_snapshot_record(
        self, run_id: str, profile_id: str
    ) -> Optional[CandidateSnapshot]:
        """读取并校验完整候选快照记录；损坏时返回空。"""
        key = self._candidate_key(run_id, profile_id)
        value = self._plugin.get_data(key=key)
        if value is None:
            return None
        try:
            snapshot = CandidateSnapshot.from_dict(value)
            if snapshot.run_id != str(run_id):
                raise ValueError("candidate snapshot run_id mismatch")
            if snapshot.profile_id != str(profile_id):
                raise ValueError("candidate snapshot profile_id mismatch")
            return snapshot
        except (TypeError, ValueError, KeyError) as error:
            self._record_recovery(key, "ignored_corrupt_data", str(error))
            return None

    def load_candidate_snapshot(self, run_id: str, profile_id: str) -> List[Candidate]:
        """读取本轮候选快照；损坏时返回空列表并记录证据。"""
        snapshot = self.load_candidate_snapshot_record(run_id, profile_id)
        return list(snapshot.candidates) if snapshot is not None else []

    def prune_candidate_snapshots(self, profile_id: str, limit: int) -> int:
        """保留最新的有限候选快照，并原子删除过期快照。"""
        keep_limit = max(1, min(int(limit), 500))
        with self._feedback_lock(profile_id):
            entries = self._candidate_index_entries(profile_id, reconcile=True)
            if len(entries) <= keep_limit:
                return 0
            retained = entries[-keep_limit:]
            removed = entries[:-keep_limit]
            retained_ids = {item["run_id"] for item in retained}
            delete_keys = [
                self._candidate_key(item["run_id"], profile_id)
                for item in removed
                if item["run_id"] not in retained_ids
            ]
            updated_index = {
                "profile_id": str(profile_id),
                "snapshots": retained,
                "schema_version": 1,
            }
            self._atomic_raw_update(
                updates={self._candidate_index_key(profile_id): updated_index},
                delete_keys=delete_keys,
                recovery_key=self._candidate_index_key(profile_id),
                action="candidate_snapshot_prune_failed",
            )
            return len(delete_keys)

    def prune_feedback_events(self, profile_id: str, limit: int) -> int:
        """裁剪反馈事件旧段，保留单调序号与可重放尾部。"""
        keep_limit = max(1, min(int(limit), 100000))
        with self._feedback_lock(profile_id):
            index = self._load_feedback_index(profile_id, strict=True)
            events: List[FeedbackEvent] = []
            old_segment_keys: List[str] = []
            for reference in index.segments:
                old_segment_keys.append(
                    self._feedback_segment_key(profile_id, reference.segment_id)
                )
                segment = self._load_feedback_segment(
                    profile_id, reference.segment_id, strict=True
                )
                if segment is None:
                    raise ValueError("feedback ledger references a missing segment")
                events.extend(segment.events)
            if len(events) <= keep_limit:
                return 0
            retention_start = max(0, len(events) - keep_limit)
            pending_sequences = [
                job.event_sequence
                for job in self._load_feedback_queue_locked(
                    profile_id, strict=True
                )
                if not job.terminal
            ]
            if pending_sequences:
                earliest_pending = min(pending_sequences)
                pending_index = next(
                    (
                        index
                        for index, event in enumerate(events)
                        if event.sequence >= earliest_pending
                    ),
                    0,
                )
                retention_start = min(retention_start, pending_index)
            retained_events = events[retention_start:]
            segments: List[FeedbackEventSegment] = []
            for offset in range(0, len(retained_events), self._feedback_segment_size):
                segment_id = len(segments) + 1
                segments.append(
                    FeedbackEventSegment(
                        profile_id=profile_id,
                        segment_id=segment_id,
                        events=tuple(
                            retained_events[offset : offset + self._feedback_segment_size]
                        ),
                    )
                )
            references = tuple(segment.to_reference() for segment in segments)
            idempotency = {
                event.idempotency_key: FeedbackEventPointer(
                    segment_id=segment.segment_id,
                    sequence=event.sequence,
                )
                for segment in segments
                for event in segment.events
            }
            updated_index = FeedbackLedgerIndex(
                profile_id=profile_id,
                next_sequence=index.next_sequence,
                retained_from_sequence=retained_events[0].sequence,
                segments=references,
                idempotency=idempotency,
            ).to_dict()
            updates = {
                self._feedback_segment_key(profile_id, segment.segment_id): segment.to_dict()
                for segment in segments
            }
            updates[self._feedback_index_key(profile_id)] = updated_index
            delete_keys = [
                key
                for key in old_segment_keys
                if key not in updates
            ]
            self._atomic_raw_update(
                updates=updates,
                delete_keys=delete_keys,
                recovery_key=self._feedback_index_key(profile_id),
                action="feedback_event_prune_failed",
            )
            return len(events) - len(retained_events)

    def _load_feedback_queue_locked(
        self, profile_id: str, *, strict: bool = False
    ) -> List[FeedbackQueueJob]:
        """在 profile 反馈锁内恢复队列，并拒绝静默丢失未完成任务。"""
        key = self._learning_key("feedback_queue", profile_id)
        value = self._plugin.get_data(key=key)
        if value is None:
            return []
        if not isinstance(value, list):
            self._record_recovery(
                key, "ignored_corrupt_data", "feedback queue must be a list"
            )
            if strict:
                raise ValueError("feedback queue data is corrupt")
            return []
        result: List[FeedbackQueueJob] = []
        seen_job_ids = set()
        seen_sequences = set()
        for raw in value:
            try:
                job = FeedbackQueueJob.from_dict(raw)
            except (TypeError, ValueError, KeyError) as error:
                self._record_recovery(key, "ignored_corrupt_item", str(error))
                if strict:
                    raise ValueError("feedback queue contains a corrupt job") from error
                continue
            if (
                job.profile_id != profile_id
                or job.job_id in seen_job_ids
                or job.event_sequence in seen_sequences
            ):
                self._record_recovery(
                    key,
                    "ignored_cross_profile_or_duplicate_item",
                    job.job_id,
                )
                if strict:
                    raise ValueError("feedback queue scope or identity is invalid")
                continue
            seen_job_ids.add(job.job_id)
            seen_sequences.add(job.event_sequence)
            result.append(job)
        return sorted(result, key=lambda item: (item.event_sequence, item.job_id))

    def load_feedback_queue(self, profile_id: str) -> List[FeedbackQueueJob]:
        """按 profile 返回经过校验的持久反馈任务。"""
        target = str(profile_id or "").strip()
        self._scope(target, "profile_id")
        with self._feedback_lock(target):
            return self._load_feedback_queue_locked(target)

    def _save_feedback_queue_locked(
        self, profile_id: str, jobs: Iterable[FeedbackQueueJob]
    ) -> None:
        """在反馈锁内原子保存同一 profile 的完整队列。"""
        target = str(profile_id or "").strip()
        self._scope(target, "profile_id")
        values = list(jobs or ())
        if any(job.profile_id != target for job in values):
            raise ValueError("feedback queue contains a cross-profile job")
        key = self._learning_key("feedback_queue", target)
        self._atomic_raw_update(
            updates={key: [job.to_dict() for job in values]},
            recovery_key=key,
            action="feedback_queue_save_failed",
        )

    def enqueue_feedback_job(
        self,
        job: FeedbackQueueJob,
        *,
        limit: int = 200,
        debounce_until: datetime = None,
    ) -> FeedbackQueueJob:
        """幂等追加任务，并可把同 profile 未认领任务推迟到统一截止时间。"""
        if not isinstance(job, FeedbackQueueJob):
            raise TypeError("job must be FeedbackQueueJob")
        keep_limit = max(1, min(int(limit), 100000))
        with self._feedback_lock(job.profile_id):
            jobs = self._load_feedback_queue_locked(job.profile_id, strict=True)
            if debounce_until is not None:
                jobs = [
                    item.defer(debounce_until)
                    if not item.terminal and item.status != "running"
                    else item
                    for item in jobs
                ]
            existing = next(
                (item for item in jobs if item.job_id == job.job_id), None
            )
            if existing is not None:
                self._save_feedback_queue_locked(job.profile_id, jobs)
                return existing
            while len(jobs) >= keep_limit:
                terminal_index = next(
                    (index for index, item in enumerate(jobs) if item.terminal), None
                )
                if terminal_index is None:
                    raise ValueError("feedback queue is full of unfinished jobs")
                jobs.pop(terminal_index)
            jobs.append(job)
            jobs.sort(key=lambda item: (item.event_sequence, item.job_id))
            self._save_feedback_queue_locked(job.profile_id, jobs)
            return job

    def claim_next_feedback_job(
        self, profile_id: str, *, lease_id: str, now: datetime = None
    ) -> Optional[FeedbackQueueJob]:
        """按事件序号认领一个就绪任务，并持久化唯一租约。"""
        target = str(profile_id or "").strip()
        self._scope(target, "profile_id")
        with self._feedback_lock(target):
            jobs = self._load_feedback_queue_locked(target, strict=True)
            for index, job in enumerate(jobs):
                if job.terminal:
                    continue
                if not job.ready(now):
                    return None
                claimed = job.claim(lease_id, now)
                jobs[index] = claimed
                self._save_feedback_queue_locked(target, jobs)
                return claimed
            return None

    def replace_feedback_job(
        self,
        job: FeedbackQueueJob,
        *,
        expected_lease_id: str = "",
    ) -> bool:
        """仅在租约仍匹配时替换任务，拒绝迟到旧进程覆盖恢复结果。"""
        if not isinstance(job, FeedbackQueueJob):
            raise TypeError("job must be FeedbackQueueJob")
        expected = str(expected_lease_id or "").strip()
        with self._feedback_lock(job.profile_id):
            jobs = self._load_feedback_queue_locked(job.profile_id, strict=True)
            for index, current in enumerate(jobs):
                if current.job_id != job.job_id:
                    continue
                if expected and (
                    current.status != "running" or current.lease_id != expected
                ):
                    return False
                jobs[index] = job
                self._save_feedback_queue_locked(job.profile_id, jobs)
                return True
            return False

    def recover_feedback_queue(
        self, profile_id: str, *, now: datetime = None
    ) -> int:
        """重启时把遗留 running 任务恢复为 queued，并清除旧租约。"""
        target = str(profile_id or "").strip()
        self._scope(target, "profile_id")
        with self._feedback_lock(target):
            jobs = self._load_feedback_queue_locked(target, strict=True)
            recovered = [job.recover(now) for job in jobs]
            count = sum(before != after for before, after in zip(jobs, recovered))
            if count:
                self._save_feedback_queue_locked(target, recovered)
            return count

    def prune_feedback_queue(self, profile_id: str, limit: int) -> int:
        """裁剪最旧终态任务，未完成任务即使超上限也全部保留。"""
        target = str(profile_id or "").strip()
        self._scope(target, "profile_id")
        keep_limit = max(1, min(int(limit), 100000))
        with self._feedback_lock(target):
            jobs = self._load_feedback_queue_locked(target, strict=True)
            if len(jobs) <= keep_limit:
                return 0
            active = [job for job in jobs if not job.terminal]
            terminal_slots = max(0, keep_limit - len(active))
            terminal = [job for job in jobs if job.terminal]
            selected_terminal_ids = {
                job.job_id for job in terminal[-terminal_slots:]
            } if terminal_slots else set()
            retained = [
                job
                for job in jobs
                if not job.terminal or job.job_id in selected_terminal_ids
            ]
            removed = len(jobs) - len(retained)
            if removed:
                self._save_feedback_queue_locked(target, retained)
            return removed

    def prune_learning_list(self, profile_id: str, prefix: str, limit: int) -> int:
        """裁剪未来队列、对话、分析或归因单键列表。"""
        if str(prefix or "").strip() == "feedback_queue":
            return self.prune_feedback_queue(profile_id, limit)
        if str(prefix or "").strip() == "memory_proposals":
            return self.prune_memory_proposals(profile_id, limit)
        if str(prefix or "").strip() == "pending_questions":
            return self.prune_pending_questions(profile_id, limit)
        if str(prefix or "").strip() == "conversation_messages":
            return self.prune_conversation_records(profile_id, limit)
        keep_limit = max(1, min(int(limit), 100000))
        key = self._learning_key(prefix, profile_id)
        with self._feedback_lock(profile_id):
            value = self._plugin.get_data(key=key)
            if value is None:
                return 0
            if not isinstance(value, list):
                self._record_recovery(
                    key, "ignored_corrupt_data", "bounded learning data must be a list"
                )
                raise ValueError(f"{prefix} data is corrupt")
            if len(value) <= keep_limit:
                return 0
            retained = (
                self._retain_agent_analysis_items(
                    profile_id,
                    value,
                    keep_limit,
                )
                if str(prefix or "").strip() == "agent_analysis"
                else value[-keep_limit:]
            )
            self._atomic_raw_update(
                updates={key: retained},
                recovery_key=key,
                action=f"{prefix}_prune_failed",
            )
            return len(value) - len(retained)

    def _retain_agent_analysis_items(
        self,
        profile_id: str,
        items: Iterable[Any],
        keep_limit: int,
        *,
        mandatory_analysis_ids: Iterable[str] = (),
        mandatory_event_ids: Iterable[str] = (),
    ) -> List[Any]:
        """裁剪混合分析列表，同时保留当前榜单与未处理评论引用。"""
        values = list(items or ())
        limit = max(1, min(int(keep_limit), 100000))
        by_analysis_id: Dict[str, Tuple[int, Mapping[str, Any]]] = {}
        for index, item in enumerate(values):
            if not isinstance(item, Mapping) or str(
                item.get("record_type") or ""
            ) != "recommendation_analysis":
                continue
            analysis_id = str(item.get("analysis_id") or "").strip()
            if analysis_id:
                by_analysis_id[analysis_id] = (index, item)

        pinned_ids = {
            str(value or "").strip()
            for value in mandatory_analysis_ids or ()
            if str(value or "").strip()
        }
        board = self.load_board(profile_id)
        if board is not None:
            pinned_ids.update(
                item.analysis_id
                for item in board.recommendations
                if item.analysis_id
            )
        try:
            pending_jobs = [
                job
                for job in self._load_feedback_queue_locked(
                    profile_id, strict=True
                )
                if not job.terminal
            ]
        except Exception:
            return values
        for job in pending_jobs:
            events = self.load_feedback_events(
                profile_id,
                after_sequence=job.event_sequence - 1,
                limit=1,
            )
            if not events:
                return values
            event = events[0]
            if event.event_id != job.event_id:
                return values
            if event.kind == "analysis_comment" and event.analysis_id:
                pinned_ids.add(event.analysis_id)
        mandatory_indexes = set()
        for analysis_id in pinned_ids:
            located = by_analysis_id.get(analysis_id)
            if located is not None:
                mandatory_indexes.add(located[0])

        event_ids = {
            str(value or "").strip()
            for value in mandatory_event_ids or ()
            if str(value or "").strip()
        }
        if event_ids:
            mandatory_indexes.update(
                index
                for index, item in enumerate(values)
                if isinstance(item, Mapping)
                and str(item.get("record_type") or "")
                == "feedback_understanding"
                and str(item.get("event_id") or "") in event_ids
            )
        budget = max(0, limit - len(mandatory_indexes))
        optional_indexes = [
            index for index in range(len(values)) if index not in mandatory_indexes
        ]
        retained_indexes = mandatory_indexes | set(
            optional_indexes[-budget:] if budget else []
        )
        return [
            item for index, item in enumerate(values) if index in retained_indexes
        ]

    @staticmethod
    def _retain_pending_records(
        items: List[Any], keep_limit: int, pending_statuses: Iterable[str]
    ) -> List[Any]:
        """保留全部未完成记录，并用剩余名额保存最新终态记录。"""
        pending = {str(value or "").strip() for value in pending_statuses}
        active_indexes = {
            index
            for index, item in enumerate(items)
            if isinstance(item, Mapping)
            and str(item.get("status") or "").strip() in pending
        }
        terminal_indexes = [
            index for index in range(len(items)) if index not in active_indexes
        ]
        terminal_slots = max(0, int(keep_limit) - len(active_indexes))
        selected = active_indexes | set(
            terminal_indexes[-terminal_slots:] if terminal_slots else []
        )
        return [item for index, item in enumerate(items) if index in selected]

    def _prune_pending_record_list(
        self,
        profile_id: str,
        prefix: str,
        limit: int,
        pending_statuses: Iterable[str],
    ) -> int:
        """裁剪指定待确认列表，同时保护所有未完成项。"""
        keep_limit = max(1, min(int(limit), 100000))
        key = self._learning_key(prefix, profile_id)
        with self._feedback_lock(profile_id):
            value = self._plugin.get_data(key=key)
            if value is None:
                return 0
            if not isinstance(value, list):
                self._record_recovery(
                    key, "ignored_corrupt_data", f"{prefix} data must be a list"
                )
                raise ValueError(f"{prefix} data is corrupt")
            retained = self._retain_pending_records(
                list(value), keep_limit, pending_statuses
            )
            removed = len(value) - len(retained)
            if removed:
                self._atomic_raw_update(
                    updates={key: retained},
                    recovery_key=key,
                    action=f"{prefix}_prune_failed",
                )
            return removed

    def prune_memory_proposals(self, profile_id: str, limit: int) -> int:
        """裁剪记忆提案终态历史，但保留全部待确认提案。"""
        return self._prune_pending_record_list(
            profile_id, "memory_proposals", limit, {"pending_confirmation"}
        )

    def prune_pending_questions(self, profile_id: str, limit: int) -> int:
        """裁剪问询终态历史，但保留全部未回答问题。"""
        return self._prune_pending_record_list(
            profile_id, "pending_questions", limit, {"pending"}
        )

    def load_feedback_understandings(
        self, profile_id: str
    ) -> List[FeedbackUnderstandingRecord]:
        """读取有界反馈理解记录，并忽略同键中的其他分析类型。"""
        target = str(profile_id or "").strip()
        self._scope(target, "profile_id")
        key = self._learning_key("agent_analysis", target)
        with self._feedback_lock(target):
            value = self._plugin.get_data(key=key)
            if value is None:
                return []
            if not isinstance(value, list):
                self._record_recovery(
                    key, "ignored_corrupt_data", "agent analysis must be a list"
                )
                return []
            result: List[FeedbackUnderstandingRecord] = []
            for item in value:
                if not isinstance(item, Mapping) or str(
                    item.get("record_type") or ""
                ) != "feedback_understanding":
                    continue
                try:
                    record = FeedbackUnderstandingRecord.from_dict(item)
                    if record.profile_id != target:
                        raise ValueError("feedback understanding profile mismatch")
                except (TypeError, ValueError, KeyError) as error:
                    self._record_recovery(
                        key, "ignored_corrupt_item", str(error)
                    )
                    continue
                result.append(record)
            return sorted(
                result, key=lambda item: (item.event_sequence, item.record_id)
            )

    def load_recommendation_analyses(
        self, profile_id: str, run_id: str = ""
    ) -> List[RecommendationAnalysis]:
        """读取结构化推荐分析，并与反馈理解记录安全共用存储键。"""
        target = str(profile_id or "").strip()
        target_run = str(run_id or "").strip()
        self._scope(target, "profile_id")
        key = self._learning_key("agent_analysis", target)
        with self._feedback_lock(target):
            value = self._plugin.get_data(key=key)
            if value is None:
                return []
            if not isinstance(value, list):
                self._record_recovery(
                    key, "ignored_corrupt_data", "agent analysis must be a list"
                )
                return []
            result: List[RecommendationAnalysis] = []
            for item in value:
                if not isinstance(item, Mapping) or str(
                    item.get("record_type") or ""
                ) != "recommendation_analysis":
                    continue
                try:
                    record = RecommendationAnalysis.from_dict(item)
                    if record.profile_id != target:
                        raise ValueError("recommendation analysis profile mismatch")
                    if target_run and record.run_id != target_run:
                        continue
                except (TypeError, ValueError, KeyError) as error:
                    self._record_recovery(key, "ignored_corrupt_item", str(error))
                    continue
                result.append(record)
            return result

    def save_board_with_recommendation_analyses(
        self,
        board: RecommendationBoard,
        analyses: Iterable[RecommendationAnalysis],
        *,
        limit: int = 500,
        archive: ArchiveFeedback = None,
    ) -> None:
        """原子保存榜单与同轮分析，并可一并替换忽略归档。"""
        if archive is not None and archive.profile_id != board.profile_id:
            raise ValueError("board and archive profile_id mismatch")
        values = list(analyses or ())
        expected = {item.candidate_id: item.analysis_id for item in board.recommendations}
        actual: Dict[str, str] = {}
        for analysis in values:
            if not isinstance(analysis, RecommendationAnalysis):
                raise TypeError("analyses must contain RecommendationAnalysis")
            if analysis.profile_id != board.profile_id or analysis.run_id != board.run_id:
                raise ValueError("board and recommendation analysis scope mismatch")
            actual[analysis.candidate_id] = analysis.analysis_id
        if (
            actual != expected
            or len(actual) != len(values)
            or len(expected) != len(board.recommendations)
        ):
            raise ValueError("board recommendation analyses are incomplete")
        keep_limit = max(len(values), min(max(1, int(limit)), 100000))
        board_key = self._profile_key("recommendation_board", board.profile_id)
        analysis_key = self._learning_key("agent_analysis", board.profile_id)
        with self._board_archive_lock, self._feedback_lock(board.profile_id):
            raw = self._plugin.get_data(key=analysis_key)
            if raw is None:
                items: List[Any] = []
            elif isinstance(raw, list):
                items = list(raw)
            else:
                self._record_recovery(
                    analysis_key,
                    "ignored_corrupt_data",
                    "agent analysis must be a list",
                )
                raise ValueError("agent analysis data is corrupt")
            replacement_ids = {analysis.analysis_id for analysis in values}
            retained = [
                item
                for item in items
                if not (
                    isinstance(item, Mapping)
                    and str(item.get("record_type") or "")
                    == "recommendation_analysis"
                    and str(item.get("analysis_id") or "") in replacement_ids
                )
            ]
            retained.extend(analysis.to_dict() for analysis in values)
            updates = {
                board_key: board.to_dict(),
                analysis_key: retained[-keep_limit:],
                self._board_history_key(board.profile_id): self._board_history_after_save(
                    board
                ),
            }
            if archive is not None:
                updates[self._profile_key("archive", board.profile_id)] = (
                    archive.to_dict()
                )
            self._atomic_raw_update(
                updates=updates,
                recovery_key=analysis_key,
                action="recommendation_analysis_write_failed",
            )

    def revise_recommendation_analysis(
        self,
        *,
        profile_id: str,
        candidate_id: str,
        run_id: str,
        source_analysis_id: str,
        revision_analysis_id: str,
        revision_event_id: str,
        revised_reason: str,
        correction_note: str,
        prompt_fingerprint: str,
        created_at: str,
        limit: int = 500,
    ) -> RecommendationAnalysis:
        """原子追加分析修订并在仍可见时切换榜单分析指针。"""
        target = str(profile_id or "").strip()
        candidate = str(candidate_id or "").strip()
        target_run = str(run_id or "").strip()
        source_id = str(source_analysis_id or "").strip()
        revision_id = str(revision_analysis_id or "").strip()
        event_id = str(revision_event_id or "").strip()
        reason = " ".join(str(revised_reason or "").split()).strip()
        note = " ".join(str(correction_note or "").split()).strip()
        fingerprint = str(prompt_fingerprint or "").strip()
        timestamp = str(created_at or "").strip()
        if not all(
            (
                target,
                candidate,
                target_run,
                source_id,
                revision_id,
                event_id,
                reason,
                note,
                fingerprint,
                timestamp,
            )
        ):
            raise ValueError("recommendation analysis revision is incomplete")
        if source_id == revision_id or len(reason) > 30 or len(note) > 240:
            raise ValueError("recommendation analysis revision is invalid")
        board_key = self._profile_key("recommendation_board", target)
        analysis_key = self._learning_key("agent_analysis", target)
        keep_limit = max(1, min(int(limit), 100000))

        with self.feedback_action_guard(target):
            board = self.load_board(target)
            raw = self._plugin.get_data(key=analysis_key)
            if raw is None:
                items: List[Any] = []
            elif isinstance(raw, list):
                items = list(raw)
            else:
                self._record_recovery(
                    analysis_key,
                    "ignored_corrupt_data",
                    "agent analysis must be a list",
                )
                raise ValueError("agent analysis data is corrupt")

            analyses: List[RecommendationAnalysis] = []
            by_id: Dict[str, RecommendationAnalysis] = {}
            for item in items:
                if not isinstance(item, Mapping) or str(
                    item.get("record_type") or ""
                ) != "recommendation_analysis":
                    continue
                try:
                    analysis = RecommendationAnalysis.from_dict(item)
                except (TypeError, ValueError, KeyError) as error:
                    self._record_recovery(
                        analysis_key, "ignored_corrupt_item", str(error)
                    )
                    continue
                if analysis.profile_id != target:
                    raise ValueError("recommendation analysis profile mismatch")
                analyses.append(analysis)
                by_id[analysis.analysis_id] = analysis

            existing = by_id.get(revision_id)
            if existing is not None:
                if (
                    existing.candidate_id != candidate
                    or existing.run_id != target_run
                    or existing.reason != reason
                    or existing.prompt_fingerprint != fingerprint
                    or note not in existing.uncertainties
                ):
                    raise ValueError("analysis revision identity conflict")
                return existing

            source = by_id.get(source_id)
            if (
                source is None
                or source.candidate_id != candidate
                or source.run_id != target_run
            ):
                raise ValueError("analysis revision source is unavailable")

            def descends_from(analysis_id: str, ancestor_id: str) -> bool:
                """判断分析版本是否位于指定祖先的 supersedes 链上。"""
                current_id = str(analysis_id or "")
                seen = set()
                while current_id and current_id not in seen:
                    if current_id == ancestor_id:
                        return True
                    seen.add(current_id)
                    current = by_id.get(current_id)
                    current_id = current.supersedes if current is not None else ""
                return False

            board_item = None
            if board is not None and board.run_id == target_run:
                board_item = next(
                    (
                        item
                        for item in board.recommendations
                        if item.candidate_id == candidate
                        and descends_from(item.analysis_id, source_id)
                    ),
                    None,
                )
            current = by_id.get(board_item.analysis_id) if board_item is not None else None
            if current is None:
                current = next(
                    (
                        item
                        for item in reversed(analyses)
                        if item.candidate_id == candidate
                        and item.run_id == target_run
                        and item.status == "active"
                        and descends_from(item.analysis_id, source_id)
                    ),
                    None,
                )
            current = current or source
            if not descends_from(current.analysis_id, source_id):
                raise ValueError("analysis revision source is outside current lineage")

            uncertainties = list(current.uncertainties)
            if note not in uncertainties:
                uncertainties.append(note)
            replacement = replace(
                current,
                analysis_id=revision_id,
                reason=reason,
                uncertainties=uncertainties,
                prompt_fingerprint=fingerprint,
                supersedes=current.analysis_id,
                status="active",
                created_at=timestamp,
            )
            superseded = replace(current, status="superseded")
            transformed: List[Any] = []
            for item in items:
                if (
                    isinstance(item, Mapping)
                    and str(item.get("record_type") or "")
                    == "recommendation_analysis"
                    and str(item.get("analysis_id") or "") == current.analysis_id
                ):
                    transformed.append(superseded.to_dict())
                else:
                    transformed.append(item)
            transformed.append(replacement.to_dict())

            board_changed = (
                board_item is not None
                and board_item.analysis_id == current.analysis_id
            )
            if board_changed:
                board_item.analysis_id = replacement.analysis_id
                board_item.reason = replacement.reason
                board.revision += 1

            retained = self._retain_agent_analysis_items(
                target,
                transformed,
                keep_limit,
                mandatory_analysis_ids=(
                    source_id,
                    current.analysis_id,
                    replacement.analysis_id,
                ),
                mandatory_event_ids=(event_id,),
            )
            updates = {analysis_key: retained}
            if board_changed:
                updates[board_key] = board.to_dict()
            self._atomic_raw_update(
                updates=updates,
                recovery_key=analysis_key,
                action="recommendation_analysis_revision_failed",
            )
            return replacement

    def load_feedback_understanding(
        self, profile_id: str, event_id: str
    ) -> Optional[FeedbackUnderstandingRecord]:
        """按事件身份读取已有反馈理解，供重复消费幂等复用。"""
        target_event = str(event_id or "").strip()
        if not target_event:
            raise ValueError("event_id is required")
        return next(
            (
                item
                for item in self.load_feedback_understandings(profile_id)
                if item.event_id == target_event
            ),
            None,
        )

    def append_feedback_understanding(
        self,
        record: FeedbackUnderstandingRecord,
        *,
        limit: int = 500,
        mandatory_analysis_ids: Iterable[str] = (),
    ) -> FeedbackUnderstandingRecord:
        """按 event_id 幂等追加结构化理解并执行有界保留。"""
        if not isinstance(record, FeedbackUnderstandingRecord):
            raise TypeError("record must be FeedbackUnderstandingRecord")
        keep_limit = max(1, min(int(limit), 100000))
        key = self._learning_key("agent_analysis", record.profile_id)
        with self._feedback_lock(record.profile_id):
            value = self._plugin.get_data(key=key)
            if value is None:
                items: List[Any] = []
            elif isinstance(value, list):
                items = list(value)
            else:
                self._record_recovery(
                    key, "ignored_corrupt_data", "agent analysis must be a list"
                )
                raise ValueError("agent analysis data is corrupt")
            for item in items:
                if not isinstance(item, Mapping):
                    continue
                if str(item.get("record_type") or "") != "feedback_understanding":
                    continue
                if str(item.get("event_id") or "") != record.event_id:
                    continue
                existing = FeedbackUnderstandingRecord.from_dict(item)
                if existing.profile_id != record.profile_id:
                    raise ValueError("feedback understanding profile mismatch")
                return existing
            items.append(record.to_dict())
            retained = self._retain_agent_analysis_items(
                record.profile_id,
                items,
                keep_limit,
                mandatory_analysis_ids=mandatory_analysis_ids,
                mandatory_event_ids=(record.event_id,),
            )
            self._atomic_raw_update(
                updates={key: retained},
                recovery_key=key,
                action="feedback_understanding_write_failed",
            )
            return record

    def load_memory_proposals(self, profile_id: str) -> List[MemoryProposal]:
        """读取按 profile 隔离的有界待确认记忆提案。"""
        target = str(profile_id or "").strip()
        self._scope(target, "profile_id")
        key = self._learning_key("memory_proposals", target)
        with self._feedback_lock(target):
            value = self._plugin.get_data(key=key)
            if value is None:
                return []
            if not isinstance(value, list):
                self._record_recovery(
                    key, "ignored_corrupt_data", "memory proposals must be a list"
                )
                return []
            result: List[MemoryProposal] = []
            for item in value:
                if not isinstance(item, Mapping) or str(
                    item.get("record_type") or ""
                ) != "memory_proposal":
                    continue
                try:
                    proposal = MemoryProposal.from_dict(item)
                    if proposal.profile_id != target:
                        raise ValueError("memory proposal profile mismatch")
                except (TypeError, ValueError, KeyError) as error:
                    self._record_recovery(
                        key, "ignored_corrupt_item", str(error)
                    )
                    continue
                result.append(proposal)
            return sorted(
                result, key=lambda item: (item.event_sequence, item.proposal_id)
            )

    def load_memory_proposal(
        self, profile_id: str, event_id: str
    ) -> Optional[MemoryProposal]:
        """按来源事件读取已有记忆提案。"""
        target_event = str(event_id or "").strip()
        if not target_event:
            raise ValueError("event_id is required")
        return next(
            (
                item
                for item in self.load_memory_proposals(profile_id)
                if item.event_id == target_event
            ),
            None,
        )

    def get_memory_proposal(
        self, profile_id: str, proposal_id: str
    ) -> Optional[MemoryProposal]:
        """按提案身份读取指定 profile 的记忆提案。"""
        target_id = str(proposal_id or "").strip()
        if not target_id:
            raise ValueError("proposal_id is required")
        return next(
            (
                item
                for item in self.load_memory_proposals(profile_id)
                if item.proposal_id == target_id
            ),
            None,
        )

    def append_memory_proposal(
        self, proposal: MemoryProposal, *, limit: int = 500
    ) -> MemoryProposal:
        """按 event_id 幂等追加待确认记忆提案并执行有界保留。"""
        if not isinstance(proposal, MemoryProposal):
            raise TypeError("proposal must be MemoryProposal")
        keep_limit = max(1, min(int(limit), 100000))
        key = self._learning_key("memory_proposals", proposal.profile_id)
        with self._feedback_lock(proposal.profile_id):
            value = self._plugin.get_data(key=key)
            if value is None:
                items: List[Any] = []
            elif isinstance(value, list):
                items = list(value)
            else:
                self._record_recovery(
                    key, "ignored_corrupt_data", "memory proposals must be a list"
                )
                raise ValueError("memory proposal data is corrupt")
            for item in items:
                if not isinstance(item, Mapping) or str(
                    item.get("record_type") or ""
                ) != "memory_proposal":
                    continue
                if str(item.get("event_id") or "") != proposal.event_id:
                    continue
                existing = MemoryProposal.from_dict(item)
                if existing.profile_id != proposal.profile_id:
                    raise ValueError("memory proposal profile mismatch")
                return existing
            items.append(proposal.to_dict())
            retained = self._retain_pending_records(
                items, keep_limit, {"pending_confirmation"}
            )
            self._atomic_raw_update(
                updates={key: retained},
                recovery_key=key,
                action="memory_proposal_write_failed",
            )
            return proposal

    def replace_memory_proposal(
        self, proposal: MemoryProposal, *, expected_status: str
    ) -> bool:
        """仅在当前状态匹配时原位替换记忆提案。"""
        if not isinstance(proposal, MemoryProposal):
            raise TypeError("proposal must be MemoryProposal")
        expected = str(expected_status or "").strip()
        if not expected:
            raise ValueError("expected_status is required")
        key = self._learning_key("memory_proposals", proposal.profile_id)
        with self._feedback_lock(proposal.profile_id):
            value = self._plugin.get_data(key=key)
            if not isinstance(value, list):
                return False
            updated = list(value)
            for index, item in enumerate(updated):
                if not isinstance(item, Mapping) or str(
                    item.get("record_type") or ""
                ) != "memory_proposal":
                    continue
                if str(item.get("proposal_id") or "") != proposal.proposal_id:
                    continue
                current = MemoryProposal.from_dict(item)
                if current.profile_id != proposal.profile_id:
                    raise ValueError("memory proposal profile mismatch")
                if current.status != expected:
                    return False
                updated[index] = proposal.to_dict()
                self._atomic_raw_update(
                    updates={key: updated},
                    recovery_key=key,
                    action="memory_proposal_replace_failed",
                )
                return True
            return False

    def project_memory_proposal(
        self,
        proposal: MemoryProposal,
        items: List[PreferenceMemoryItem],
        *,
        confirmed_by_mp_user_id: str,
        resolved_at: str,
    ) -> Tuple[MemoryProjectionResult, MemoryProposal]:
        """原子投影确认记忆并把提案更新为确认或被替代状态。"""
        if not isinstance(proposal, MemoryProposal):
            raise TypeError("proposal must be MemoryProposal")
        proposed = list(items or [])
        if not proposed or any(
            not isinstance(item, PreferenceMemoryItem) for item in proposed
        ):
            raise TypeError("items must contain preference memory items")
        actor = str(confirmed_by_mp_user_id or "").strip()
        if not actor or len(actor) > 128:
            raise ValueError("confirmed_by_mp_user_id is invalid")
        proposal_key = self._learning_key(
            "memory_proposals", proposal.profile_id
        )
        memory_key = self._profile_key(
            "preference_memory", proposal.profile_id
        )
        with self._feedback_lock(proposal.profile_id):
            raw_proposals = self._plugin.get_data(key=proposal_key)
            if not isinstance(raw_proposals, list):
                raise ValueError("memory proposal data is corrupt")
            stored_index = None
            current = None
            for index, raw in enumerate(raw_proposals):
                if not isinstance(raw, Mapping) or str(
                    raw.get("record_type") or ""
                ) != "memory_proposal":
                    continue
                if str(raw.get("proposal_id") or "") != proposal.proposal_id:
                    continue
                stored_index = index
                current = MemoryProposal.from_dict(raw)
                break
            if stored_index is None or current is None:
                raise ValueError("memory proposal is unavailable")
            if current.profile_id != proposal.profile_id:
                raise ValueError("memory proposal profile mismatch")
            if current != proposal:
                raise ValueError("memory proposal changed before projection")
            if current.status != "pending_confirmation":
                raise ValueError("memory proposal is already resolved")

            memory = self._load_preference_memory(
                proposal.profile_id, strict=True
            )
            result = memory.project(
                proposed,
                expected_revision=current.expected_memory_revision,
                source_event_sequence=current.event_sequence,
            )
            if result.applied:
                updated_proposal = replace(
                    current,
                    status="confirmed",
                    reminder_policy="unselected",
                    next_remind_at="",
                    resolved_at=resolved_at,
                    resolved_by_mp_user_id=actor,
                    resolved_memory_revision=result.actual_revision,
                    projected_memory_item_ids=tuple(
                        item.item_id for item in proposed
                    ),
                    resolution_reason="",
                )
            else:
                updated_proposal = replace(
                    current,
                    status="superseded",
                    reminder_policy="unselected",
                    next_remind_at="",
                    resolved_at=resolved_at,
                    resolved_by_mp_user_id=actor,
                    resolved_memory_revision=result.actual_revision,
                    projected_memory_item_ids=(),
                    resolution_reason=result.reason,
                )
            updated_proposals = list(raw_proposals)
            updated_proposals[stored_index] = updated_proposal.to_dict()
            updates = {proposal_key: updated_proposals}
            if result.applied:
                updates = {
                    memory_key: result.memory.to_dict(),
                    proposal_key: updated_proposals,
                }
            self._atomic_raw_update(
                updates=updates,
                recovery_key=proposal_key,
                action="memory_proposal_projection_failed",
            )
            stored_proposal = self.get_memory_proposal(
                proposal.profile_id, proposal.proposal_id
            )
            if stored_proposal != updated_proposal:
                raise ValueError("memory proposal projection readback mismatch")
            if result.applied and self._load_preference_memory(
                proposal.profile_id, strict=True
            ) != result.memory:
                raise ValueError("preference memory projection readback mismatch")
            return result, updated_proposal

    def load_pending_questions(self, profile_id: str) -> List[PendingQuestion]:
        """读取按 profile 隔离的有界待回答问题。"""
        target = str(profile_id or "").strip()
        self._scope(target, "profile_id")
        key = self._learning_key("pending_questions", target)
        with self._feedback_lock(target):
            value = self._plugin.get_data(key=key)
            if value is None:
                return []
            if not isinstance(value, list):
                self._record_recovery(
                    key, "ignored_corrupt_data", "pending questions must be a list"
                )
                return []
            result: List[PendingQuestion] = []
            for item in value:
                if not isinstance(item, Mapping) or str(
                    item.get("record_type") or ""
                ) != "pending_question":
                    continue
                try:
                    question = PendingQuestion.from_dict(item)
                    if question.profile_id != target:
                        raise ValueError("pending question profile mismatch")
                except (TypeError, ValueError, KeyError) as error:
                    self._record_recovery(
                        key, "ignored_corrupt_item", str(error)
                    )
                    continue
                result.append(question)
            return sorted(
                result, key=lambda item: (item.event_sequence, item.question_id)
            )

    def load_pending_question(
        self, profile_id: str, event_id: str
    ) -> Optional[PendingQuestion]:
        """按来源事件读取已有待回答问题。"""
        target_event = str(event_id or "").strip()
        if not target_event:
            raise ValueError("event_id is required")
        return next(
            (
                item
                for item in self.load_pending_questions(profile_id)
                if item.event_id == target_event
            ),
            None,
        )

    def get_pending_question(
        self, profile_id: str, question_id: str
    ) -> Optional[PendingQuestion]:
        """按问题身份读取指定 profile 的待回答问询。"""
        target_id = str(question_id or "").strip()
        if not target_id:
            raise ValueError("question_id is required")
        return next(
            (
                item
                for item in self.load_pending_questions(profile_id)
                if item.question_id == target_id
            ),
            None,
        )

    def append_pending_question(
        self, question: PendingQuestion, *, limit: int = 500
    ) -> PendingQuestion:
        """按 event_id 幂等追加待回答问题并执行有界保留。"""
        if not isinstance(question, PendingQuestion):
            raise TypeError("question must be PendingQuestion")
        keep_limit = max(1, min(int(limit), 100000))
        key = self._learning_key("pending_questions", question.profile_id)
        with self._feedback_lock(question.profile_id):
            value = self._plugin.get_data(key=key)
            if value is None:
                items: List[Any] = []
            elif isinstance(value, list):
                items = list(value)
            else:
                self._record_recovery(
                    key, "ignored_corrupt_data", "pending questions must be a list"
                )
                raise ValueError("pending question data is corrupt")
            for item in items:
                if not isinstance(item, Mapping) or str(
                    item.get("record_type") or ""
                ) != "pending_question":
                    continue
                if str(item.get("event_id") or "") != question.event_id:
                    continue
                existing = PendingQuestion.from_dict(item)
                if existing.profile_id != question.profile_id:
                    raise ValueError("pending question profile mismatch")
                return existing
            items.append(question.to_dict())
            retained = self._retain_pending_records(items, keep_limit, {"pending"})
            self._atomic_raw_update(
                updates={key: retained},
                recovery_key=key,
                action="pending_question_write_failed",
            )
            return question

    def replace_pending_question(
        self, question: PendingQuestion, *, expected_status: str
    ) -> bool:
        """仅在当前状态匹配时原位替换待回答问题。"""
        if not isinstance(question, PendingQuestion):
            raise TypeError("question must be PendingQuestion")
        expected = str(expected_status or "").strip()
        if not expected:
            raise ValueError("expected_status is required")
        key = self._learning_key("pending_questions", question.profile_id)
        with self._feedback_lock(question.profile_id):
            value = self._plugin.get_data(key=key)
            if not isinstance(value, list):
                return False
            updated = list(value)
            for index, item in enumerate(updated):
                if not isinstance(item, Mapping) or str(
                    item.get("record_type") or ""
                ) != "pending_question":
                    continue
                if str(item.get("question_id") or "") != question.question_id:
                    continue
                current = PendingQuestion.from_dict(item)
                if current.profile_id != question.profile_id:
                    raise ValueError("pending question profile mismatch")
                if current.status != expected:
                    return False
                updated[index] = question.to_dict()
                self._atomic_raw_update(
                    updates={key: updated},
                    recovery_key=key,
                    action="pending_question_replace_failed",
                )
                return True
            return False

    def append_run(self, run: RecommendationRun) -> None:
        """把运行记录写入对应用户历史头部并执行上限裁剪。"""
        key = self._profile_key("run_history", run.profile_id)
        raw_history = self._plugin.get_data(key=key)
        history = list(raw_history) if isinstance(raw_history, list) else []
        history.insert(0, run.to_dict())
        self._plugin.save_data(key=key, value=history[: self._history_limit])

    def load_run_history(self, profile_id: str) -> List[RecommendationRun]:
        """容错读取当前用户的有界运行历史。"""
        key = self._profile_key("run_history", profile_id)
        value = self._plugin.get_data(key=key)
        if value is None:
            return []
        if not isinstance(value, list):
            self._record_recovery(key, "ignored_corrupt_data", "history must be a list")
            return []
        result: List[RecommendationRun] = []
        for item in value[: self._history_limit]:
            try:
                run = RecommendationRun.from_dict(item)
            except (TypeError, ValueError, KeyError) as error:
                self._record_recovery(key, "ignored_corrupt_item", str(error))
                continue
            if run.profile_id == profile_id:
                result.append(run)
            else:
                self._record_recovery(key, "ignored_cross_profile_item", run.profile_id)
        return result

    def save_telegram_session(self, session: TelegramSelectionSession) -> None:
        """保存一个 Telegram 选择会话并裁剪过期记录。"""
        raw = self._plugin.get_data(key=self.telegram_sessions_key)
        sessions = dict(raw) if isinstance(raw, Mapping) else {}
        retained: Dict[str, Any] = {}
        for token, value in sessions.items():
            try:
                current = TelegramSelectionSession.from_dict(value)
            except (TypeError, ValueError, KeyError):
                continue
            if not current.is_expired() or current.status == "processing":
                retained[str(token)] = current.to_dict()
        retained[session.token] = session.to_dict()
        self._plugin.save_data(key=self.telegram_sessions_key, value=retained)

    def load_telegram_session(self, token: str) -> Optional[TelegramSelectionSession]:
        """按不可猜令牌读取 Telegram 选择会话。"""
        raw = self._plugin.get_data(key=self.telegram_sessions_key)
        if not isinstance(raw, Mapping):
            return None
        value = raw.get(str(token or "").strip())
        if value is None:
            return None
        try:
            return TelegramSelectionSession.from_dict(value)
        except (TypeError, ValueError, KeyError) as error:
            self._record_recovery(
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

    def _plugin_data_entries(self) -> List[Tuple[str, Any]]:
        """读取宿主全部插件数据行，兼容模型对象和测试字典。"""
        try:
            raw = self._plugin.get_data()
        except (TypeError, AttributeError):
            return []
        if isinstance(raw, Mapping):
            return [(str(key), value) for key, value in raw.items()]
        entries: List[Tuple[str, Any]] = []
        for record in raw or ():
            if isinstance(record, Mapping):
                key = record.get("key")
                value = record.get("value")
            else:
                key = getattr(record, "key", None)
                value = getattr(record, "value", None)
            if key not in (None, ""):
                entries.append((str(key), value))
        return entries

    def _pending_session_from_value(
        self, value: Any, recovery_key: str
    ) -> Optional[TelegramPendingSession]:
        """恢复单条 Telegram 待办会话，损坏数据记入恢复日志。"""
        try:
            return TelegramPendingSession.from_dict(value)
        except (TypeError, ValueError, KeyError) as error:
            self._record_recovery(
                recovery_key,
                "ignored_corrupt_item",
                str(error),
            )
            return None

    @staticmethod
    def _pending_session_score(session: TelegramPendingSession) -> Tuple[int, ...]:
        """为重复会话选择消息身份更完整且仍可重试的记录。"""
        return (
            int(bool(session.message_id)),
            int(bool(session.chat_id)),
            int(bool(session.source)),
            int(session.status == "open"),
        )

    def _load_telegram_pending_session_map(
        self, *, migrate_legacy: bool = True
    ) -> Dict[str, TelegramPendingSession]:
        """合并独立会话和全部旧共享记录，并按需完成原地迁移。"""
        sessions: Dict[str, TelegramPendingSession] = {}
        dedicated_tokens = set()
        legacy_found = False
        entries = self._plugin_data_entries()
        if not any(key == self.telegram_pending_sessions_key for key, _ in entries):
            legacy = self._plugin.get_data(key=self.telegram_pending_sessions_key)
            if isinstance(legacy, Mapping):
                entries.append((self.telegram_pending_sessions_key, legacy))

        def retain(candidate: TelegramPendingSession, *, dedicated: bool) -> None:
            """按完整度与独立存储优先级保留同令牌的最佳会话。"""
            current = sessions.get(candidate.token)
            current_dedicated = candidate.token in dedicated_tokens
            selected = current is None or (
                self._pending_session_score(candidate), int(dedicated)
            ) > (
                self._pending_session_score(current), int(current_dedicated)
            )
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
                self._plugin.save_data(
                    key=self._telegram_pending_session_key(session.token),
                    value=session.to_dict(),
                )
            self._plugin.del_data(key=self.telegram_pending_sessions_key)
        return sessions

    def save_telegram_pending_session(
        self, session: TelegramPendingSession
    ) -> None:
        """以独立数据键保存 Telegram 待确认会话并裁剪过期记录。"""
        if not isinstance(session, TelegramPendingSession):
            raise TypeError("session must be TelegramPendingSession")
        with self._telegram_pending_lock:
            sessions = self._load_telegram_pending_session_map()
            for current in sessions.values():
                if current.token != session.token and current.is_expired():
                    self._plugin.del_data(
                        key=self._telegram_pending_session_key(current.token)
                    )
            self._plugin.save_data(
                key=self._telegram_pending_session_key(session.token),
                value=session.to_dict(),
            )

    def load_telegram_pending_session(
        self, token: str
    ) -> Optional[TelegramPendingSession]:
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
            self._plugin.del_data(key=self._telegram_pending_session_key(target))
            return True

    def load_telegram_pending_sessions(
        self,
        profile_id: str,
        item_type: str,
        item_id: str,
        *,
        status: str = "open",
    ) -> List[TelegramPendingSession]:
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
    ) -> List[TelegramPendingSession]:
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

    def annotate_run(
        self,
        profile_id: str,
        run_id: str,
        status: str,
        metrics: Dict[str, Any] = None,
        errors: List[str] = None,
    ) -> bool:
        """更新指定运行记录的状态与后处理证据。"""
        key = self._profile_key("run_history", profile_id)
        value = self._plugin.get_data(key=key)
        if not isinstance(value, list):
            return False
        changed = False
        updated: List[Any] = []
        for item in value:
            if (
                not changed
                and isinstance(item, Mapping)
                and str(item.get("profile_id") or "") == profile_id
                and str(item.get("run_id") or "") == run_id
            ):
                current = dict(item)
                current["status"] = status
                current_metrics = dict(current.get("metrics") or {})
                current_metrics.update(metrics or {})
                current["metrics"] = current_metrics
                current_errors = [str(error) for error in current.get("errors") or []]
                current_errors.extend(str(error) for error in errors or [])
                current["errors"] = current_errors
                updated.append(current)
                changed = True
            else:
                updated.append(item)
        if changed:
            self._plugin.save_data(key=key, value=updated[: self._history_limit])
        return changed

    @staticmethod
    def _raw_run_ids(value: Any) -> List[str]:
        """从已知榜单或运行历史载荷中提取非空 run_id。"""
        items = value if isinstance(value, list) else [value]
        result: List[str] = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            for field_name in ("previous_run_id", "run_id"):
                run_id = str(item.get(field_name) or "").strip()
                if run_id and run_id not in result:
                    result.append(run_id)
        return result

    def _feedback_segment_keys_from_raw(self, profile_id: str) -> List[str]:
        """从原始索引安全提取反馈段键，供显式重置损坏账本。"""
        raw = self._plugin.get_data(key=self._feedback_index_key(profile_id))
        if not isinstance(raw, Mapping):
            return []
        result: List[str] = []
        for item in raw.get("segments") or []:
            if not isinstance(item, Mapping):
                continue
            try:
                segment_id = int(item.get("segment_id") or 0)
            except (TypeError, ValueError):
                continue
            if segment_id > 0:
                result.append(self._feedback_segment_key(profile_id, segment_id))
        return list(dict.fromkeys(result))

    def _candidate_keys_from_raw(self, profile_id: str) -> List[str]:
        """从候选索引、榜单和历史提取可达快照键。"""
        run_ids: List[str] = []
        raw_index = self._plugin.get_data(key=self._candidate_index_key(profile_id))
        if isinstance(raw_index, Mapping):
            for item in raw_index.get("snapshots") or []:
                if not isinstance(item, Mapping):
                    continue
                run_id = str(item.get("run_id") or "").strip()
                if run_id and run_id not in run_ids:
                    run_ids.append(run_id)
        for prefix in ("run_history", "recommendation_board", self.board_history_prefix):
            value = self._plugin.get_data(key=self._profile_key(prefix, profile_id))
            for run_id in self._raw_run_ids(value):
                if run_id not in run_ids:
                    run_ids.append(run_id)
        return [self._candidate_key(run_id, profile_id) for run_id in run_ids]

    def learning_storage_keys(self, profile_id: str) -> List[str]:
        """列出仅学习重置覆盖的当前与预留 profile 键。"""
        return list(
            dict.fromkeys(
                [
                    self._feedback_index_key(profile_id),
                    self._profile_key("preference_memory", profile_id),
                    *self._feedback_segment_keys_from_raw(profile_id),
                    *[
                        self._learning_key(prefix, profile_id)
                        for prefix in self.learning_profile_prefixes
                    ],
                ]
            )
        )

    def full_profile_storage_keys(self, profile_id: str) -> List[str]:
        """列出 AgentRank 自有 profile 数据，不包含宿主订阅或媒体库。"""
        fixed_prefixes = (
            "profile_snapshot",
            "recommendation_board",
            self.board_history_prefix,
            "archive",
            "profile_preferences",
            self.playback_snapshot_prefix,
            "run_history",
            self.candidate_snapshot_index_prefix,
            "feedback_event_index",
            "preference_memory",
        )
        return list(
            dict.fromkeys(
                [
                    *[self._profile_key(prefix, profile_id) for prefix in fixed_prefixes],
                    *self._candidate_keys_from_raw(profile_id),
                    *self._feedback_segment_keys_from_raw(profile_id),
                    *[
                        self._learning_key(prefix, profile_id)
                        for prefix in self.learning_profile_prefixes
                    ],
                    self._confirmation_key(profile_id),
                ]
            )
        )

    def reset_learning_data(self, profile_id: str) -> List[str]:
        """清空学习事实和确认记忆，保留画像、榜单、归档与人工偏好。"""
        with self._feedback_lock(profile_id):
            keys = self.learning_storage_keys(profile_id)
            index_key = self._feedback_index_key(profile_id)
            memory_key = self._profile_key("preference_memory", profile_id)
            updates = {
                index_key: FeedbackLedgerIndex.empty(profile_id).to_dict(),
                memory_key: PreferenceMemory.empty(profile_id).to_dict(),
            }
            pending_keys = [
                self._telegram_pending_session_key(session.token)
                for session in self.load_all_telegram_pending_sessions(status="")
                if session.profile_id == str(profile_id)
            ]
            delete_keys = [
                key for key in [*keys, *pending_keys] if key not in updates
            ]
            self._atomic_raw_update(
                updates=updates,
                delete_keys=delete_keys,
                recovery_key=index_key,
                action="learning_reset_failed",
            )
            return [*delete_keys, *updates]

    def reset_all_profile_data(self, profile_id: str) -> List[str]:
        """删除 AgentRank 自有 profile 数据，并保留插件配置和宿主数据。"""
        with self._board_archive_lock, self._feedback_lock(profile_id):
            keys = self.full_profile_storage_keys(profile_id)
            updates: Dict[str, Any] = {}
            raw_sessions = self._plugin.get_data(key=self.telegram_sessions_key)
            if isinstance(raw_sessions, Mapping):
                retained_sessions = {
                    str(token): value
                    for token, value in raw_sessions.items()
                    if not isinstance(value, Mapping)
                    or str(value.get("profile_id") or "") != str(profile_id)
                }
                if retained_sessions != dict(raw_sessions):
                    updates[self.telegram_sessions_key] = retained_sessions
            pending_keys = [
                self._telegram_pending_session_key(session.token)
                for session in self.load_all_telegram_pending_sessions(status="")
                if session.profile_id == str(profile_id)
            ]
            keys = list(dict.fromkeys([*keys, *pending_keys]))
            self._atomic_raw_update(
                updates=updates,
                delete_keys=keys,
                recovery_key=self._profile_key("full_reset", profile_id),
                action="full_reset_failed",
            )
            return keys

    def save_reset_confirmation(
        self, profile_id: str, value: Mapping[str, Any]
    ) -> None:
        """保存不含明文令牌的彻底重置确认记录。"""
        record = dict(value or {})
        required = {"token_hash", "requester_id", "issued_at", "expires_at"}
        if not required.issubset(record) or any(not str(record[key]) for key in required):
            raise ValueError("reset confirmation record is incomplete")
        if "token" in record or "authorization" in record or "cookie" in record:
            raise ValueError("reset confirmation record contains plaintext secrets")
        key = self._confirmation_key(profile_id)
        with self._feedback_lock(profile_id):
            self._atomic_raw_update(
                updates={key: record},
                recovery_key=key,
                action="reset_confirmation_write_failed",
            )

    def load_reset_confirmation(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """读取彻底重置确认记录；无效载荷按不存在处理。"""
        value = self._plugin.get_data(key=self._confirmation_key(profile_id))
        if not isinstance(value, Mapping):
            return None
        required = {"token_hash", "requester_id", "issued_at", "expires_at"}
        if not required.issubset(value):
            return None
        return {str(key): item for key, item in value.items()}

    def delete_reset_confirmation(self, profile_id: str) -> None:
        """删除一次性确认记录。"""
        self._plugin.del_data(key=self._confirmation_key(profile_id))

    def delete_profile(self, profile_id: str) -> None:
        """删除当前用户画像，不触碰其他用户或 MoviePilot 订阅。"""
        self._plugin.del_data(key=self._profile_key("profile_snapshot", profile_id))

    def delete_board(self, profile_id: str) -> None:
        """删除当前用户榜单，不触碰归档和运行历史。"""
        self._plugin.del_data(key=self._profile_key("recommendation_board", profile_id))

    def _restore_raw(self, key: str, value: Any) -> None:
        """在复合写入失败后恢复单个键的原始值。"""
        if value is None:
            self._plugin.del_data(key=key)
        else:
            self._plugin.save_data(key=key, value=value)

    def save_board_and_archive(
        self, board: RecommendationBoard, archive: ArchiveFeedback
    ) -> None:
        """原子替换同一用户的榜单和归档，失败时恢复两者。"""
        if board.profile_id != archive.profile_id:
            raise ValueError("board and archive profile_id mismatch")
        board_key = self._profile_key("recommendation_board", board.profile_id)
        archive_key = self._profile_key("archive", archive.profile_id)
        history_key = self._board_history_key(board.profile_id)
        with self._board_archive_lock, self._feedback_lock(board.profile_id):
            self._atomic_raw_update(
                updates={
                    board_key: board.to_dict(),
                    archive_key: archive.to_dict(),
                    history_key: self._board_history_after_save(board),
                },
                recovery_key=board_key,
                action="board_archive_write_failed",
            )

    def capture_board_archive_raw(self, profile_id: str) -> Dict[str, Any]:
        """捕获榜单和归档原始值，供复合反馈失败时逐字段恢复。"""
        board_key = self._profile_key("recommendation_board", profile_id)
        archive_key = self._profile_key("archive", profile_id)
        return {
            board_key: self._plugin.get_data(key=board_key),
            archive_key: self._plugin.get_data(key=archive_key),
        }

    def restore_board_archive_raw(
        self, profile_id: str, values: Mapping[str, Any]
    ) -> None:
        """原子恢复同一 profile 的榜单和归档原始状态。"""
        expected_keys = {
            self._profile_key("recommendation_board", profile_id),
            self._profile_key("archive", profile_id),
        }
        if set(values) != expected_keys:
            raise ValueError("board archive rollback snapshot is invalid")
        updates = {key: value for key, value in values.items() if value is not None}
        deletes = [key for key, value in values.items() if value is None]
        self._atomic_raw_update(
            updates=updates,
            delete_keys=deletes,
            recovery_key=self._profile_key("feedback_action", profile_id),
            action="feedback_action_board_rollback_failed",
        )

    def capture_feedback_action_raw(self, profile_id: str) -> Dict[str, Any]:
        """捕获反馈动作涉及的榜单、归档和结构化分析原始值。"""
        keys = (
            self._profile_key("recommendation_board", profile_id),
            self._profile_key("archive", profile_id),
            self._board_history_key(profile_id),
            self._learning_key("agent_analysis", profile_id),
        )
        return {key: self._plugin.get_data(key=key) for key in keys}

    def restore_feedback_action_raw(
        self, profile_id: str, values: Mapping[str, Any]
    ) -> None:
        """原子恢复反馈动作涉及的榜单、归档和结构化分析。"""
        expected_keys = {
            self._profile_key("recommendation_board", profile_id),
            self._profile_key("archive", profile_id),
            self._board_history_key(profile_id),
            self._learning_key("agent_analysis", profile_id),
        }
        if set(values) != expected_keys:
            raise ValueError("feedback action rollback snapshot is invalid")
        updates = {key: value for key, value in values.items() if value is not None}
        deletes = [key for key, value in values.items() if value is None]
        self._atomic_raw_update(
            updates=updates,
            delete_keys=deletes,
            recovery_key=self._profile_key("feedback_action", profile_id),
            action="feedback_action_rollback_failed",
        )

    def save_profile_and_board(
        self, profile: UserProfile, board: RecommendationBoard
    ) -> None:
        """原子替换同一用户的画像与榜单，失败时恢复两者。"""
        if profile.profile_id != board.profile_id:
            raise ValueError("profile and board profile_id mismatch")
        profile_key = self._profile_key("profile_snapshot", profile.profile_id)
        board_key = self._profile_key("recommendation_board", board.profile_id)
        history_key = self._board_history_key(board.profile_id)
        with self._board_archive_lock, self._feedback_lock(board.profile_id):
            self._atomic_raw_update(
                updates={
                    profile_key: profile.to_dict(),
                    board_key: board.to_dict(),
                    history_key: self._board_history_after_save(board),
                },
                recovery_key=board_key,
                action="profile_board_write_failed",
            )

    def clear_profile_and_board(self, profile_id: str) -> None:
        """原子删除当前用户画像和榜单，失败时恢复原始数据。"""
        profile_key = self._profile_key("profile_snapshot", profile_id)
        board_key = self._profile_key("recommendation_board", profile_id)
        old_profile = self._plugin.get_data(key=profile_key)
        old_board = self._plugin.get_data(key=board_key)
        try:
            self._plugin.del_data(key=profile_key)
            self._plugin.del_data(key=board_key)
        except Exception:
            self._restore_raw(profile_key, old_profile)
            self._restore_raw(board_key, old_board)
            raise
