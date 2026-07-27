"""基于同轮冻结安全候选维护固定五条榜单。"""

from dataclasses import dataclass
from typing import Iterable, List, Optional

from ..model.board import RecommendationBoard
from ..model.constants import RECOMMENDATION_LIMIT
from ..storage.repository import AgentRankRepository
from .validation import RecommendationValidator


@dataclass(frozen=True)
class BoardRefillResult:
    """描述一次移除后的确定性安全补位结果。"""

    board: RecommendationBoard
    refill_count: int
    status: str

    @property
    def current_count(self) -> int:
        """返回补位完成后的实际榜单条数。"""
        return len(self.board.recommendations)


class BoardRefillService:
    """只使用当前 run 的不可变候选快照补齐榜单。"""

    def __init__(
        self,
        repository: AgentRankRepository,
        validator: Optional[RecommendationValidator] = None,
    ):
        """绑定候选快照仓储与既有安全推荐验证器。"""
        self._repository = repository
        self._validator = validator or RecommendationValidator()

    def refill(
        self,
        profile_id: str,
        board: RecommendationBoard,
        *,
        blocked_candidate_ids: Iterable[str] = (),
        action_label: str,
    ) -> BoardRefillResult:
        """按冻结候选原顺序补位，并写明安全候选不足状态。"""
        target = str(profile_id or "").strip()
        if board.profile_id != target:
            raise PermissionError("board profile_id does not match requested profile_id")

        blocked = {
            str(candidate_id or "").strip()
            for candidate_id in blocked_candidate_ids or ()
            if str(candidate_id or "").strip()
        }
        snapshot = self._repository.load_candidate_snapshot_record(
            board.run_id, target
        )
        candidates = list(snapshot.candidates) if snapshot is not None else []
        profile = self._repository.load_profile(target)
        preference_evidence: List[str] = []
        if profile is not None:
            preference_evidence.extend(profile.tags)
            preference_evidence.extend(profile.ranking_tags)

        fallback = self._validator.build_fallback_items(
            candidates,
            board.recommendations,
            blocked_candidate_ids=blocked,
            preference_evidence=preference_evidence,
            limit=RECOMMENDATION_LIMIT,
        )
        board.recommendations.extend(fallback)
        for rank, item in enumerate(board.recommendations, start=1):
            item.rank = rank

        if len(board.recommendations) >= RECOMMENDATION_LIMIT:
            board.recommendations = board.recommendations[:RECOMMENDATION_LIMIT]
            board.status = "success"
            board.message = (
                f"{action_label}已生效，并从本轮冻结安全候选池补位"
                if fallback
                else f"{action_label}已生效，榜单仍保持五条"
            )
            status = "filled"
        else:
            board.status = "recommendation_incomplete"
            board.message = (
                f"{action_label}已生效；安全候选不足，当前仅"
                f" {len(board.recommendations)} 条"
            )
            status = "safe_candidate_insufficient"
        return BoardRefillResult(
            board=board,
            refill_count=len(fallback),
            status=status,
        )
