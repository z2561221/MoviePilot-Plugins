"""订阅、入库与播放结果的可信单调归因服务。"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from ..model.candidate import Candidate, typed_tmdb_candidate_id
from ..model.outcome import OutcomeAttribution, OUTCOME_STATE_RANK
from ..model.playback import PlaybackSnapshot
from ..storage.repository import AgentRankRepository


@dataclass(frozen=True)
class AttributionVerificationResult:
    """汇总一次 profile 归因复查的可公开结果。"""

    profile_id: str
    checked: int
    advanced: int
    pending: int
    records: Tuple[OutcomeAttribution, ...]

    def to_dict(self) -> Dict[str, Any]:
        """返回不含异常原文和宿主身份的复查摘要。"""
        return {
            "profile_id": self.profile_id,
            "checked": self.checked,
            "advanced": self.advanced,
            "pending": self.pending,
            "records": [item.to_public_dict() for item in self.records],
        }


class OutcomeAttributionService:
    """只根据宿主可复查事实推进推荐结果，不把 UI 返回当业务成功。"""

    def __init__(
        self,
        repository: AgentRankRepository,
        *,
        subscription_adapter: Any,
        library_adapter: Any,
        now_factory: Any = None,
        record_limit: int = 500,
    ):
        """绑定隔离仓储、宿主读取适配器和测试时钟。"""
        if not isinstance(repository, AgentRankRepository):
            raise TypeError("repository must be AgentRankRepository")
        self._repository = repository
        self._subscriptions = subscription_adapter
        self._library = library_adapter
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self._record_limit = max(1, min(int(record_limit), 100000))

    def _now(self) -> str:
        """返回标准 UTC 复查时间。"""
        current = self._now_factory()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _attribution_id(run_id: str, candidate_id: str) -> str:
        """生成不泄漏 profile 身份的稳定运行内归因 ID。"""
        payload = f"{run_id}\x1f{candidate_id}".encode("utf-8")
        return f"outcome-{hashlib.sha256(payload).hexdigest()[:24]}"

    def _candidate_context(
        self, profile_id: str, candidate_id: str
    ) -> Tuple[Any, Candidate]:
        """从当前榜单及其冻结快照绑定合法候选。"""
        target = str(profile_id or "").strip()
        candidate_key = str(candidate_id or "").strip()
        board = self._repository.load_board(target)
        if board is None or board.profile_id != target:
            raise ValueError("current recommendation board is unavailable")
        if not any(
            item.candidate_id == candidate_key for item in board.recommendations
        ):
            raise ValueError("candidate is not in current recommendation board")
        candidate = next(
            (
                item
                for item in self._repository.load_candidate_snapshot(
                    board.run_id, target
                )
                if item.candidate_id == candidate_key
            ),
            None,
        )
        if candidate is None:
            raise ValueError("candidate snapshot is unavailable")
        tmdb_id = str(candidate.source_ids.get("tmdb") or "").strip()
        typed_tmdb_candidate_id(
            tmdb_id,
            candidate.media_type,
            candidate.metadata.get("mp_media_type"),
        )
        return board, candidate

    def _new_record(
        self,
        profile_id: str,
        board: Any,
        candidate: Candidate,
        *,
        state: str,
        observed_at: str,
        source: str,
    ) -> OutcomeAttribution:
        """从受信榜单候选创建第一条归因证据。"""
        field_times = {
            "native_drawer_opened_at": "",
            "subscription_observed_at": "",
            "library_observed_at": "",
            "playback_observed_at": "",
        }
        field_sources = {
            "native_drawer_source": "",
            "subscription_source": "",
            "library_source": "",
            "playback_source": "",
        }
        time_field = {
            "native_drawer_opened": "native_drawer_opened_at",
            "subscription_observed": "subscription_observed_at",
            "library_observed": "library_observed_at",
            "playback_observed": "playback_observed_at",
        }[state]
        source_field = {
            "native_drawer_opened": "native_drawer_source",
            "subscription_observed": "subscription_source",
            "library_observed": "library_source",
            "playback_observed": "playback_source",
        }[state]
        field_times[time_field] = observed_at
        field_sources[source_field] = source
        return OutcomeAttribution(
            attribution_id=self._attribution_id(board.run_id, candidate.candidate_id),
            profile_id=profile_id,
            run_id=board.run_id,
            candidate_id=candidate.candidate_id,
            title=candidate.title,
            media_type=candidate.media_type,
            media_source=candidate.media_source,
            media_id=candidate.media_id,
            tmdb_id=str(candidate.source_ids.get("tmdb") or ""),
            mp_media_type=str(candidate.metadata.get("mp_media_type") or ""),
            state=state,
            created_at=observed_at,
            updated_at=observed_at,
            verification_code="direct_evidence",
            **field_times,
            **field_sources,
        )

    def _record_direct(
        self,
        profile_id: str,
        candidate_id: str,
        *,
        state: str,
        source: str,
    ) -> OutcomeAttribution:
        """原子记录一项 UI 或受控服务直接证据。"""
        target = str(profile_id or "").strip()
        now = self._now()
        with self._repository.profile_data_guard(target):
            board, candidate = self._candidate_context(target, candidate_id)
            attribution_id = self._attribution_id(
                board.run_id, candidate.candidate_id
            )
            records = self._repository.load_outcome_attributions(target, strict=True)
            existing = next(
                (item for item in records if item.attribution_id == attribution_id),
                None,
            )
            updated = (
                existing.advance(state, now, source)
                if existing is not None
                else self._new_record(
                    target,
                    board,
                    candidate,
                    state=state,
                    observed_at=now,
                    source=source,
                )
            )
            retained = [
                updated if item.attribution_id == attribution_id else item
                for item in records
            ]
            if existing is None:
                retained.append(updated)
            self._repository.save_outcome_attributions(
                target, retained, limit=self._record_limit
            )
            return updated

    def record_native_drawer_opened(
        self, profile_id: str, candidate_id: str
    ) -> OutcomeAttribution:
        """仅记录 MoviePilot 原生订阅交互已打开，不宣称订阅成功。"""
        return self._record_direct(
            profile_id,
            candidate_id,
            state="native_drawer_opened",
            source="moviepilot_native_drawer",
        )

    def record_subscription_observed(
        self,
        profile_id: str,
        candidate_id: str,
        *,
        source: str = "plugin_controlled_subscription",
    ) -> OutcomeAttribution:
        """记录插件安全链已经确认的订阅存在证据。"""
        return self._record_direct(
            profile_id,
            candidate_id,
            state="subscription_observed",
            source=source,
        )

    @staticmethod
    def _candidate(record: OutcomeAttribution) -> Candidate:
        """从归因记录恢复宿主存在性检查所需的最小候选。"""
        return Candidate(
            candidate_id=record.candidate_id,
            title=record.title,
            media_type=record.media_type,
            media_source=record.media_source,
            media_id=record.media_id,
            source_ids={"tmdb": record.tmdb_id},
            metadata={"mp_media_type": record.mp_media_type},
        )

    @staticmethod
    def _playback_time(record: OutcomeAttribution, snapshot: PlaybackSnapshot) -> str:
        """返回发生在归因创建之后的目标播放时间，否则返回空。"""
        try:
            baseline = datetime.fromisoformat(record.created_at.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return ""
        baseline = baseline.replace(tzinfo=baseline.tzinfo or timezone.utc)
        matches = []
        for sample in snapshot.samples:
            try:
                sample_id = typed_tmdb_candidate_id(
                    sample.stable_id or sample.tmdb_id,
                    sample.media_type,
                )
            except ValueError:
                continue
            if sample_id != record.candidate_id or not sample.last_played_at:
                continue
            try:
                played = datetime.fromisoformat(
                    sample.last_played_at.replace("Z", "+00:00")
                )
            except (TypeError, ValueError):
                continue
            played = played.replace(tzinfo=played.tzinfo or timezone.utc)
            if played.astimezone(timezone.utc) >= baseline.astimezone(timezone.utc):
                matches.append(played.astimezone(timezone.utc))
        return max(matches).isoformat() if matches else ""

    def verify_profile(
        self,
        profile_id: str,
        *,
        playback_snapshot: Optional[PlaybackSnapshot] = None,
    ) -> AttributionVerificationResult:
        """复查订阅、媒体库和播放事实，失败时保持最后可信状态。"""
        target = str(profile_id or "").strip()
        if not target:
            raise ValueError("profile_id is required")
        checked_at = self._now()
        snapshot = playback_snapshot or self._repository.load_playback_snapshot(target)
        subscription_ids: Optional[Set[str]] = None
        subscription_error = ""
        try:
            subscription_ids = set(self._subscriptions.candidate_ids())
        except Exception:
            subscription_error = "subscription_read_failed"
        playback_error = "playback_read_failed"
        if (
            snapshot is not None
            and snapshot.profile_id == target
            and snapshot.status == "ready"
        ):
            playback_error = ""
        with self._repository.profile_data_guard(target):
            records = self._repository.load_outcome_attributions(target, strict=True)
            updated_records: List[OutcomeAttribution] = []
            advanced = 0
            pending_count = 0
            for record in records:
                if record.terminal:
                    updated_records.append(record)
                    continue
                before_rank = OUTCOME_STATE_RANK[record.state]
                current = record
                errors: List[str] = []
                if subscription_error:
                    errors.append(subscription_error)
                elif record.candidate_id in (subscription_ids or set()):
                    current = current.advance(
                        "subscription_observed",
                        checked_at,
                        "moviepilot_subscription",
                    )
                try:
                    in_library = bool(self._library.exists(self._candidate(record)))
                except Exception:
                    in_library = False
                    errors.append("library_read_failed")
                if in_library:
                    current = current.advance(
                        "library_observed", checked_at, "moviepilot_library"
                    )
                played_at = ""
                if playback_error:
                    errors.append(playback_error)
                else:
                    played_at = self._playback_time(record, snapshot)
                if played_at:
                    current = current.advance(
                        "playback_observed", played_at, "playback_reporting"
                    )
                    errors = []
                if OUTCOME_STATE_RANK[current.state] > before_rank:
                    advanced += 1
                pending = bool(errors) and not current.terminal
                if pending:
                    pending_count += 1
                current = current.mark_verification(
                    checked_at=checked_at,
                    pending=pending,
                    code=errors[0] if errors else "verification_complete",
                )
                updated_records.append(current)
            if updated_records != records:
                self._repository.save_outcome_attributions(
                    target, updated_records, limit=self._record_limit
                )
        return AttributionVerificationResult(
            profile_id=target,
            checked=len(updated_records),
            advanced=advanced,
            pending=pending_count,
            records=tuple(updated_records),
        )

    def list_records(self, profile_id: str) -> List[OutcomeAttribution]:
        """读取指定 profile 的全部有界归因记录。"""
        return self._repository.load_outcome_attributions(profile_id)

    def public_records(self, profile_id: str) -> List[Dict[str, Any]]:
        """返回前端可展示的脱敏归因记录。"""
        return [item.to_public_dict() for item in self.list_records(profile_id)]
