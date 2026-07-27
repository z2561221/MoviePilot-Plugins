"""喜欢、不喜欢与忽略的统一反馈动作服务。"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..model.feedback import FeedbackEvent
from ..storage.repository import AgentRankRepository
from .archive import ArchiveService


FEEDBACK_ACTION_KINDS = frozenset({"like", "dislike", "ignore"})


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

    def __post_init__(self) -> None:
        """校验结果始终携带已持久化事件和有效榜单版本。"""
        if not isinstance(self.event, FeedbackEvent) or not self.event.is_persisted:
            raise ValueError("feedback action result requires a persisted event")
        object.__setattr__(self, "created", bool(self.created))
        object.__setattr__(self, "board_revision", max(1, int(self.board_revision)))
        object.__setattr__(self, "board_run_id", str(self.board_run_id or ""))
        object.__setattr__(self, "board_changed", bool(self.board_changed))

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
            "learning_effect": (
                "exclusion_only"
                if self.event.kind == "ignore"
                else "pending_confirmation"
            ),
            "memory_delta": {},
        }


class FeedbackActionService:
    """把三态交互转换为幂等反馈事实并协调忽略事务。"""

    def __init__(self, repository: AgentRankRepository):
        """绑定唯一仓储和既有归档领域服务。"""
        self._repository = repository
        self._archive = ArchiveService(repository)

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
                and event.kind in {"like", "dislike"}
                and event.candidate_id
            ):
                states[event.candidate_id] = event.kind
        return states

    @staticmethod
    def _same_action(
        event: FeedbackEvent, *, kind: str, candidate_id: str, run_id: str
    ) -> bool:
        """判断一条事实是否代表同轮同作品的同类动作。"""
        return (
            event.kind == kind
            and event.candidate_id == candidate_id
            and event.run_id == run_id
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
    def _result(event: FeedbackEvent, created: bool, board: Any, changed: bool = False):
        """根据最新榜单构造统一结果。"""
        return FeedbackActionResult(
            event=event,
            created=created,
            board_revision=board.revision,
            board_run_id=board.run_id,
            board_changed=changed,
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
    ) -> FeedbackActionResult:
        """幂等记录三态动作；忽略同时原子更新榜单和归档。"""
        target = str(profile_id or "").strip()
        candidate = str(candidate_id or "").strip()
        action = str(kind or "").strip().casefold()
        request_key = str(idempotency_key or "").strip()
        actor = str(actor_id or "").strip()
        analysis = str(analysis_id or "").strip()
        expected_run = str(expected_run_id or "").strip()
        if not target or not candidate:
            raise FeedbackActionError(
                "invalid_feedback_target", "反馈必须指定 profile_id 和 candidate_id", 422
            )
        if action not in FEEDBACK_ACTION_KINDS:
            raise FeedbackActionError(
                "invalid_feedback_kind", "反馈类型必须是喜欢、不喜欢或忽略", 422
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
            item_present = any(
                item.candidate_id == candidate for item in board.recommendations
            )
            archive = self._repository.load_archive(target)
            archived = any(entry.candidate_id == candidate for entry in archive.entries)
            latest_polarity = next(
                (
                    event
                    for event in reversed(events)
                    if event.kind in {"like", "dislike"}
                    and event.candidate_id == candidate
                    and event.run_id == board.run_id
                ),
                None,
            )
            if (
                action in {"like", "dislike"}
                and latest_polarity is not None
                and latest_polarity.kind == action
            ):
                return self._result(latest_polarity, False, board)
            if action == "ignore" and same_action is not None and archived and not item_present:
                return self._result(same_action, False, board)
            if not item_present:
                raise FeedbackActionError(
                    "candidate_not_on_board", "该作品已不在当前榜单中", 409
                )

            supersedes = ""
            if action in {"like", "dislike"}:
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
            try:
                if action == "ignore":
                    old_board_archive = self._repository.capture_board_archive_raw(target)
                    archive_result = self._archive._ignore_locked(target, candidate)
                    if not archive_result.changed:
                        raise FeedbackActionError(
                            "ignore_state_conflict", "忽略状态已变化，请刷新后重试", 409
                        )
                    board_changed = True
                    board = self._repository.load_board(target)
                    if board is None:
                        raise RuntimeError("ignored board disappeared after save")
                appended = self._repository.append_feedback_event(draft)
            except Exception:
                if old_board_archive is not None:
                    try:
                        self._repository.restore_board_archive_raw(
                            target, old_board_archive
                        )
                    except Exception as rollback_error:
                        raise FeedbackActionError(
                            "feedback_rollback_failed",
                            "反馈保存失败且状态恢复异常，请刷新核对后重试",
                            500,
                        ) from rollback_error
                raise
            return self._result(
                appended.event,
                appended.created,
                board,
                changed=board_changed,
            )
