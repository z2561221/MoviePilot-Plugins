"""反馈记录与结构化分析交互。"""

from datetime import datetime, timezone
from typing import Any, Dict

from .errors import ApiContractError
from ..service.analysis_comment import AnalysisCommentError, AnalysisCommentService
from ..service.feedback_action import FeedbackActionError, FeedbackActionService
from ..service.feedback_queue import FeedbackQueueError


class FeedbackApiMixin:
    """反馈记录与结构化分析交互。"""

    def feedback(self, payload: Any, actor_id: str = "") -> Dict[str, Any]:
        """通过统一事实入口记录喜欢、不喜欢或忽略。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        candidate_id = self._candidate_id(body)
        try:
            result = FeedbackActionService(
                self._repository(),
                analysis_limit=int(
                    self.plugin._config.get("analysis_record_limit") or 500
                ),
            ).act(
                profile_id=target,
                candidate_id=candidate_id,
                kind=str(body.get("kind") or ""),
                idempotency_key=str(body.get("idempotency_key") or ""),
                actor_id=actor_id,
                analysis_id=str(body.get("analysis_id") or ""),
                expected_board_revision=body.get("board_revision"),
                expected_run_id=str(body.get("run_id") or ""),
                defer_polarity_side_effects=True,
            )
        except FeedbackActionError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "feedback_failed", "反馈保存失败，榜单与归档已恢复"
            ) from error
        try:
            queue_job = (
                None
                if result.event.kind == "neutral"
                else self._feedback_queue().enqueue_event(
                    result.event,
                    delay_seconds=(
                        float(
                            self.plugin._config.get(
                                "feedback_debounce_seconds", 30.0
                            )
                        )
                        if result.event.kind in {"like", "dislike"}
                        else 0.0
                    ),
                    debounce_profile=result.event.kind in {"like", "dislike"},
                )
            )
        except FeedbackQueueError as error:
            raise ApiContractError(
                503,
                "feedback_queue_failed",
                "反馈已保存，但理解任务入队失败；可使用原操作重试",
            ) from error
        data = result.to_dict()
        data["queue_status"] = queue_job.status if queue_job is not None else "cancelled"
        data["queue_job"] = queue_job.to_public_dict() if queue_job is not None else None
        short_term = None
        try:
            # FeedbackActionResult 已在同一事务中返回动作后的真实榜单上下文；
            # 不要再使用客户端可能携带的旧 revision，避免把学习投影写入错误版本。
            result_board_run_id = str(
                getattr(result, "board_run_id", "")
                or result.event.run_id
                or ""
            )
            result_board_revision = max(
                1,
                int(
                    getattr(result, "board_revision", 0)
                    or 1
                ),
            )
            if result.event.kind in {"like", "dislike"}:
                self._repository().record_board_interaction(
                    target,
                    result_board_run_id,
                    result_board_revision,
                    result.event.kind,
                    datetime.now(timezone.utc).isoformat(),
                )
                short_term = self._append_short_term_signal(
                    profile_id=target,
                    kind=result.event.kind,
                    idempotency_key=f"feedback:{result.event.idempotency_key}",
                    candidate_id=result.event.candidate_id,
                    run_id=result_board_run_id,
                    board_revision=result_board_revision,
                    source="structured_feedback",
                    strength=0.95 if result.event.kind == "like" else -1.0,
                    decay_days=60,
                )
            elif result.event.kind == "ignore":
                self._repository().record_board_interaction(
                    target,
                    result_board_run_id,
                    result_board_revision,
                    "ignore",
                    datetime.now(timezone.utc).isoformat(),
                )
        except Exception as error:
            # 反馈事实已经成功落账；把学习投影错误留在响应中，避免重复提交写入。
            short_term = {
                "created": False,
                "error": "short_term_signal_failed",
                "message": str(error)[:160],
            }
        data["short_term"] = short_term
        return self._success(data)

    def analysis_comment(self, payload: Any, actor_id: str = "") -> Dict[str, Any]:
        """记录一条绑定当前结构化分析的用户评论并异步修订。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        candidate_id = self._candidate_id(body)
        try:
            result = AnalysisCommentService(
                self._repository(),
                analysis_limit=int(
                    self.plugin._config.get("analysis_record_limit") or 500
                ),
            ).submit(
                profile_id=target,
                candidate_id=candidate_id,
                analysis_id=str(body.get("analysis_id") or ""),
                comment=str(body.get("comment") or ""),
                idempotency_key=str(body.get("idempotency_key") or ""),
                actor_id=actor_id,
                expected_board_revision=body.get("board_revision"),
                expected_run_id=str(body.get("run_id") or ""),
            )
        except AnalysisCommentError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "analysis_comment_failed", "评论保存失败，请刷新后重试"
            ) from error
        try:
            queue_job = self._feedback_queue().enqueue_event(result.event)
        except FeedbackQueueError as error:
            raise ApiContractError(
                503,
                "analysis_comment_queue_failed",
                "评论已保存，但分析修订任务入队失败；可使用原操作重试",
            ) from error
        data = result.to_dict()
        data["queue_status"] = queue_job.status
        data["queue_job"] = queue_job.to_public_dict()
        return self._success(data)

    def analysis(
        self,
        profile_id: Any,
        candidate_id: Any,
        analysis_id: Any,
    ) -> Dict[str, Any]:
        """返回当前榜单候选绑定的结构化分析，拒绝读取过期版本。"""
        target = self._profile_id(profile_id)
        candidate = str(candidate_id or "").strip()
        requested_analysis = str(analysis_id or "").strip()
        if not candidate or not requested_analysis:
            raise ApiContractError(
                422,
                "analysis_identity_required",
                "缺少推荐分析标识，请刷新榜单后重试",
            )
        board = self._repository().load_board(target)
        if board is None:
            raise ApiContractError(409, "board_unavailable", "当前没有可读取的推荐榜单")
        item = next(
            (
                value
                for value in board.recommendations
                if value.candidate_id == candidate
            ),
            None,
        )
        if item is None or item.analysis_id != requested_analysis:
            raise ApiContractError(
                409,
                "analysis_revision_conflict",
                "推荐分析已更新，请刷新榜单后重试",
            )
        record = next(
            (
                value
                for value in self._repository().load_recommendation_analyses(
                    target, board.run_id
                )
                if value.analysis_id == requested_analysis
                and value.candidate_id == candidate
                and value.status == "active"
            ),
            None,
        )
        if record is None:
            raise ApiContractError(
                404,
                "analysis_unavailable",
                "当前推荐分析不可用，请刷新榜单后重试",
            )
        return self._success(record.to_dict())
