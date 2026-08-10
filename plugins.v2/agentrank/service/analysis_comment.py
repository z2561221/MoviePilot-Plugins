"""逐条 Agent 分析评论、幂等事件与安全修订服务。"""

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..model.analysis import RecommendationAnalysis
from ..model.feedback import FeedbackEvent
from ..model.feedback_understanding import FeedbackUnderstandingRecord
from ..storage.repository import AgentRankRepository


ANALYSIS_COMMENT_KIND = "analysis_comment"


class AnalysisCommentError(Exception):
    """表示分析评论无法在当前榜单上下文中安全受理。"""

    def __init__(self, code: str, message: str, status_code: int = 409):
        """保存稳定错误码、用户文案和建议 HTTP 状态。"""
        self.code = str(code)
        self.message = str(message)
        self.status_code = int(status_code)
        super().__init__(self.message)


@dataclass(frozen=True)
class AnalysisCommentResult:
    """返回评论事件及提交时的榜单版本。"""

    event: FeedbackEvent
    created: bool
    board_revision: int
    board_run_id: str
    analysis_status: str = "pending_revision"

    def __post_init__(self) -> None:
        """校验结果始终引用已持久化评论事实。"""
        if not isinstance(self.event, FeedbackEvent) or not self.event.is_persisted:
            raise ValueError("analysis comment result requires a persisted event")
        if self.event.kind != ANALYSIS_COMMENT_KIND:
            raise ValueError("analysis comment result event kind is invalid")
        object.__setattr__(self, "created", bool(self.created))
        object.__setattr__(self, "board_revision", max(1, int(self.board_revision)))
        object.__setattr__(self, "board_run_id", str(self.board_run_id or ""))
        object.__setattr__(
            self, "analysis_status", str(self.analysis_status or "pending_revision")
        )
        if self.analysis_status not in {
            "pending_revision",
            "revised",
            "awaiting_clarification",
        }:
            raise ValueError("analysis comment result status is invalid")

    def to_dict(self) -> Dict[str, Any]:
        """返回不回显评论正文的前端安全结果。"""
        return {
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
            },
            "board_revision": self.board_revision,
            "board_run_id": self.board_run_id,
            "analysis_status": self.analysis_status,
            "learning_effect": "no_memory_change",
        }


class AnalysisCommentService:
    """校验评论归属并把理解结果投影为不可变分析修订。"""

    def __init__(
        self, repository: AgentRankRepository, *, analysis_limit: int = 500
    ):
        """绑定仓储和结构化分析保留上限。"""
        if not isinstance(repository, AgentRankRepository):
            raise TypeError("repository must be AgentRankRepository")
        self._repository = repository
        self._analysis_limit = max(1, min(int(analysis_limit), 100000))

    @staticmethod
    def _same_request(
        event: FeedbackEvent,
        *,
        candidate_id: str,
        analysis_id: str,
        comment: str,
        actor_id: str,
        run_id: str,
    ) -> bool:
        """判断同一幂等键是否对应完全相同的评论请求。"""
        return (
            event.kind == ANALYSIS_COMMENT_KIND
            and event.candidate_id == candidate_id
            and event.analysis_id == analysis_id
            and event.comment == comment
            and event.created_by_mp_user_id == actor_id
            and (not run_id or event.run_id == run_id)
        )

    @staticmethod
    def _analysis_by_id(
        analyses: list[RecommendationAnalysis], analysis_id: str
    ) -> Optional[RecommendationAnalysis]:
        """从当前 profile 的有界历史中读取指定分析。"""
        return next(
            (item for item in analyses if item.analysis_id == analysis_id),
            None,
        )

    def submit(
        self,
        *,
        profile_id: str,
        candidate_id: str,
        analysis_id: str,
        comment: str,
        idempotency_key: str,
        actor_id: str,
        expected_board_revision: Optional[int] = None,
        expected_run_id: str = "",
    ) -> AnalysisCommentResult:
        """绑定当前可见分析并幂等追加一条不可变评论事件。"""
        target = str(profile_id or "").strip()
        candidate = str(candidate_id or "").strip()
        source_analysis_id = str(analysis_id or "").strip()
        text = " ".join(str(comment or "").split()).strip()
        request_key = str(idempotency_key or "").strip()
        actor = str(actor_id or "").strip()
        expected_run = str(expected_run_id or "").strip()
        if not target or not candidate or not source_analysis_id:
            raise AnalysisCommentError(
                "invalid_analysis_comment_target",
                "评论必须指定 profile_id、candidate_id 和 analysis_id",
                422,
            )
        if not text:
            raise AnalysisCommentError(
                "analysis_comment_required", "请输入需要纠正的具体内容", 422
            )
        if len(text) > 1000:
            raise AnalysisCommentError(
                "analysis_comment_too_long", "评论不能超过 1000 个字符", 422
            )
        if not request_key or len(request_key) > 256:
            raise AnalysisCommentError(
                "invalid_idempotency_key", "评论请求缺少有效幂等标识", 422
            )
        if not actor or len(actor) > 160:
            raise AnalysisCommentError(
                "analysis_comment_actor_required", "无法确认当前评论操作者", 403
            )

        with self._repository.feedback_action_guard(target):
            board = self._repository.load_board(target)
            if board is None:
                raise AnalysisCommentError(
                    "board_unavailable", "当前没有可评论的推荐榜单", 409
                )
            existing = self._repository.load_feedback_event(target, request_key)
            if existing is not None:
                if not self._same_request(
                    existing,
                    candidate_id=candidate,
                    analysis_id=source_analysis_id,
                    comment=text,
                    actor_id=actor,
                    run_id=expected_run,
                ):
                    raise AnalysisCommentError(
                        "idempotency_conflict", "幂等标识已被其他评论请求使用", 409
                    )
                understanding = self._repository.load_feedback_understanding(
                    target, existing.event_id
                )
                analysis_status = "pending_revision"
                if understanding is not None:
                    if understanding.outcome == "ambiguous":
                        analysis_status = "awaiting_clarification"
                    elif understanding.outcome == "understood":
                        revised = any(
                            item.analysis_id
                            == understanding.analysis_revision_id
                            for item in self._repository.load_recommendation_analyses(
                                target, existing.run_id
                            )
                        )
                        analysis_status = (
                            "revised" if revised else "pending_revision"
                        )
                return AnalysisCommentResult(
                    event=existing,
                    created=False,
                    board_revision=board.revision,
                    board_run_id=board.run_id,
                    analysis_status=analysis_status,
                )
            if expected_run and expected_run != board.run_id:
                raise AnalysisCommentError(
                    "board_run_conflict", "榜单已刷新，请基于最新分析重试", 409
                )
            if expected_board_revision is not None:
                try:
                    expected_revision = int(expected_board_revision)
                except (TypeError, ValueError) as error:
                    raise AnalysisCommentError(
                        "invalid_board_revision", "榜单 revision 必须是整数", 422
                    ) from error
                if expected_revision != board.revision:
                    raise AnalysisCommentError(
                        "board_revision_conflict", "榜单状态已变化，请刷新后重试", 409
                    )
            item = next(
                (
                    recommendation
                    for recommendation in board.recommendations
                    if recommendation.candidate_id == candidate
                ),
                None,
            )
            if item is None:
                raise AnalysisCommentError(
                    "candidate_not_on_board", "该作品已不在当前榜单中", 409
                )
            if item.analysis_id != source_analysis_id:
                raise AnalysisCommentError(
                    "analysis_context_conflict",
                    "Agent分析已变化，请基于当前分析重新评论",
                    409,
                )
            analysis = self._analysis_by_id(
                self._repository.load_recommendation_analyses(target, board.run_id),
                source_analysis_id,
            )
            if (
                analysis is None
                or analysis.profile_id != target
                or analysis.candidate_id != candidate
                or analysis.run_id != board.run_id
                or analysis.status != "active"
            ):
                raise AnalysisCommentError(
                    "analysis_unavailable", "当前 Agent 分析缺少完整审计上下文", 409
                )
            appended = self._repository.append_feedback_event(
                FeedbackEvent(
                    profile_id=target,
                    kind=ANALYSIS_COMMENT_KIND,
                    candidate_id=candidate,
                    run_id=board.run_id,
                    analysis_id=source_analysis_id,
                    comment=text,
                    created_by_mp_user_id=actor,
                    idempotency_key=request_key,
                )
            )
            return AnalysisCommentResult(
                event=appended.event,
                created=appended.created,
                board_revision=board.revision,
                board_run_id=board.run_id,
            )

    @staticmethod
    def revision_id(event: FeedbackEvent) -> str:
        """根据不可变事件身份生成重试稳定的分析版本 ID。"""
        digest = hashlib.sha256(
            f"analysis-comment:{event.event_id}".encode("utf-8")
        ).hexdigest()[:32]
        return f"analysis-{digest}"

    def apply_revision(
        self, event: FeedbackEvent, record: FeedbackUnderstandingRecord
    ) -> RecommendationAnalysis:
        """幂等应用已理解评论，保持确定性证据和支持度不变。"""
        if not isinstance(event, FeedbackEvent) or event.kind != ANALYSIS_COMMENT_KIND:
            raise ValueError("analysis revision event is invalid")
        if (
            not isinstance(record, FeedbackUnderstandingRecord)
            or record.event_id != event.event_id
            or record.profile_id != event.profile_id
            or record.action != ANALYSIS_COMMENT_KIND
            or record.outcome != "understood"
        ):
            raise ValueError("analysis revision understanding is invalid")
        if record.analysis_revision_id != self.revision_id(event):
            raise ValueError("analysis revision identity mismatch")
        fingerprint = hashlib.sha256(
            (
                f"{event.analysis_id}\0{record.prompt_fingerprint}\0"
                f"{record.analysis_revision_id}"
            ).encode("utf-8")
        ).hexdigest()
        return self._repository.revise_recommendation_analysis(
            profile_id=event.profile_id,
            candidate_id=event.candidate_id,
            run_id=event.run_id,
            source_analysis_id=event.analysis_id,
            revision_analysis_id=record.analysis_revision_id,
            revision_event_id=event.event_id,
            revised_reason=record.analysis_revision_reason,
            correction_note=record.analysis_revision_note,
            prompt_fingerprint=fingerprint,
            created_at=record.created_at,
            limit=self._analysis_limit,
        )
