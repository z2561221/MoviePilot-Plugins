"""喜欢、不喜欢与忽略的统一反馈动作服务。"""

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..model.feedback import FeedbackEvent
from ..storage.repository import AgentRankRepository
from .archive import ArchiveService
from .board_refill import BoardRefillService


FEEDBACK_ACTION_KINDS = frozenset({"like", "dislike", "neutral", "ignore"})


class FeedbackActionError(Exception):
    """表示统一反馈动作的稳定业务错误。"""

    def __init__(self, code: str, message: str, status_code: int = 409):
        """保存错误码、用户文案和建议 HTTP 状态。"""
        self.code = str(code)
        self.message = str(message)
        self.status_code = int(status_code)
        super().__init__(self.message)


@dataclass(frozen=True)
class FeedbackActionResult:
    """返回反馈事实状态与动作后的最新榜单 revision。"""

    event: FeedbackEvent
    created: bool
    board_revision: int
    board_run_id: str
    board_changed: bool = False
    refill_count: int = 0
    current_count: int = 0
    refill_status: str = "not_applicable"
    message: str = ""

    def __post_init__(self) -> None:
        """校验结果始终携带已持久化事件和有效榜单版本。"""
        if not isinstance(self.event, FeedbackEvent) or not self.event.is_persisted:
            raise ValueError("feedback action result requires a persisted event")
        object.__setattr__(self, "created", bool(self.created))
        object.__setattr__(self, "board_revision", max(1, int(self.board_revision)))
        object.__setattr__(self, "board_run_id", str(self.board_run_id or ""))
        object.__setattr__(self, "board_changed", bool(self.board_changed))
        object.__setattr__(self, "refill_count", max(0, int(self.refill_count)))
        object.__setattr__(self, "current_count", max(0, int(self.current_count)))
        object.__setattr__(self, "refill_status", str(self.refill_status or "not_applicable"))
        object.__setattr__(self, "message", str(self.message or ""))

    def to_dict(self) -> Dict[str, Any]:
        """返回前端稳定动作结果，不暴露内部幂等索引。"""
        return {
            "changed": self.board_changed,
            "action": self.event.kind,
            "candidate_id": self.event.candidate_id,
            "board_changed": self.board_changed,
            "created": self.created,
            "event_status": "created" if self.created else "duplicate",
            "event": {
                "event_id": self.event.event_id,
                "sequence": self.event.sequence,
                "kind": self.event.kind,
                "candidate_id": self.event.candidate_id,
                "run_id": self.event.run_id,
                "analysis_id": self.event.analysis_id,
                "created_at": self.event.created_at,
                "status": self.event.status,
                "supersedes": self.event.supersedes,
            },
            "board_revision": self.board_revision,
            "board_run_id": self.board_run_id,
            "current_count": self.current_count,
            "refill_count": self.refill_count,
            "refill_status": self.refill_status,
            "message": self.message,
            "reason_code": (
                "safe_candidate_insufficient"
                if self.refill_status == "safe_candidate_insufficient"
                else ""
            ),
            "learning_effect": (
                "exclusion_only"
                if self.event.kind == "ignore"
                else "none"
                if self.event.kind == "neutral"
                else "pending_confirmation"
            ),
            "memory_delta": {},
        }


class FeedbackActionService:
    """把三态交互转换为幂等反馈事实并协调忽略事务。"""

    def __init__(
        self, repository: AgentRankRepository, *, analysis_limit: int = 500
    ):
        """绑定唯一仓储和既有归档领域服务。"""
        self._repository = repository
        self._archive = ArchiveService(repository)
        self._refill = BoardRefillService(repository)
        self._analysis_limit = max(1, min(int(analysis_limit), 100000))

    def _events(self, profile_id: str) -> list[FeedbackEvent]:
        """读取当前保留窗口内的全部反馈事实。"""
        return self._repository.load_feedback_events(profile_id)

    def active_polarities(self, profile_id: str, run_id: str) -> Dict[str, str]:
        """投影指定榜单轮次中每个作品最新的喜欢或不喜欢状态。"""
        target_run = str(run_id or "").strip()
        if not target_run:
            return {}
        states: Dict[str, str] = {}
        for event in self._events(profile_id):
            if (
                event.run_id == target_run
                and event.kind in {"like", "dislike", "neutral"}
                and event.candidate_id
                and event.status == "recorded"
            ):
                if event.kind == "neutral":
                    states.pop(event.candidate_id, None)
                else:
                    states[event.candidate_id] = event.kind
        return states

    def active_candidate_polarities(self, profile_id: str) -> Dict[str, str]:
        """跨榜单轮次投影每个作品最新且已记录的赞踩状态。"""
        states: Dict[str, str] = {}
        for event in self._events(profile_id):
            if (
                event.kind in {"like", "dislike", "neutral"}
                and event.candidate_id
                and event.status == "recorded"
            ):
                if event.kind == "neutral":
                    states.pop(event.candidate_id, None)
                else:
                    states[event.candidate_id] = event.kind
        return states

    def latest_candidate_polarities(self, profile_id: str) -> Dict[str, str]:
        """返回跨榜单最新赞踩或中立状态，保留中立取消语义。"""
        states: Dict[str, str] = {}
        for event in self._events(profile_id):
            if (
                event.kind in {"like", "dislike", "neutral"}
                and event.candidate_id
                and event.status == "recorded"
            ):
                states[event.candidate_id] = event.kind
        return states

    def active_disliked_candidate_ids(self, profile_id: str) -> set[str]:
        """返回仅用于作品级硬排除的当前不喜欢作品身份。"""
        return {
            candidate_id
            for candidate_id, polarity in self.active_candidate_polarities(
                profile_id
            ).items()
            if polarity == "dislike"
        }

    def _record_failed_retryable(
        self,
        *,
        profile_id: str,
        candidate_id: str,
        kind: str,
        request_key: str,
        actor_id: str,
        run_id: str,
        analysis_id: str,
        supersedes: str,
    ) -> None:
        """尽力记录不占用原幂等键的可重试失败事实。"""
        fingerprint = "|".join(
            (profile_id, candidate_id, kind, request_key, actor_id, run_id, analysis_id)
        )
        failure_key = f"failed:{hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()}"
        failure = FeedbackEvent(
            profile_id=profile_id,
            kind=kind,
            candidate_id=candidate_id,
            run_id=run_id,
            analysis_id=analysis_id,
            created_by_mp_user_id=actor_id,
            idempotency_key=failure_key,
            supersedes=supersedes,
            status="failed_retryable",
        )
        try:
            self._repository.append_feedback_event(failure)
        except Exception:
            return

    @staticmethod
    def _same_action(
        event: FeedbackEvent, *, kind: str, candidate_id: str, run_id: str
    ) -> bool:
        """判断一条事实是否代表同轮同作品的同类动作。"""
        return (
            event.kind == kind
            and event.candidate_id == candidate_id
            and event.run_id == run_id
            and event.status == "recorded"
        )

    @staticmethod
    def _same_idempotent_request(
        event: FeedbackEvent,
        *,
        kind: str,
        candidate_id: str,
        actor_id: str,
        run_id: str,
        analysis_id: str,
    ) -> bool:
        """验证同一幂等键没有被其他动作、作品、用户或上下文复用。"""
        return (
            event.kind == kind
            and event.candidate_id == candidate_id
            and event.created_by_mp_user_id == actor_id
            and (not run_id or event.run_id == run_id)
            and (not analysis_id or event.analysis_id == analysis_id)
        )

    @staticmethod
    def _result(
        event: FeedbackEvent,
        created: bool,
        board: Any,
        changed: bool = False,
        *,
        refill_count: int = 0,
        refill_status: str = "",
    ):
        """根据最新榜单构造统一结果。"""
        status = str(refill_status or "")
        if not status:
            if event.kind in {"dislike", "ignore"}:
                status = (
                    "safe_candidate_insufficient"
                    if board.status == "recommendation_incomplete"
                    else "filled"
                )
            else:
                status = "not_applicable"
        return FeedbackActionResult(
            event=event,
            created=created,
            board_revision=board.revision,
            board_run_id=board.run_id,
            board_changed=changed,
            refill_count=refill_count,
            current_count=len(board.recommendations),
            refill_status=status,
            message=str(board.message or "") if changed else "",
        )

    def act(
        self,
        *,
        profile_id: str,
        candidate_id: str,
        kind: str,
        idempotency_key: str,
        actor_id: str = "",
        analysis_id: str = "",
        expected_board_revision: Optional[int] = None,
        expected_run_id: str = "",
        defer_polarity_side_effects: bool = False,
    ) -> FeedbackActionResult:
        """幂等记录三态动作；忽略同时原子更新榜单和归档。"""
        target = str(profile_id or "").strip()
        candidate = str(candidate_id or "").strip()
        action = str(kind or "").strip().casefold()
        request_key = str(idempotency_key or "").strip()
        actor = str(actor_id or "").strip()
        analysis = str(analysis_id or "").strip()
        expected_run = str(expected_run_id or "").strip()
        defer_polarity = bool(defer_polarity_side_effects)
        if not target or not candidate:
            raise FeedbackActionError(
                "invalid_feedback_target", "反馈必须指定 profile_id 和 candidate_id", 422
            )
        if action not in FEEDBACK_ACTION_KINDS:
            raise FeedbackActionError(
                "invalid_feedback_kind", "反馈类型必须是点赞、点踩、取消或忽略", 422
            )
        if not request_key:
            raise FeedbackActionError(
                "idempotency_key_required", "反馈请求缺少幂等标识", 422
            )
        if len(request_key) > 256:
            raise FeedbackActionError(
                "invalid_idempotency_key", "反馈幂等标识长度不能超过 256 个字符", 422
            )

        with self._repository.feedback_action_guard(target):
            board = self._repository.load_board(target)
            if board is None:
                raise FeedbackActionError(
                    "board_unavailable", "当前没有可操作的推荐榜单", 409
                )

            existing_request = self._repository.load_feedback_event(
                target, request_key
            )
            if existing_request is not None:
                if not self._same_idempotent_request(
                    existing_request,
                    kind=action,
                    candidate_id=candidate,
                    actor_id=actor,
                    run_id=expected_run,
                    analysis_id=analysis,
                ):
                    raise FeedbackActionError(
                        "idempotency_conflict", "幂等标识已被其他反馈请求使用", 409
                    )
                return self._result(existing_request, False, board)

            if expected_run and expected_run != board.run_id:
                raise FeedbackActionError(
                    "board_run_conflict", "榜单已刷新，请基于最新榜单重试", 409
                )
            if expected_board_revision is not None:
                try:
                    expected_revision = int(expected_board_revision)
                except (TypeError, ValueError) as error:
                    raise FeedbackActionError(
                        "invalid_board_revision", "榜单 revision 必须是整数", 422
                    ) from error
                if expected_revision != board.revision:
                    raise FeedbackActionError(
                        "board_revision_conflict", "榜单状态已变化，请刷新后重试", 409
                    )

            events = self._events(target)
            same_action = next(
                (
                    event
                    for event in reversed(events)
                    if self._same_action(
                        event,
                        kind=action,
                        candidate_id=candidate,
                        run_id=board.run_id,
                    )
                ),
                None,
            )
            board_item = next(
                (
                    item
                    for item in board.recommendations
                    if item.candidate_id == candidate
                ),
                None,
            )
            item_present = board_item is not None
            archive = self._repository.load_archive(target)
            archived = any(entry.candidate_id == candidate for entry in archive.entries)
            latest_polarity = next(
                (
                    event
                    for event in reversed(events)
                    if event.kind in {"like", "dislike", "neutral"}
                    and event.candidate_id == candidate
                    and event.run_id == board.run_id
                    and event.status == "recorded"
                ),
                None,
            )
            if (
                action in {"like", "dislike"}
                and latest_polarity is not None
                and latest_polarity.kind == action
                and not (action == "dislike" and item_present)
            ):
                return self._result(latest_polarity, False, board)
            if action == "neutral":
                if latest_polarity is None or latest_polarity.kind == "neutral":
                    raise FeedbackActionError(
                        "feedback_already_neutral", "当前作品没有可取消的点赞或点踩", 409
                    )
            if action == "ignore" and same_action is not None and archived and not item_present:
                return self._result(same_action, False, board)
            if not item_present and not (
                action in {"like", "dislike", "neutral"}
                and latest_polarity is not None
            ):
                raise FeedbackActionError(
                    "candidate_not_on_board", "该作品已不在当前榜单中", 409
                )

            bound_analysis = (
                str(getattr(board_item, "analysis_id", "") or "").strip()
                if board_item is not None
                else str(getattr(latest_polarity, "analysis_id", "") or "").strip()
            )
            if analysis and analysis != bound_analysis:
                raise FeedbackActionError(
                    "analysis_context_conflict",
                    "Agent分析已变化，请基于当前榜单重新操作",
                    409,
                )
            analysis = bound_analysis

            supersedes = ""
            if action in {"like", "dislike", "neutral"}:
                if latest_polarity is not None:
                    supersedes = latest_polarity.event_id
            elif same_action is not None:
                supersedes = same_action.event_id

            draft = FeedbackEvent(
                profile_id=target,
                kind=action,
                candidate_id=candidate,
                run_id=board.run_id,
                analysis_id=analysis,
                created_by_mp_user_id=actor,
                idempotency_key=request_key,
                supersedes=supersedes,
            )
            old_board_archive = None
            board_changed = False
            refill_count = 0
            refill_status = "not_applicable"
            try:
                if (
                    action in {"dislike", "ignore"}
                    and item_present
                    and not (action == "dislike" and defer_polarity)
                ):
                    old_board_archive = self._repository.capture_feedback_action_raw(
                        target
                    )
                    if action == "ignore":
                        archive_result = self._archive._apply_ignore_state(
                            target, board, archive, candidate
                        )
                        if not archive_result.changed:
                            raise FeedbackActionError(
                                "ignore_state_conflict",
                                "忽略状态已变化，请刷新后重试",
                                409,
                            )
                        action_label = "忽略"
                    else:
                        board.recommendations = [
                            item
                            for item in board.recommendations
                            if item.candidate_id != candidate
                        ]
                        board.revision += 1
                        action_label = "不喜欢"
                    disliked_ids = {
                        candidate_id
                        for candidate_id, polarity in self.active_polarities(
                            target, board.run_id
                        ).items()
                        if polarity == "dislike"
                    }
                    archived_ids = {entry.candidate_id for entry in archive.entries}
                    refill = self._refill.refill(
                        target,
                        board,
                        blocked_candidate_ids={
                            *disliked_ids,
                            *archived_ids,
                            candidate,
                        },
                        action_label=action_label,
                    )
                    refill_count = refill.refill_count
                    refill_status = refill.status
                    if refill.analysis_context_ready:
                        self._repository.save_board_with_recommendation_analyses(
                            board,
                            refill.analyses,
                            limit=self._analysis_limit,
                            archive=archive,
                        )
                    else:
                        self._repository.save_board_and_archive(board, archive)
                    board_changed = True
                appended = self._repository.append_feedback_event(draft)
            except Exception:
                if old_board_archive is not None:
                    try:
                        self._repository.restore_feedback_action_raw(
                            target, old_board_archive
                        )
                    except Exception as rollback_error:
                        raise FeedbackActionError(
                            "feedback_rollback_failed",
                            "反馈保存失败且状态恢复异常，请刷新核对后重试",
                            500,
                        ) from rollback_error
                    self._record_failed_retryable(
                        profile_id=target,
                        candidate_id=candidate,
                        kind=action,
                        request_key=request_key,
                        actor_id=actor,
                        run_id=board.run_id,
                        analysis_id=analysis,
                        supersedes=supersedes,
                    )
                raise
            return self._result(
                appended.event,
                appended.created,
                board,
                changed=board_changed,
                refill_count=refill_count,
                refill_status=refill_status,
            )

    def is_current_polarity(self, event: FeedbackEvent) -> bool:
        """判断延迟任务引用的赞踩事实是否仍是当前最终状态。"""
        if not isinstance(event, FeedbackEvent) or event.kind not in {"like", "dislike"}:
            return False
        latest = next(
            (
                item
                for item in reversed(self._events(event.profile_id))
                if item.candidate_id == event.candidate_id
                and item.run_id == event.run_id
                and item.kind in {"like", "dislike", "neutral"}
                and item.status == "recorded"
            ),
            None,
        )
        return latest is not None and latest.event_id == event.event_id

    def finalize_deferred_polarity(self, event: FeedbackEvent) -> bool:
        """在防抖截止后应用最终点踩的榜单移除与安全补位。"""
        if not self.is_current_polarity(event) or event.kind != "dislike":
            return False
        target = event.profile_id
        with self._repository.feedback_action_guard(target):
            if not self.is_current_polarity(event):
                return False
            board = self._repository.load_board(target)
            if board is None or board.run_id != event.run_id:
                return False
            item = next(
                (
                    value
                    for value in board.recommendations
                    if value.candidate_id == event.candidate_id
                ),
                None,
            )
            if item is None:
                return False
            archive = self._repository.load_archive(target)
            raw = self._repository.capture_feedback_action_raw(target)
            try:
                board.recommendations = [
                    value
                    for value in board.recommendations
                    if value.candidate_id != event.candidate_id
                ]
                board.revision += 1
                disliked_ids = {
                    candidate_id
                    for candidate_id, polarity in self.active_polarities(
                        target, board.run_id
                    ).items()
                    if polarity == "dislike"
                }
                archived_ids = {entry.candidate_id for entry in archive.entries}
                refill = self._refill.refill(
                    target,
                    board,
                    blocked_candidate_ids={*disliked_ids, *archived_ids},
                    action_label="点踩",
                )
                if refill.analysis_context_ready:
                    self._repository.save_board_with_recommendation_analyses(
                        board,
                        refill.analyses,
                        limit=self._analysis_limit,
                        archive=archive,
                    )
                else:
                    self._repository.save_board_and_archive(board, archive)
            except Exception:
                self._repository.restore_feedback_action_raw(target, raw)
                raise
            return True
