"""基于同轮冻结安全候选维护固定五条榜单。"""

from dataclasses import dataclass
from typing import Iterable, List, Optional

from ..model.board import RecommendationBoard
from ..model.constants import RECOMMENDATION_LIMIT
from ..storage.repository import AgentRankRepository
from .scoring import PolicyLearningService, StableRecommendationRanker
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
        ranker: Optional[StableRecommendationRanker] = None,
    ):
        """绑定候选快照仓储与既有安全推荐验证器。"""
        self._repository = repository
        self._validator = validator or RecommendationValidator()
        self._ranker = ranker or StableRecommendationRanker()

    @staticmethod
    def _context_matches_board(
        profile_id: str,
        board: RecommendationBoard,
        policy: object,
        memory: object,
        playback: object,
    ) -> bool:
        """确认当前上下文与榜单已保存的策略和播放事实完全一致。"""
        if any(value is None for value in (policy, memory, playback)):
            return False
        if not board.recommendations:
            return False
        if any(item.support is None for item in board.recommendations):
            return False
        policy_versions = {
            item.support.policy_version for item in board.recommendations
        }
        if policy_versions and policy_versions != {
            str(getattr(policy, "policy_version", "") or "")
        }:
            return False
        return bool(
            str(getattr(policy, "profile_id", "") or "") == profile_id
            and str(getattr(memory, "profile_id", "") or "") == profile_id
            and str(getattr(playback, "profile_id", "") or "") == profile_id
            and int(getattr(policy, "memory_revision", -1))
            == int(getattr(memory, "memory_revision", -2))
            and str(getattr(policy, "playback_fingerprint", "") or "")
            == PolicyLearningService.playback_fingerprint(playback)
        )

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
        scoring_errors: List[str] = []
        try:
            snapshot = self._repository.load_candidate_snapshot_record(
                board.run_id, target
            )
            profile = self._repository.load_profile(target)
            preferences = self._repository.load_profile_preferences(target)
            memory = self._repository.load_preference_memory(target)
            policy = self._repository.load_policy_snapshot(target)
            playback = self._repository.load_playback_snapshot(target)
        except Exception:
            snapshot = None
            profile = None
            preferences = None
            memory = None
            policy = None
            playback = None
            scoring_errors.append("support_context_load_failed")
        candidates = list(snapshot.candidates) if snapshot is not None else []
        preference_evidence: List[str] = []
        if profile is not None:
            preference_evidence.extend(profile.tags)
            preference_evidence.extend(profile.ranking_tags)

        context_ready = bool(snapshot is not None) and self._context_matches_board(
            target,
            board,
            policy,
            memory,
            playback,
        )
        if not context_ready:
            scoring_errors.append("support_context_unavailable")
            fallback = []
        else:
            fallback = self._validator.build_fallback_items(
                candidates,
                board.recommendations,
                blocked_candidate_ids=blocked,
                preference_evidence=preference_evidence,
                limit=RECOMMENDATION_LIMIT,
                policy_snapshot=policy,
                confirmed_memory=memory,
                profile_preferences=preferences,
                playback_snapshot=playback,
                scoring_errors=scoring_errors,
            )
        current_items = list(board.recommendations)
        if fallback:
            agent_order = {
                item.candidate_id: index
                for index, item in enumerate(current_items)
                if item.selection_source == "agent"
            }
            try:
                current_items = self._ranker.rank(
                    [*current_items, *fallback],
                    candidates,
                    agent_order=agent_order,
                )[:RECOMMENDATION_LIMIT]
            except Exception:
                scoring_errors.append("stable_ranking_failed")
                fallback = []
        for rank, item in enumerate(current_items, start=1):
            item.rank = rank
        board.recommendations = current_items

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
                f"{action_label}已生效；"
                + (
                    "同策略评分上下文不可用，无法安全补位，当前仅"
                    if scoring_errors
                    else "安全候选不足，当前仅"
                )
                + f" {len(board.recommendations)} 条"
            )
            status = "safe_candidate_insufficient"
        return BoardRefillResult(
            board=board,
            refill_count=len(fallback),
            status=status,
        )
