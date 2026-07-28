"""基于同轮冻结安全候选维护固定五条榜单。"""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from ..model.analysis import RecommendationAnalysis
from ..model.board import RecommendationBoard
from ..model.constants import RECOMMENDATION_LIMIT
from ..storage.repository import AgentRankRepository
from .analysis import RecommendationAnalysisBuilder
from .scoring import PolicyLearningService, StableRecommendationRanker
from .validation import RecommendationValidator


@dataclass(frozen=True)
class BoardRefillResult:
    """描述一次移除后的确定性安全补位结果。"""

    board: RecommendationBoard
    refill_count: int
    status: str
    analyses: List[RecommendationAnalysis]
    analysis_context_ready: bool

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
        analysis_builder: Optional[RecommendationAnalysisBuilder] = None,
    ):
        """绑定候选快照仓储与既有安全推荐验证器。"""
        self._repository = repository
        self._validator = validator or RecommendationValidator()
        self._ranker = ranker or StableRecommendationRanker()
        self._analysis_builder = analysis_builder or RecommendationAnalysisBuilder()

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

    @staticmethod
    def _matching_analyses(
        profile_id: str,
        board: RecommendationBoard,
        policy: object,
        analyses: Iterable[RecommendationAnalysis],
    ) -> Optional[Dict[str, RecommendationAnalysis]]:
        """校验榜单每条分析的身份、支持度与版本，并按候选返回。"""
        values = list(analyses or ())
        by_id = {item.analysis_id: item for item in values}
        if not board.recommendations or len(by_id) != len(values):
            return None
        matched: Dict[str, RecommendationAnalysis] = {}
        prompt_fingerprints = set()
        policy_version = str(getattr(policy, "policy_version", "") or "")
        memory_revision = int(getattr(policy, "memory_revision", -1))
        for item in board.recommendations:
            if item.support is None or not item.analysis_id:
                return None
            analysis = by_id.get(item.analysis_id)
            if analysis is None or any(
                (
                    analysis.profile_id != profile_id,
                    analysis.run_id != board.run_id,
                    analysis.candidate_id != item.candidate_id,
                    analysis.selection_source != item.selection_source,
                    analysis.summary != item.summary,
                    analysis.reason != item.reason,
                    analysis.policy_version != policy_version,
                    analysis.policy_version != item.support.policy_version,
                    analysis.memory_revision != memory_revision,
                    analysis.support_percentage != item.support.percentage,
                )
            ):
                return None
            if analysis.candidate_id in matched:
                return None
            matched[analysis.candidate_id] = analysis
            prompt_fingerprints.add(analysis.prompt_fingerprint)
        if len(prompt_fingerprints) != 1:
            return None
        return matched

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
            persisted_board = self._repository.load_board(target)
            snapshot = self._repository.load_candidate_snapshot_record(
                board.run_id, target
            )
            profile = self._repository.load_profile(target)
            preferences = self._repository.load_profile_preferences(target)
            memory = self._repository.load_preference_memory(target)
            policy = self._repository.load_policy_snapshot(target)
            playback = self._repository.load_playback_snapshot(target)
            stored_analyses = self._repository.load_recommendation_analyses(
                target, board.run_id
            )
        except Exception:
            persisted_board = None
            snapshot = None
            profile = None
            preferences = None
            memory = None
            policy = None
            playback = None
            stored_analyses = []
            scoring_errors.append("support_context_load_failed")
        candidates = list(snapshot.candidates) if snapshot is not None else []
        preference_evidence: List[str] = []
        if profile is not None:
            preference_evidence.extend(profile.tags)
            preference_evidence.extend(profile.ranking_tags)

        persisted_ids = {
            item.candidate_id
            for item in getattr(persisted_board, "recommendations", ())
        }
        current_ids = {item.candidate_id for item in board.recommendations}
        analysis_map = (
            self._matching_analyses(target, persisted_board, policy, stored_analyses)
            if persisted_board is not None
            and persisted_board.run_id == board.run_id
            else None
        )
        context_ready = bool(
            snapshot is not None
            and persisted_board is not None
            and current_ids.issubset(persisted_ids)
            and analysis_map is not None
            and self._context_matches_board(
                target,
                persisted_board,
                policy,
                memory,
                playback,
            )
        )
        pre_refill_items = list(board.recommendations)
        if not context_ready:
            scoring_errors.append("analysis_or_support_context_unavailable")
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
        current_items = list(pre_refill_items)
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
                current_items = list(pre_refill_items)

        visible_analyses: List[RecommendationAnalysis] = []
        if context_ready:
            prompt_fingerprint = next(
                iter({item.prompt_fingerprint for item in analysis_map.values()})
            )
            try:
                for item in current_items:
                    existing = analysis_map.get(item.candidate_id)
                    if existing is not None and existing.analysis_id == item.analysis_id:
                        visible_analyses.append(existing)
                        continue
                    generated = self._analysis_builder.build(
                        target,
                        board.run_id,
                        item,
                        policy,
                        prompt_fingerprint,
                    )
                    item.analysis_id = generated.analysis_id
                    visible_analyses.append(generated)
            except Exception:
                scoring_errors.append("recommendation_analysis_build_failed")
                context_ready = False
                fallback = []
                current_items = list(pre_refill_items)
                visible_analyses = []
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
            refill_count=len(
                {
                    item.candidate_id for item in board.recommendations
                }
                - {item.candidate_id for item in pre_refill_items}
            ),
            status=status,
            analyses=visible_analyses,
            analysis_context_ready=context_ready,
        )
