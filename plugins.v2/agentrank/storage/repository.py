"""基于 MoviePilot 插件数据接口的稳定画像身份存储仓库。"""

import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Mapping, Optional, Type, TypeVar
from urllib.parse import quote

from ..model.archive import ArchiveFeedback
from ..model.board import RecommendationBoard
from ..model.candidate import Candidate
from ..model.candidate_snapshot import CandidateSnapshot
from ..model.feedback import (
    FeedbackAppendResult,
    FeedbackEvent,
    FeedbackEventSegment,
    FeedbackLedgerIndex,
)
from ..model.memory import (
    MemoryProjectionResult,
    PreferenceMemory,
    PreferenceMemoryItem,
)
from ..model.profile import UserProfile
from ..model.profile_preferences import ProfilePreferences
from ..model.playback import PlaybackSnapshot
from ..model.run import RecommendationRun
from ..model.telegram_selection import TelegramSelectionSession


ModelType = TypeVar("ModelType")


class AgentRankRepository:
    """统一封装 AgentRank 的 profile_id 隔离键与容错读取。"""

    _board_archive_lock = threading.RLock()
    _feedback_locks_guard = threading.Lock()
    _feedback_locks: Dict[str, threading.RLock] = {}
    recovery_log_key = "agentrank_recovery_log"
    telegram_sessions_key = "telegram_selection_sessions"
    playback_snapshot_prefix = "playback_snapshot"

    def __init__(
        self,
        plugin: Any,
        history_limit: int = 50,
        feedback_segment_size: int = 100,
    ):
        """绑定插件数据接口并设置历史与反馈分段上限。"""
        self._plugin = plugin
        self._history_limit = max(1, min(int(history_limit), 200))
        self._feedback_segment_size = max(
            1, min(int(feedback_segment_size), 1000)
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
    def board_archive_guard(self, profile_id: str) -> Iterator[None]:
        """串行化榜单提交与归档反馈，避免读改写竞态。"""
        self._scope(profile_id, "profile_id")
        with self._board_archive_lock:
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

    def save_board(self, board: RecommendationBoard) -> None:
        """保存当前用户榜单。"""
        self._plugin.save_data(
            key=self._profile_key("recommendation_board", board.profile_id),
            value=board.to_dict(),
        )

    def load_board(self, profile_id: str) -> Optional[RecommendationBoard]:
        """读取当前用户榜单；损坏或不存在时返回空。"""
        return self._load_scoped_model(
            self._profile_key("recommendation_board", profile_id),
            RecommendationBoard,
            profile_id,
        )

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

    def save_candidate_snapshot(self, snapshot: CandidateSnapshot) -> None:
        """首次保存候选快照，拒绝覆盖并在写入失败时清除半快照。"""
        if not isinstance(snapshot, CandidateSnapshot):
            raise TypeError("snapshot must be CandidateSnapshot")
        key = self._candidate_key(snapshot.run_id, snapshot.profile_id)
        if self._plugin.get_data(key=key) is not None:
            raise ValueError("candidate snapshot already exists")
        try:
            self._plugin.save_data(key=key, value=snapshot.to_dict())
            stored = self._plugin.get_data(key=key)
            verified = CandidateSnapshot.from_dict(stored)
            if verified.content_hash != snapshot.content_hash:
                raise ValueError("candidate snapshot readback mismatch")
        except Exception:
            self._plugin.del_data(key=key)
            raise

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
        old_board = self._plugin.get_data(key=board_key)
        old_archive = self._plugin.get_data(key=archive_key)
        try:
            self._plugin.save_data(key=board_key, value=board.to_dict())
            self._plugin.save_data(key=archive_key, value=archive.to_dict())
        except Exception:
            self._restore_raw(board_key, old_board)
            self._restore_raw(archive_key, old_archive)
            raise

    def save_profile_and_board(
        self, profile: UserProfile, board: RecommendationBoard
    ) -> None:
        """原子替换同一用户的画像与榜单，失败时恢复两者。"""
        if profile.profile_id != board.profile_id:
            raise ValueError("profile and board profile_id mismatch")
        profile_key = self._profile_key("profile_snapshot", profile.profile_id)
        board_key = self._profile_key("recommendation_board", board.profile_id)
        old_profile = self._plugin.get_data(key=profile_key)
        old_board = self._plugin.get_data(key=board_key)
        try:
            self._plugin.save_data(key=profile_key, value=profile.to_dict())
            self._plugin.save_data(key=board_key, value=board.to_dict())
        except Exception:
            self._restore_raw(profile_key, old_profile)
            self._restore_raw(board_key, old_board)
            raise

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
