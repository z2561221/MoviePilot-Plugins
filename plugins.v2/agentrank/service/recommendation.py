"""按用户锁定的 Agent 榜单推荐编排服务。"""

import asyncio
import hashlib
import json
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from ..agent_tools.context import (
    FINAL_AGENT_ROLE,
    PRELIMINARY_AGENT_ROLE,
    PROFILE_AGENT_ROLE,
    RANKING_AGENT_ROLE,
    build_trusted_context,
)
from ..agent_tools.schemas import SubmitBatchResultInput
from ..model.candidate import typed_tmdb_candidate_id
from ..model.config import configured_identities
from ..model.feedback import ShortTermSignal
from ..model.constants import (
    RANKING_OUTPUT_LIMIT,
    RECOMMENDATION_LIMIT,
)
from ..model.board import RecommendationBoard, RecommendationItem
from ..model.judgment import JudgmentBatchCheckpoint, PreliminaryJudgment
from ..model.profile import (
    PROFILE_SCHEMA_VERSION,
    RETRIEVAL_RESOLUTION_VERSION,
    UserProfile,
)
from ..model.retrieval import RetrievalFilters, RetrievalPlan
from ..model.run import AdaptiveFingerprints, RecommendationRun
from ..model.policy import PolicySnapshot
from ..storage.repository import AgentRankRepository
from ..storage.judgment import JudgmentCheckpointStore
from .prompt import (
    DEFAULT_PROFILE_PROMPT,
    build_profile_prompt,
    build_preliminary_prompt,
    build_final_prompt,
    build_ranking_prompt,
    build_refill_prompt,
)
from .analysis import RecommendationAnalysisBuilder
from .keyword_resolution import (
    ControlledRetrievalPlanResolver,
    RetrievalPlanResolution,
)
from .feedback_action import FeedbackActionService
from .scoring import DeterministicSupportScorer, StableRecommendationRanker
from .tournament import (
    PreliminaryBatch,
    PreliminaryBatchResult,
    judgment_weights_fingerprint,
    partition_preliminary_batches,
    retrieval_fingerprint,
)
from .validation import (
    AgentOutputError,
    COPY_REWRITE_REASON_CODES,
    ProfileOutputParser,
    RankingOutputParser,
    RecommendationValidator,
)


logger = logging.getLogger(__name__)

_PROVENANCE_URL_PATTERN = re.compile(r"(?i)\b(?:https?|ftp)://[^\s]+")
_PROVENANCE_SECRET_PATTERN = re.compile(
    r"(?i)\b(?:authorization|cookie|api[_-]?key|llm[_-]?key|access[_-]?token|token)\b\s*[:=]\s*[^\s,;]+"
)
_PROVENANCE_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
_PROVENANCE_HOST_PORT_PATTERN = re.compile(
    r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}:\d{2,6}"
)

_BOARD_RECENCY_ROUND_WEIGHTS = (0.0, 0.35, 0.7, 1.0)
_BOARD_RECENCY_HISTORY_LIMIT = len(_BOARD_RECENCY_ROUND_WEIGHTS) - 1


def _safe_agent_failure_reason(value: Any) -> str:
    """把逐调用失败原因收敛为无地址和凭据的短文本。"""
    text = " ".join(str(value or "").split()).strip()
    text = _PROVENANCE_URL_PATTERN.sub("[已脱敏地址]", text)
    text = _PROVENANCE_HOST_PORT_PATTERN.sub("[已脱敏地址]", text)
    text = _PROVENANCE_BEARER_PATTERN.sub("[已脱敏凭据]", text)
    return _PROVENANCE_SECRET_PATTERN.sub("[已脱敏凭据]", text)[:240]


@dataclass
class RecommendationRunResult:
    """表示一次推荐请求的最终状态。"""

    profile_id: str
    run_id: str
    status: str
    username: str = ""
    message: str = ""
    final_count: int = 0
    agent_calls: int = 0
    board: Optional[RecommendationBoard] = None


@dataclass
class TournamentOutcome:
    """汇总初赛、决赛及安全补位边界。"""

    validation: Any = None
    agent_order: Dict[str, int] = None
    fallback_reason: str = ""
    errors: List[str] = None
    prompt_fingerprint_source: str = ""
    validation_drops: List[Dict[str, Any]] = None
    fallback_candidate_ids: List[str] = None


class RecommendationOrchestrator:
    """串联输入、候选、受限 Agent、校验、补选与原子保存。"""

    def __init__(
        self,
        repository: AgentRankRepository,
        candidate_service: Any,
        agent_adapter: Any,
        run_id_factory: Callable[[], str] = None,
        parser: Any = None,
        profile_parser: ProfileOutputParser = None,
        ranking_parser: RankingOutputParser = None,
        validator: RecommendationValidator = None,
        library_adapter: Any = None,
        playback_service: Any = None,
        retrieval_plan_resolver: Any = None,
        policy_service: Any = None,
        ranker: Any = None,
        analysis_builder: Any = None,
        progress_callback: Callable[[Mapping[str, Any]], Any] = None,
        judgment_store: Any = None,
        support_scorer: Any = None,
    ):
        """注入可测试的领域依赖并初始化用户锁集合。"""
        self._repository = repository
        self._candidate_service = candidate_service
        self.agent_adapter = agent_adapter
        self._run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)
        self._profile_parser = profile_parser or ProfileOutputParser()
        self._ranking_parser = (
            ranking_parser
            or parser
            or RankingOutputParser(max_recommendations=RANKING_OUTPUT_LIMIT)
        )
        self._validator = validator or RecommendationValidator()
        self._library_adapter = library_adapter
        self._playback_service = playback_service
        if policy_service is None:
            from .scoring import PolicyLearningService

            policy_service = PolicyLearningService(repository)
        self._policy_service = policy_service
        self._ranker = ranker or StableRecommendationRanker()
        self._analysis_builder = analysis_builder or RecommendationAnalysisBuilder()
        self._judgment_store = judgment_store or JudgmentCheckpointStore(repository)
        self._support_scorer = support_scorer or DeterministicSupportScorer()
        self._progress_callback = progress_callback
        self._retrieval_plan_resolver = (
            retrieval_plan_resolver or ControlledRetrievalPlanResolver()
        )
        self._running_profiles: Set[str] = set()
        self._running_guard = threading.Lock()

    def _enter_profile(self, profile_id: str) -> bool:
        """原子登记运行画像身份；已运行时返回假。"""
        with self._running_guard:
            if profile_id in self._running_profiles:
                return False
            self._running_profiles.add(profile_id)
            return True

    def _leave_profile(self, profile_id: str) -> None:
        """释放画像身份运行标记。"""
        with self._running_guard:
            self._running_profiles.discard(profile_id)

    async def _run_agent_role(
        self,
        role: str,
        prompt: str,
        trusted_context: Any,
    ) -> str:
        """调用指定角色 Agent，并拒绝跨角色上下文。"""
        if trusted_context.agent_role != role:
            raise ValueError("AgentRank role and trusted context do not match")
        method_name = {
            PROFILE_AGENT_ROLE: "run_profile",
            RANKING_AGENT_ROLE: "run_ranking",
            PRELIMINARY_AGENT_ROLE: "run_preliminary",
            FINAL_AGENT_ROLE: "run_final",
        }.get(role, "run")
        method = getattr(self.agent_adapter, method_name, None)
        if callable(method):
            return await method(prompt, trusted_context)
        return await self.agent_adapter.run(prompt, trusted_context)

    @staticmethod
    def _record_agent_provenance(
        metrics: Dict[str, Any],
        role: str,
        value: Any,
        *,
        stage: str,
        attempt: int,
        duration_ms: int,
    ) -> Dict[str, Any]:
        """把单次 Agent 调用的脱敏模型来源聚合进运行指标。"""
        raw = getattr(value, "provenance", None)
        if not isinstance(raw, Mapping):
            raw = getattr(value, "agentrank_provenance", None)
        if not isinstance(raw, Mapping):
            raw = {}

        def safe_text(key: str, fallback: str = "") -> str:
            """只读取约定字段并限制持久化文本长度。"""
            return str(raw.get(key) or fallback).strip()[:160]

        try:
            model_call_count = max(0, int(raw.get("model_call_count") or 0))
        except (TypeError, ValueError):
            model_call_count = 0
        try:
            repair_count = max(0, int(raw.get("repair_count") or 0))
        except (TypeError, ValueError):
            repair_count = 0
        entry = {
            "role": role,
            "provider_id": safe_text("provider_id"),
            "selected_provider_name": safe_text("selected_provider_name"),
            "provider": safe_text("provider"),
            "model": safe_text("model", "unknown"),
            "source": safe_text("source", "unknown"),
            "model_call_count": model_call_count,
            "repair_count": repair_count,
            "stage": str(stage or role).strip()[:32],
            "attempt": max(1, int(attempt or 1)),
            "duration_ms": max(0, int(duration_ms or 0)),
            "status": "pending",
            "failure_reason": "",
        }
        entries = metrics.setdefault("agent_provenance", [])
        entries.append(entry)
        metrics["model_call_count"] = int(metrics.get("model_call_count", 0) or 0) + model_call_count
        metrics[f"{role}_model_call_count"] = int(
            metrics.get(f"{role}_model_call_count", 0) or 0
        ) + model_call_count
        metrics["agent_repair_count"] = int(
            metrics.get("agent_repair_count", 0) or 0
        ) + repair_count
        metrics[f"{role}_repair_count"] = int(
            metrics.get(f"{role}_repair_count", 0) or 0
        ) + repair_count
        metrics[f"{role}_agent_model"] = entry["model"]
        metrics[f"{role}_agent_source"] = entry["source"]

        models = list(dict.fromkeys(item["model"] for item in entries))
        known_models = [model for model in models if model != "unknown"]
        metrics["agent_model"] = " / ".join(known_models or models)
        providers = list(
            dict.fromkeys(
                item["selected_provider_name"] or item["provider"]
                for item in entries
                if item["selected_provider_name"] or item["provider"]
            )
        )
        metrics["agent_provider"] = " / ".join(providers)
        sources = list(dict.fromkeys(item["source"] for item in entries))
        metrics["agent_model_source"] = (
            sources[0] if len(sources) == 1 else "mixed"
        )
        return entry

    @staticmethod
    def _finish_agent_provenance(
        entry: Optional[Dict[str, Any]], status: str, failure_reason: Any = ""
    ) -> None:
        """完成一条逐调用记录并仅保存安全失败摘要。"""
        if not isinstance(entry, dict):
            return
        entry["status"] = str(status or "failed").strip()[:32]
        entry["failure_reason"] = _safe_agent_failure_reason(failure_reason)

    @staticmethod
    def _display_name(profile_id: str, config: Mapping[str, Any]) -> str:
        """返回 profile_id 对应的 Emby 显示名。"""
        for identity in configured_identities(config):
            if identity.profile_id == profile_id:
                return identity.username
        return ""

    @staticmethod
    def _board_candidate_ids(board: Any) -> List[str]:
        """提取榜单中的规范候选身份。"""
        return [
            str(item.candidate_id or "").strip()
            for item in (getattr(board, "recommendations", ()) or ())
            if str(getattr(item, "candidate_id", "") or "").strip()
        ]

    def _board_recency_weights(
        self,
        profile_id: str,
        previous_board_candidate_ids: Iterable[str],
    ) -> Dict[str, float]:
        """按最近成功榜单轮次生成可解释的重复惩罚权重。"""
        weights: Dict[str, float] = {
            str(candidate_id or "").strip(): _BOARD_RECENCY_ROUND_WEIGHTS[0]
            for candidate_id in previous_board_candidate_ids or ()
            if str(candidate_id or "").strip()
        }
        try:
            history = self._repository.load_run_history(profile_id)
        except Exception:
            history = []
        previous_board_id_set = {
            str(candidate_id or "").strip()
            for candidate_id in previous_board_candidate_ids or ()
            if str(candidate_id or "").strip()
        }
        skipped_current_board_history = False
        observed_rounds = 0
        for run in history:
            metrics = dict(getattr(run, "metrics", {}) or {})
            candidate_ids = [
                str(candidate_id or "").strip()
                for candidate_id in metrics.get("recommendation_candidate_ids") or ()
                if str(candidate_id or "").strip()
            ]
            if not candidate_ids:
                continue
            if (
                previous_board_id_set
                and not skipped_current_board_history
                and set(candidate_ids) == previous_board_id_set
            ):
                skipped_current_board_history = True
                continue
            observed_rounds += 1
            if observed_rounds > _BOARD_RECENCY_HISTORY_LIMIT:
                break
            factor = _BOARD_RECENCY_ROUND_WEIGHTS[observed_rounds]
            for candidate_id in candidate_ids:
                weights.setdefault(candidate_id, factor)
        return weights

    @staticmethod
    def _board_recency_factor(
        candidate_id: Any, weights: Mapping[str, Any]
    ) -> float:
        """读取候选榜单新鲜度权重并限制在零到一。"""
        try:
            value = float((weights or {}).get(str(candidate_id or "").strip(), 1.0))
        except (TypeError, ValueError):
            value = 1.0
        return max(0.0, min(1.0, value))

    @classmethod
    def _order_candidates_by_board_recency(
        cls, candidates: Iterable[Any], weights: Mapping[str, Any]
    ) -> List[Any]:
        """按榜单新鲜度优先排序候选，并保留原始稳定顺序。"""
        indexed = list(enumerate(candidates or ()))
        indexed.sort(
            key=lambda item: (
                -cls._board_recency_factor(item[1].candidate_id, weights),
                item[0],
            )
        )
        return [candidate for _, candidate in indexed]

    @staticmethod
    def _soften_profile_media_types(
        plan: RetrievalPlan,
    ) -> Tuple[RetrievalPlan, Tuple[str, ...]]:
        """将画像推断的媒体类型转为排序标签，避免把偏好误作排他过滤。"""
        media_types = tuple(plan.filters.media_types)
        if not media_types:
            return plan, ()
        labels = {"movie": "电影", "tv": "电视剧", "anime": "动画"}
        ranking_tags = list(plan.ranking_tags)
        for media_type in media_types:
            tag = labels.get(media_type, media_type)
            if tag and tag not in ranking_tags:
                ranking_tags.append(tag)
        filters = plan.filters
        return RetrievalPlan(
            filters=RetrievalFilters(
                media_types=(),
                genre_ids=filters.genre_ids,
                keyword_ids=filters.keyword_ids,
                original_languages=filters.original_languages,
                year_min=filters.year_min,
                year_max=filters.year_max,
                rating_min=filters.rating_min,
                vote_count_min=filters.vote_count_min,
                sort_by=filters.sort_by,
            ),
            ranking_tags=tuple(ranking_tags),
        ), media_types

    @staticmethod
    def _trusted_weights(
        config: Mapping[str, Any],
        policy: PolicySnapshot = None,
        confirmed_memory: Any = None,
        profile_preferences: Any = None,
        playback_snapshot: Any = None,
    ) -> Dict[str, Any]:
        """选择 Agent 允许读取的权重和筛选配置。"""
        values = {
            "weights": (
                dict(policy.effective_weights)
                if policy is not None
                else dict(config.get("weights") or {})
            ),
            "candidate_pool_size": int(config.get("candidate_pool_size") or 15),
        }
        if policy is not None:
            values.update(
                {
                    "base_weights": dict(policy.base_weights),
                    "learned_deltas": dict(policy.learned_deltas),
                    "evidence_certainty": dict(policy.evidence_certainty),
                    "policy_version": policy.policy_version,
                    "memory_revision": policy.memory_revision,
                    "confirmed_preferences": [
                        {
                            "category": item.category,
                            "value": item.value,
                            "polarity": item.polarity,
                            "strength": item.strength,
                            "certainty": item.certainty,
                            "evidence_refs": [f"memory:{item.item_id}"],
                        }
                        for item in (
                            confirmed_memory.active_items()
                            if confirmed_memory is not None
                            else ()
                        )
                    ],
                    "evidence_catalog": (
                        DeterministicSupportScorer.trusted_signal_catalog(
                            confirmed_memory,
                            profile_preferences,
                            playback_snapshot,
                        )
                        if confirmed_memory is not None
                        and profile_preferences is not None
                        and playback_snapshot is not None
                        else []
                    ),
                }
            )
        return values

    @staticmethod
    def _profile_cache_reason(
        enabled: bool,
        forced_rebuild: bool,
        previous_profile: Optional[UserProfile],
        playback_fingerprint: str,
        preferences_fingerprint: str,
        profile_prompt_fingerprint: str,
        profile_input_fingerprint: str,
    ) -> str:
        """返回画像缓存命中或未命中的稳定原因码。"""
        if not enabled:
            return "disabled"
        if forced_rebuild:
            return "forced_rebuild"
        if previous_profile is None:
            return "missing"
        if previous_profile.schema_version < PROFILE_SCHEMA_VERSION:
            return "profile_schema_changed"
        if (
            previous_profile.retrieval_resolution_version
            < RETRIEVAL_RESOLUTION_VERSION
        ):
            return "retrieval_resolution_changed"
        if previous_profile.playback_fingerprint != playback_fingerprint:
            return "playback_changed"
        if previous_profile.preferences_fingerprint != preferences_fingerprint:
            return "preferences_changed"
        if previous_profile.profile_prompt_fingerprint != profile_prompt_fingerprint:
            return "profile_prompt_changed"
        if previous_profile.profile_input_fingerprint != profile_input_fingerprint:
            return "profile_input_changed"
        return "hit"

    @staticmethod
    def _playback_evidence_fingerprints(playback_snapshot: Any) -> Dict[str, str]:
        """按稳定样本身份计算逐条播放事实指纹。"""
        result: Dict[str, str] = {}
        for sample in list(getattr(playback_snapshot, "samples", ()) or ()):
            payload = sample.to_dict() if hasattr(sample, "to_dict") else dict(sample)
            stable_id = str(payload.get("stable_id") or "").strip()
            if not stable_id:
                continue
            raw = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            result[stable_id] = hashlib.sha256(raw).hexdigest()
        return result

    @staticmethod
    def _profile_input_fingerprint(
        playback_fingerprint: str,
        preferences_fingerprint: str,
        confirmed_memory: Any,
        config: Mapping[str, Any],
    ) -> str:
        """计算播放事实、确认偏好和画像规则组成的完整输入指纹。"""
        memory = (
            confirmed_memory.to_dict()
            if confirmed_memory is not None and hasattr(confirmed_memory, "to_dict")
            else {}
        )
        payload = {
            "playback_fingerprint": playback_fingerprint,
            "preferences_fingerprint": preferences_fingerprint,
            "confirmed_memory": memory,
            "profile_config": {
                "profile_prompt": str(config.get("profile_prompt") or ""),
                "playback_recent_days": int(config.get("playback_recent_days") or 90),
                "playback_completion_threshold": float(
                    config.get("playback_completion_threshold") or 0.85
                ),
                "playback_abandon_minutes": int(
                    config.get("playback_abandon_minutes") or 20
                ),
                "minimum_samples": int(config.get("minimum_samples") or 5),
            },
        }
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def _incremental_playback_context(
        cls,
        playback_snapshot: Any,
        previous_profile: Optional[UserProfile],
    ) -> tuple[Dict[str, Any], Dict[str, str]]:
        """为画像 Agent 返回全量首轮或只含变化样本的增量播放上下文。"""
        payload = dict(playback_snapshot.to_dict())
        fingerprints = cls._playback_evidence_fingerprints(playback_snapshot)
        previous = dict(
            getattr(previous_profile, "playback_evidence_fingerprints", {}) or {}
        )
        if previous_profile is None or not previous:
            payload["incremental"] = False
            payload["removed_stable_ids"] = []
            return payload, fingerprints
        changed_ids = {
            stable_id
            for stable_id, fingerprint in fingerprints.items()
            if previous.get(stable_id) != fingerprint
        }
        payload["samples"] = [
            sample
            for sample in payload.get("samples") or []
            if str(sample.get("stable_id") or "") in changed_ids
        ]
        payload["incremental"] = True
        payload["full_sample_count"] = int(getattr(playback_snapshot, "sample_count", 0))
        payload["removed_stable_ids"] = sorted(set(previous) - set(fingerprints))
        return payload, fingerprints

    def _publish_progress(
        self,
        metrics: Mapping[str, Any],
        stage: str,
        message: str = "",
    ) -> None:
        """发布只含运行身份和阶段的安全实时进度。"""
        callback = self._progress_callback
        if not callable(callback):
            return
        payload = {
            "profile_id": str(metrics.get("_profile_id") or ""),
            "run_id": str(metrics.get("_run_id") or ""),
            "stage": str(stage or ""),
        }
        if message:
            payload["message"] = str(message)[:120]
        try:
            callback(payload)
        except Exception:
            logger.exception("AgentRank 实时进度回调失败 stage=%s", stage)

    def _start_stage(self, metrics: Dict[str, Any], stage: str) -> None:
        """开始一个可审计运行阶段，并记录稳定执行顺序。"""
        if metrics.get("_stage_name"):
            raise RuntimeError("previous recommendation stage is still active")
        metrics.setdefault("stage_order", []).append(stage)
        metrics["_stage_name"] = stage
        metrics["_stage_started_at"] = time.monotonic()
        self._publish_progress(metrics, stage)

    @staticmethod
    def _finish_stage(metrics: Dict[str, Any], status: str) -> None:
        """完成当前运行阶段并记录毫秒耗时和安全状态。"""
        stage = str(metrics.pop("_stage_name", "") or "")
        started_at = metrics.pop("_stage_started_at", None)
        if not stage:
            return
        elapsed_ms = (
            max(0, int((time.monotonic() - started_at) * 1000))
            if isinstance(started_at, (int, float))
            else 0
        )
        metrics.setdefault("stage_status", {})[stage] = str(status)
        metrics.setdefault("stage_ms", {})[stage] = elapsed_ms

    @staticmethod
    def _record_retry(
        metrics: Dict[str, Any], stage: str, attempt: int, error: BaseException
    ) -> None:
        """记录一次已进入重试的瞬时失败，不把它伪装成最终运行错误。"""
        stage_name = str(stage or "agent")
        metrics.setdefault("retry_events", []).append(
            {
                "stage": stage_name,
                "attempt": int(attempt),
                "reason": str(error)[:240],
            }
        )
        counter_key = f"{stage_name}_retry_count"
        metrics[counter_key] = int(metrics.get(counter_key, 0) or 0) + 1

    def _append_run(
        self,
        profile_id: str,
        username: str,
        run_id: str,
        status: str,
        started_at: str,
        started_clock: float,
        message: str,
        errors: List[str],
        metrics: Dict[str, Any],
    ) -> None:
        """写入包含耗时和关键计数的有界运行历史。"""
        final_metrics = dict(metrics)
        final_metrics.pop("_stage_name", None)
        final_metrics.pop("_stage_started_at", None)
        final_metrics.pop("_profile_id", None)
        final_metrics.pop("_run_id", None)
        final_metrics["elapsed_ms"] = max(0, int((time.monotonic() - started_clock) * 1000))
        self._repository.append_run(
            RecommendationRun(
                profile_id=profile_id,
                username=username,
                run_id=run_id,
                status=status,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
                message=message,
                errors=list(errors),
                metrics=final_metrics,
            )
        )

    def _exclude_library_candidates(
        self, candidates: List[Any]
    ) -> tuple[List[Any], List[Any]]:
        """同步检查媒体库并返回保留候选与已存在候选。"""
        if self._library_adapter is None:
            return list(candidates), []
        excluded = [
            candidate
            for candidate in candidates
            if self._library_adapter.exists(candidate)
        ]
        excluded_ids = {item.candidate_id for item in excluded}
        remaining = [
            candidate
            for candidate in candidates
            if candidate.candidate_id not in excluded_ids
        ]
        return remaining, excluded

    @staticmethod
    def _archive_candidate_ids(archive: Any) -> Set[str]:
        """从新旧归档载荷中提取可证明类型的 TMDB 身份。"""
        result: Set[str] = set()
        for entry in getattr(archive, "entries", []) or []:
            candidate_id = str(getattr(entry, "candidate_id", "") or "").strip()
            try:
                result.add(typed_tmdb_candidate_id(candidate_id))
                continue
            except ValueError:
                pass
            recommendation = getattr(entry, "recommendation", {}) or {}
            if not isinstance(recommendation, Mapping):
                continue
            source_ids = recommendation.get("source_ids") or {}
            metadata = recommendation.get("metadata") or {}
            try:
                result.add(
                    typed_tmdb_candidate_id(
                        source_ids.get("tmdb"),
                        recommendation.get("media_type"),
                        metadata.get("mp_media_type"),
                    )
                )
            except (AttributeError, ValueError):
                continue
        return result

    def _failure(
        self,
        profile_id: str,
        username: str,
        run_id: str,
        status: str,
        message: str,
        started_at: str,
        started_clock: float,
        metrics: Dict[str, Any],
        errors: List[str],
        agent_calls: int = 0,
    ) -> RecommendationRunResult:
        """记录失败并返回旧榜单，不覆盖当前画像。"""
        self._finish_stage(metrics, status)
        metrics["agent_calls"] = agent_calls
        metrics["final_count"] = 0
        self._append_run(
            profile_id,
            username,
            run_id,
            status,
            started_at,
            started_clock,
            message,
            errors,
            metrics,
        )
        old_board = self._repository.load_board(profile_id)
        return RecommendationRunResult(
            profile_id=profile_id,
            username=username,
            run_id=run_id,
            status=status,
            message=message,
            agent_calls=agent_calls,
            board=old_board,
        )

    def _uses_tournament_protocol(self) -> bool:
        """生产适配器必须同时实现初赛和决赛终结角色。"""
        return all(
            callable(getattr(self.agent_adapter, name, None))
            for name in ("run_preliminary", "run_final")
        )

    def _rank_final_items(
        self,
        items: List[RecommendationItem],
        candidates: List[Any],
        agent_order: Mapping[str, int],
        *,
        preserve_agent_order: bool,
    ) -> List[RecommendationItem]:
        """保留有效决赛顺序，并只对安全补位项做确定性排序。"""
        values = list(items or ())
        trusted_order = {
            str(candidate_id): int(index)
            for candidate_id, index in dict(agent_order or {}).items()
        }
        if not preserve_agent_order or not trusted_order:
            return self._ranker.rank(values, candidates, agent_order=trusted_order)
        agent_items = [
            item for item in values if item.candidate_id in trusted_order
        ]
        agent_items.sort(key=lambda item: trusted_order[item.candidate_id])
        fallback_items = [
            item for item in values if item.candidate_id not in trusted_order
        ]
        if fallback_items:
            fallback_items = self._ranker.rank(fallback_items, candidates)
        ranked = [*agent_items, *fallback_items]
        for index, item in enumerate(ranked, start=1):
            item.rank = index
        return ranked

    async def _run_preliminary_batch(
        self,
        *,
        profile_id: str,
        run_id: str,
        username: str,
        batch: PreliminaryBatch,
        profile_fingerprint: str,
        retrieval_plan_fingerprint: str,
        ranking_profile: Mapping[str, Any],
        trusted_weights: Mapping[str, Any],
        metrics: Dict[str, Any],
    ) -> PreliminaryBatchResult:
        """运行一个初赛批次，成功即持久化，失败后只读同指纹检查点。"""
        cached = self._judgment_store.load(profile_id, batch.idempotency_key)
        if cached is not None:
            return PreliminaryBatchResult(
                batch=batch,
                status="cache_hit",
                judgments=list(cached.judgments),
            )
        context = build_trusted_context(
            username=username,
            run_id=f"{run_id}-{batch.batch_id}",
            candidates=[item.to_dict() for item in batch.candidates],
            archive_feedback={"entries": []},
            weights=trusted_weights,
            profile=ranking_profile,
            agent_role=PRELIMINARY_AGENT_ROLE,
            submission_constraints={"advance_quota": batch.advance_quota},
        )
        call_entry: Optional[Dict[str, Any]] = None
        stage_clock = time.monotonic()
        metrics["agent_calls"] = int(metrics.get("agent_calls", 0) or 0) + 1
        metrics["preliminary_agent_calls"] = int(
            metrics.get("preliminary_agent_calls", 0) or 0
        ) + 1
        try:
            raw = await self._run_agent_role(
                PRELIMINARY_AGENT_ROLE,
                build_preliminary_prompt(),
                context,
            )
            duration_ms = max(0, int((time.monotonic() - stage_clock) * 1000))
            metrics["agent_ms"] = int(metrics.get("agent_ms", 0) or 0) + duration_ms
            call_entry = self._record_agent_provenance(
                metrics,
                PRELIMINARY_AGENT_ROLE,
                raw,
                stage=batch.batch_id,
                attempt=1,
                duration_ms=duration_ms,
            )
            parsed = SubmitBatchResultInput.model_validate_json(str(raw))
            judgments = [
                PreliminaryJudgment.from_dict(item.model_dump(mode="json"))
                for item in parsed.judgments
            ]
            expected_ids = {
                str(item.candidate_id) for item in batch.candidates
            }
            actual_ids = [item.candidate_id for item in judgments]
            if len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != expected_ids:
                raise AgentOutputError(
                    "preliminary judgments must cover the exact batch candidate set"
                )
            if sum(item.advance for item in judgments) > batch.advance_quota:
                raise AgentOutputError("preliminary advance quota exceeded")
            checkpoint = JudgmentBatchCheckpoint(
                profile_id=profile_id,
                batch_id=batch.batch_id,
                idempotency_key=batch.idempotency_key,
                profile_fingerprint=profile_fingerprint,
                retrieval_fingerprint=retrieval_plan_fingerprint,
                weights_fingerprint=batch.weights_fingerprint,
                candidate_fingerprint=batch.candidate_fingerprint,
                judgments=judgments,
            )
            saved = self._judgment_store.save(checkpoint)
            self._finish_agent_provenance(call_entry, "completed")
            return PreliminaryBatchResult(
                batch=batch,
                status="agent",
                judgments=list(saved.judgments),
            )
        except Exception as error:
            duration_ms = max(0, int((time.monotonic() - stage_clock) * 1000))
            if call_entry is None:
                call_entry = self._record_agent_provenance(
                    metrics,
                    PRELIMINARY_AGENT_ROLE,
                    error,
                    stage=batch.batch_id,
                    attempt=1,
                    duration_ms=duration_ms,
                )
                metrics["agent_ms"] = int(metrics.get("agent_ms", 0) or 0) + duration_ms
            self._finish_agent_provenance(call_entry, "failed", error)
            cached = self._judgment_store.load(profile_id, batch.idempotency_key)
            if cached is not None:
                return PreliminaryBatchResult(
                    batch=batch,
                    status="cache_recovered",
                    judgments=list(cached.judgments),
                    error=_safe_agent_failure_reason(error),
                )
            return PreliminaryBatchResult(
                batch=batch,
                status="failed",
                error=_safe_agent_failure_reason(error),
            )

    def _support_fill_candidates(
        self,
        candidates: List[Any],
        quota: int,
        *,
        policy_snapshot: PolicySnapshot,
        confirmed_memory: Any,
        profile_preferences: Any,
        playback_snapshot: Any,
        errors: List[str],
    ) -> List[Tuple[Any, int]]:
        """只为失败批次补决赛席位，不决定最终 Top 5 顺序。"""
        scored: List[Tuple[int, int, Any, int]] = []
        for index, candidate in enumerate(candidates):
            try:
                result = self._support_scorer.score_candidate(
                    candidate,
                    policy_snapshot,
                    (),
                    (),
                    confirmed_memory,
                    profile_preferences,
                    playback_snapshot,
                )
                net_units = int(result.score.net_units)
                percentage = int(result.score.percentage)
            except Exception as error:
                errors.append(
                    f"preliminary safe fill {candidate.candidate_id}: "
                    f"{_safe_agent_failure_reason(error)}"
                )
                net_units = -(10**18)
                percentage = 0
            scored.append((net_units, -index, candidate, percentage))
        scored.sort(key=lambda item: (-item[0], -item[1], item[2].candidate_id))
        return [
            (candidate, max(0, min(100, percentage)))
            for _, _, candidate, percentage in scored[: max(0, int(quota))]
        ]

    async def _run_tournament(
        self,
        *,
        profile_id: str,
        run_id: str,
        username: str,
        candidates: List[Any],
        current_profile: UserProfile,
        ranking_profile: Mapping[str, Any],
        trusted_weights: Mapping[str, Any],
        policy_snapshot: PolicySnapshot,
        confirmed_memory: Any,
        profile_preferences: Any,
        playback_snapshot: Any,
        archived_ids: Set[str],
        disliked_ids: Set[str],
        subscribed_ids: Set[str],
        config: Mapping[str, Any],
        metrics: Dict[str, Any],
        previous_board_candidate_ids: Optional[Iterable[str]] = None,
        board_recency_weights: Optional[Mapping[str, Any]] = None,
    ) -> TournamentOutcome:
        """并行初赛、批次恢复、席位补齐和独立决赛。"""
        board_recency_weights = dict(board_recency_weights or {})
        profile_fingerprint = str(current_profile.profile_input_fingerprint or "")
        if not profile_fingerprint:
            profile_fingerprint = hashlib.sha256(
                json.dumps(
                    current_profile.to_dict(),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        retrieval_plan_fingerprint = retrieval_fingerprint(current_profile)
        weights_fingerprint = judgment_weights_fingerprint(trusted_weights)
        batches = partition_preliminary_batches(
            candidates,
            profile_fingerprint,
            retrieval_plan_fingerprint,
            weights_fingerprint,
        )
        metrics["preliminary_batch_count"] = len(batches)
        metrics["preliminary_candidate_count"] = len(candidates)
        stage_clock = time.monotonic()
        results = await asyncio.gather(
            *[
                self._run_preliminary_batch(
                    profile_id=profile_id,
                    run_id=run_id,
                    username=username,
                    batch=batch,
                    profile_fingerprint=profile_fingerprint,
                    retrieval_plan_fingerprint=retrieval_plan_fingerprint,
                    ranking_profile=ranking_profile,
                    trusted_weights=trusted_weights,
                    metrics=metrics,
                )
                for batch in batches
            ]
        )
        metrics["preliminary_ms"] = max(
            0, int((time.monotonic() - stage_clock) * 1000)
        )
        results.sort(key=lambda item: item.batch.index)
        metrics["preliminary_batch_statuses"] = [
            {
                "batch_id": item.batch.batch_id,
                "status": item.status,
                "candidate_count": len(item.batch.candidates),
            }
            for item in results
        ]
        metrics["preliminary_cache_hit_count"] = sum(
            item.status in {"cache_hit", "cache_recovered"} for item in results
        )
        metrics["preliminary_failed_count"] = sum(
            item.status == "failed" for item in results
        )
        metrics["judgment_card_cache_hit_count"] = metrics[
            "preliminary_cache_hit_count"
        ]

        finalist_pairs: List[Tuple[Any, Dict[str, Any]]] = []
        processing: Dict[str, Dict[str, Any]] = {}
        tournament_errors: List[str] = []
        safe_fill_count = 0
        for result in results:
            candidate_by_id = {
                item.candidate_id: item for item in result.batch.candidates
            }
            if result.judgments:
                indexed = list(enumerate(result.judgments))
                indexed.sort(
                    key=lambda item: (
                        not item[1].advance,
                        -(
                            float(item[1].fit_score)
                            * self._board_recency_factor(
                                item[1].candidate_id,
                                board_recency_weights,
                            )
                        ),
                        -item[1].fit_score,
                        item[0],
                    )
                )
                selected = indexed[: result.batch.advance_quota]
                selected_ids = {item.candidate_id for _, item in selected}
                for judgment in result.judgments:
                    processing[judgment.candidate_id] = {
                        "batch_id": result.batch.batch_id,
                        "status": result.status,
                        "selected": judgment.candidate_id in selected_ids,
                    }
                for _, judgment in selected:
                    finalist_pairs.append(
                        (candidate_by_id[judgment.candidate_id], judgment.to_dict())
                    )
            else:
                if result.error:
                    tournament_errors.append(
                        f"{result.batch.batch_id}: {result.error}"
                    )
                filled = self._support_fill_candidates(
                    result.batch.candidates,
                    result.batch.advance_quota,
                    policy_snapshot=policy_snapshot,
                    confirmed_memory=confirmed_memory,
                    profile_preferences=profile_preferences,
                    playback_snapshot=playback_snapshot,
                    errors=tournament_errors,
                )
                filled_ids = {candidate.candidate_id for candidate, _ in filled}
                safe_fill_count += len(filled)
                for candidate in result.batch.candidates:
                    processing[candidate.candidate_id] = {
                        "batch_id": result.batch.batch_id,
                        "status": "failed",
                        "selected": candidate.candidate_id in filled_ids,
                    }
                for candidate, percentage in filled:
                    finalist_pairs.append(
                        (
                            candidate,
                            {
                                "candidate_id": candidate.candidate_id,
                                "fit_score": percentage,
                                "positive_evidence": [],
                                "counter_evidence": None,
                                "advance": True,
                                "source": "safe_fill",
                            },
                        )
                    )
        evidence_options_by_id: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
        evidence_eligible_ids: Set[str] = set()
        for candidate in candidates:
            try:
                options = self._support_scorer.verified_evidence_options(
                    candidate,
                    policy_snapshot,
                    confirmed_memory,
                    profile_preferences,
                    playback_snapshot,
                )
            except Exception as error:
                tournament_errors.append(
                    f"final evidence {candidate.candidate_id}: "
                    f"{_safe_agent_failure_reason(error)}"
                )
                continue
            evidence_options_by_id[candidate.candidate_id] = options
            if len(options.get("positive_evidence_options") or ()) >= 2:
                evidence_eligible_ids.add(candidate.candidate_id)

        eligible_finalist_pairs = [
            pair
            for pair in finalist_pairs
            if pair[0].candidate_id in evidence_eligible_ids
        ]
        selected_finalist_ids = {
            candidate.candidate_id for candidate, _ in eligible_finalist_pairs
        }
        evidence_fill_quota = max(0, len(evidence_eligible_ids) - len(eligible_finalist_pairs))
        evidence_fill = self._support_fill_candidates(
            [
                candidate
                for candidate in candidates
                if candidate.candidate_id in evidence_eligible_ids
                and candidate.candidate_id not in selected_finalist_ids
            ],
            evidence_fill_quota,
            policy_snapshot=policy_snapshot,
            confirmed_memory=confirmed_memory,
            profile_preferences=profile_preferences,
            playback_snapshot=playback_snapshot,
            errors=tournament_errors,
        )
        evidence_fill_pairs = [
            (
                candidate,
                {
                    "candidate_id": candidate.candidate_id,
                    "fit_score": percentage,
                    "positive_evidence": [],
                    "counter_evidence": None,
                    "advance": True,
                    "source": "evidence_fill",
                },
            )
            for candidate, percentage in evidence_fill
        ]
        previous_board_candidate_ids = [
            str(candidate_id or "").strip()
            for candidate_id in (previous_board_candidate_ids or ())
            if str(candidate_id or "").strip()
        ]
        previous_board_id_set = set(previous_board_candidate_ids)
        finalist_pool = [*eligible_finalist_pairs, *evidence_fill_pairs]
        if previous_board_id_set:
            # 上一榜候选是本轮强重复项，更早榜单只按权重衰减，不写负向记忆。
            finalist_pool = [
                *[
                    pair
                    for pair in finalist_pool
                    if pair[0].candidate_id not in previous_board_id_set
                ],
                *[
                    pair
                    for pair in finalist_pool
                    if pair[0].candidate_id in previous_board_id_set
                ],
            ]
        indexed_finalist_pool = list(enumerate(finalist_pool))
        indexed_finalist_pool.sort(
            key=lambda item: (
                -self._board_recency_factor(
                    item[1][0].candidate_id,
                    board_recency_weights,
                ),
                item[0],
            )
        )
        finalist_pool = [pair for _, pair in indexed_finalist_pool]
        selected_pairs: List[Tuple[Any, Dict[str, Any]]] = []
        selected_ids: Set[str] = set()
        for pair in finalist_pool:
            candidate_id = pair[0].candidate_id
            if candidate_id in selected_ids:
                continue
            selected_pairs.append(pair)
            selected_ids.add(candidate_id)
            if len(selected_pairs) >= 6:
                break
        if len(selected_pairs) < 6:
            for pair in finalist_pool:
                candidate_id = pair[0].candidate_id
                if candidate_id in selected_ids:
                    continue
                selected_pairs.append(pair)
                selected_ids.add(candidate_id)
                if len(selected_pairs) >= 6:
                    break
        metrics["evidence_eligible_candidate_count"] = len(evidence_eligible_ids)
        metrics["evidence_ineligible_candidate_count"] = (
            len(candidates) - len(evidence_eligible_ids)
        )
        finalist_pairs = selected_pairs[:6]
        finalists = [candidate for candidate, _ in finalist_pairs]
        judgment_cards = [card for _, card in finalist_pairs]
        used_preliminary_ids = {
            candidate.candidate_id for candidate, _ in eligible_finalist_pairs
        }
        metrics["final_evidence_fill_count"] = sum(
            candidate.candidate_id not in used_preliminary_ids
            for candidate in finalists
        )
        finalist_new_count = sum(
            candidate.candidate_id not in previous_board_id_set
            for candidate in finalists
        )
        available_new_count = sum(
            candidate.candidate_id not in previous_board_id_set
            for candidate in candidates
        )
        minimum_new_items = (
            min(RECOMMENDATION_LIMIT, available_new_count)
            if previous_board_id_set
            else 0
        )
        maximum_previous_items = max(0, RECOMMENDATION_LIMIT - minimum_new_items)
        freshness_status = (
            "not_applicable"
            if not previous_board_id_set
            else "applied"
            if minimum_new_items >= RECOMMENDATION_LIMIT
            else "insufficient_candidates"
        )
        metrics["previous_board_candidate_count"] = len(previous_board_id_set)
        metrics["finalist_previous_candidate_count"] = (
            len(finalists) - finalist_new_count
        )
        metrics["finalist_new_candidate_count"] = finalist_new_count
        metrics["freshness_minimum_new_items"] = minimum_new_items
        metrics["freshness_maximum_previous_items"] = maximum_previous_items
        metrics["freshness_status"] = freshness_status
        metrics["freshness_shortfall_reason"] = (
            "eligible_new_candidates_insufficient"
            if freshness_status == "insufficient_candidates"
            else ""
        )
        expected_count = min(RECOMMENDATION_LIMIT, len(finalists))
        fallback_candidate_ids = [candidate.candidate_id for candidate in finalists]
        final_evidence_options = {
            candidate.candidate_id: evidence_options_by_id[candidate.candidate_id]
            for candidate in finalists
        }
        final_candidate_refs = {
            candidate.candidate_id: f"c{index}"
            for index, candidate in enumerate(finalists, start=1)
        }
        metrics["candidate_preliminary_status"] = processing
        metrics["preliminary_safe_fill_count"] = safe_fill_count
        metrics["finalist_count"] = len(finalists)
        metrics["final_input_fingerprint"] = hashlib.sha256(
            json.dumps(
                {
                    "profile_fingerprint": profile_fingerprint,
                    "retrieval_fingerprint": retrieval_plan_fingerprint,
                    "weights_fingerprint": weights_fingerprint,
                    "candidate_ids": [item.candidate_id for item in finalists],
                    "judgment_cards": judgment_cards,
                    "previous_board_candidate_ids": previous_board_candidate_ids,
                    "minimum_new_items": minimum_new_items,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        metrics["final_input_source"] = (
            "cached_judgments"
            if results
            and all(
                item.status in {"cache_hit", "cache_recovered"}
                for item in results
            )
            else "current_judgments"
        )
        if len(processing) != len(candidates):
            raise RuntimeError("preliminary processing coverage is incomplete")

        final_context = build_trusted_context(
            username=username,
            run_id=f"{run_id}-final",
            candidates=[item.to_dict() for item in finalists],
            archive_feedback={"entries": []},
            weights=trusted_weights,
            profile=ranking_profile,
            judgment_cards=judgment_cards,
            agent_role=FINAL_AGENT_ROLE,
            submission_constraints={
                "top_n": expected_count,
                "allowed_candidate_ids": fallback_candidate_ids,
                "candidate_refs": final_candidate_refs,
                "evidence_options": final_evidence_options,
                "previous_board_candidate_ids": previous_board_candidate_ids,
                "minimum_new_items": minimum_new_items,
                "maximum_previous_items": maximum_previous_items,
                "freshness_status": freshness_status,
            },
        )
        base_prompt = build_final_prompt(
            copy_prompt=str(config.get("copy_prompt") or ""),
            ranking_prompt=str(config.get("ranking_prompt") or ""),
        )
        last_reason = "final_agent_failed"
        last_retry_code = "final_agent_failed"
        last_retry_field = "submission"
        last_drop_feedback: List[Dict[str, Any]] = []
        final_validation_drops: List[Dict[str, Any]] = []
        retry_allowed_candidate_ids = list(fallback_candidate_ids)
        final_stage_clock = time.monotonic()
        for attempt in range(2):
            prompt = base_prompt
            attempt_context = final_context
            if attempt:
                feedback = json.dumps(
                    last_drop_feedback,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                retry_options = {
                    candidate_id: final_evidence_options.get(candidate_id, {})
                    for candidate_id in retry_allowed_candidate_ids
                }
                allowed_ids_text = json.dumps(
                    retry_allowed_candidate_ids,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                options_text = json.dumps(
                    retry_options,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                prompt += (
                    f"\nAGENTRANK_FINAL_RETRY code={last_retry_code} "
                    f"field={last_retry_field}. "
                    "只修正上一次提交中列出的字段问题，并重新提交完整 Top 5。"
                    f"上次校验反馈={feedback}。"
                    f"allowed_candidate_ids={allowed_ids_text}。"
                    f"allowed_candidate_refs={json.dumps([final_candidate_refs.get(item, '') for item in retry_allowed_candidate_ids], ensure_ascii=False, separators=(',', ':'))}。"
                    f"candidate_ref_map={json.dumps({final_candidate_refs.get(item, ''): item for item in retry_allowed_candidate_ids}, ensure_ascii=False, separators=(',', ':'))}。"
                    "必须原样保留这些候选短引用及其顺序，禁止新增、替换或重排。"
                    f"合法证据选项={options_text}。"
                )
                allowed_id_set = set(retry_allowed_candidate_ids)
                attempt_context = build_trusted_context(
                    username=username,
                    run_id=f"{run_id}-final-retry",
                    candidates=[
                        item.to_dict()
                        for item in finalists
                        if item.candidate_id in allowed_id_set
                    ],
                    archive_feedback={"entries": []},
                    weights=trusted_weights,
                    profile=ranking_profile,
                    judgment_cards=[
                        card
                        for card in judgment_cards
                        if str(card.get("candidate_id") or "") in allowed_id_set
                    ],
                    agent_role=FINAL_AGENT_ROLE,
                    submission_constraints={
                        "top_n": expected_count,
                        "allowed_candidate_ids": retry_allowed_candidate_ids,
                        "candidate_refs": final_candidate_refs,
                        "evidence_options": retry_options,
                        "previous_board_candidate_ids": previous_board_candidate_ids,
                        "minimum_new_items": minimum_new_items,
                        "maximum_previous_items": maximum_previous_items,
                        "freshness_status": freshness_status,
                    },
                )
                metrics["final_retry_count"] = int(
                    metrics.get("final_retry_count", 0) or 0
                ) + 1
            stage_clock = time.monotonic()
            metrics["agent_calls"] = int(metrics.get("agent_calls", 0) or 0) + 1
            metrics["final_agent_calls"] = int(
                metrics.get("final_agent_calls", 0) or 0
            ) + 1
            call_entry: Optional[Dict[str, Any]] = None
            try:
                raw = await self._run_agent_role(
                    FINAL_AGENT_ROLE, prompt, attempt_context
                )
                duration_ms = max(
                    0, int((time.monotonic() - stage_clock) * 1000)
                )
                metrics["agent_ms"] = int(metrics.get("agent_ms", 0) or 0) + duration_ms
                call_entry = self._record_agent_provenance(
                    metrics,
                    FINAL_AGENT_ROLE,
                    raw,
                    stage="final",
                    attempt=attempt + 1,
                    duration_ms=duration_ms,
                )
                parsed = self._ranking_parser.parse(raw)
                validation = self._validator.validate(
                    parsed,
                    finalists,
                    archived_ids,
                    subscribed_ids,
                    preference_evidence=[
                        *current_profile.tags,
                        *current_profile.ranking_tags,
                    ],
                    playback_samples=playback_snapshot.samples,
                    disliked_candidate_ids=disliked_ids,
                    policy_snapshot=policy_snapshot,
                    confirmed_memory=confirmed_memory,
                    profile_preferences=profile_preferences,
                    playback_snapshot=playback_snapshot,
                )
                if len(validation.accepted) != expected_count:
                    submitted_candidate_ids = [
                        item.candidate_id for item in parsed.recommendations
                    ]
                    if (
                        len(submitted_candidate_ids) == expected_count
                        and len(set(submitted_candidate_ids)) == expected_count
                        and set(submitted_candidate_ids).issubset(
                            set(fallback_candidate_ids)
                        )
                    ):
                        retry_allowed_candidate_ids = submitted_candidate_ids
                    last_drop_feedback = [
                        {
                            "candidate_id": drop.candidate_id,
                            "reason": drop.reason,
                        }
                        for drop in validation.dropped
                    ]
                    if not last_drop_feedback:
                        last_drop_feedback = [
                            {
                                "candidate_id": "",
                                "reason": "missing_recommendation",
                            }
                        ]
                    final_validation_drops.extend(
                        {
                            "attempt": attempt + 1,
                            **item,
                        }
                        for item in last_drop_feedback
                    )
                    feedback_text = ", ".join(
                        f"{item['candidate_id'] or 'submission'}:{item['reason']}"
                        for item in last_drop_feedback
                    )
                    raise AgentOutputError(
                        "final board validation failed: " + feedback_text
                    )
                accepted_new_count = sum(
                    item.candidate_id not in previous_board_id_set
                    for item in validation.accepted
                )
                if accepted_new_count < minimum_new_items:
                    last_drop_feedback = [
                        {
                            "candidate_id": "",
                            "reason": "previous_board_overlap_exceeded",
                        }
                    ]
                    final_validation_drops.append(
                        {
                            "attempt": attempt + 1,
                            **last_drop_feedback[0],
                        }
                    )
                    raise AgentOutputError(
                        "final board validation failed: "
                        "submission:previous_board_overlap_exceeded"
                    )
                self._finish_agent_provenance(call_entry, "completed")
                metrics["final_status"] = "success"
                metrics["final_ms"] = max(
                    0, int((time.monotonic() - final_stage_clock) * 1000)
                )
                return TournamentOutcome(
                    validation=validation,
                    agent_order={
                        item.candidate_id: index
                        for index, item in enumerate(validation.accepted)
                    },
                    fallback_reason="",
                    errors=tournament_errors,
                    prompt_fingerprint_source=base_prompt,
                    validation_drops=final_validation_drops,
                    fallback_candidate_ids=fallback_candidate_ids,
                )
            except Exception as error:
                duration_ms = max(
                    0, int((time.monotonic() - stage_clock) * 1000)
                )
                error_code = str(getattr(error, "code", "") or "").strip()
                error_field = str(getattr(error, "field", "") or "").strip()
                failure_reason = _safe_agent_failure_reason(error)
                if error_code and error_code not in failure_reason:
                    failure_reason = (
                        f"Agent submission failed: {error_code} "
                        f"({error_field or 'submission'})"
                    )
                if call_entry is None:
                    call_entry = self._record_agent_provenance(
                        metrics,
                        FINAL_AGENT_ROLE,
                        error,
                        stage="final",
                        attempt=attempt + 1,
                        duration_ms=duration_ms,
                    )
                    metrics["agent_ms"] = int(metrics.get("agent_ms", 0) or 0) + duration_ms
                self._finish_agent_provenance(call_entry, "failed", error)
                tournament_errors.append(
                    f"final attempt {attempt + 1}: {failure_reason}"
                )
                if isinstance(error, AgentOutputError):
                    last_retry_code = "final_validation_failed"
                    last_retry_field = "recommendations"
                elif error_code:
                    last_retry_code = error_code
                    last_retry_field = error_field or "submission"
                    if not last_drop_feedback:
                        last_drop_feedback = [
                            {
                                "candidate_id": "",
                                "reason": f"{last_retry_code} ({last_retry_field})",
                            }
                        ]
                else:
                    last_retry_code = "final_agent_failed"
                    last_retry_field = "submission"
                last_reason = (
                    "final_validation_failed"
                    if isinstance(error, AgentOutputError)
                    else "final_agent_failed"
                )
        metrics["final_status"] = "failed"
        metrics["final_ms"] = max(
            0, int((time.monotonic() - final_stage_clock) * 1000)
        )
        return TournamentOutcome(
            validation=None,
            agent_order={},
            fallback_reason=last_reason,
            errors=tournament_errors,
            prompt_fingerprint_source=base_prompt,
            validation_drops=final_validation_drops,
            fallback_candidate_ids=fallback_candidate_ids,
        )

    @staticmethod
    def _adaptive_fingerprint(value: Any) -> str:
        """对自适应门控输入计算稳定 SHA-256，不含运行时间和 run_id。"""
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _adaptive_source_fingerprint(
        self,
        current_profile: UserProfile,
        candidate_result: Any,
        candidates: Iterable[Any],
    ) -> str:
        """根据来源配方、分页层级和候选事实计算来源指纹。"""
        candidate_payload = [
            item.to_dict() if hasattr(item, "to_dict") else dict(item)
            for item in candidates or ()
        ]
        payload = {
            "filters": dict(current_profile.filters or {}),
            "ranking_tags": list(current_profile.ranking_tags or []),
            "candidate_ids": [
                str(item.get("candidate_id") or "") for item in candidate_payload
            ],
            "candidate_facts": candidate_payload,
            "request_recipes": list(
                getattr(candidate_result, "request_recipes", []) or []
            ),
            "source_counts": dict(
                getattr(candidate_result, "accepted_source_counts", {}) or {}
            ),
            "layer_counts": dict(getattr(candidate_result, "layer_counts", {}) or {}),
        }
        return self._adaptive_fingerprint(payload)

    def _adaptive_preference_fingerprint(
        self,
        profile_id: str,
        current_profile: UserProfile,
        profile_preferences: Any,
        confirmed_memory: Any,
    ) -> str:
        """根据画像、确认记忆和近期信号计算偏好指纹。"""
        signals = self._repository.load_short_term_signals(profile_id)
        payload = {
            "profile_input_fingerprint": current_profile.profile_input_fingerprint,
            "preferences_fingerprint": profile_preferences.fingerprint(),
            "memory_revision": int(getattr(confirmed_memory, "memory_revision", 0) or 0),
            "signals": [
                {
                    "idempotency_key": item.idempotency_key,
                    "kind": item.kind,
                    "candidate_id": item.candidate_id,
                    "run_id": item.run_id,
                    "board_revision": item.board_revision,
                    "strength": item.strength,
                    "decay_days": item.decay_days,
                    "observed_at": item.observed_at,
                }
                for item in signals
            ],
        }
        return self._adaptive_fingerprint(payload)

    def _adaptive_consumption_fingerprint(self, board: Any) -> str:
        """根据当前榜单曝光和交互状态计算消费指纹。"""
        if board is None:
            return self._adaptive_fingerprint({"consumption": "none"})
        consumption = self._repository.load_board_consumption(
            board.profile_id, board.run_id, board.revision
        )
        return self._adaptive_fingerprint(
            consumption.to_dict() if consumption is not None else {"consumption": "none"}
        )

    def _record_rotation_signal_if_needed(
        self, profile_id: str, board: Any, metrics: Dict[str, Any]
    ) -> None:
        """为已曝光且无交互的榜单写入一次独立轮换信号。"""
        if board is None:
            return
        consumption = self._repository.load_board_consumption(
            profile_id, board.run_id, board.revision
        )
        if consumption is None or not consumption.exposed or consumption.interacted:
            return
        key = f"rotation:{board.run_id}:{board.revision}"
        if any(
            item.idempotency_key == key
            for item in self._repository.load_short_term_signals(profile_id)
        ):
            metrics["rotation_signal_created"] = False
            return
        signal = ShortTermSignal(
            profile_id=profile_id,
            kind="rotation",
            idempotency_key=key,
            run_id=board.run_id,
            board_revision=board.revision,
            strength=1.0,
            decay_days=7,
            observed_at=datetime.now(timezone.utc).isoformat(),
            source="board_exposed_without_action",
        )
        self._repository.append_short_term_signal(signal)
        metrics["rotation_signal_created"] = True

    async def run(
        self,
        profile_id: str,
        config: Mapping[str, Any],
        *,
        trigger_reason: str = "manual",
    ) -> RecommendationRunResult:
        """为一个画像身份执行完整推荐；同身份并发请求立即返回 running。"""
        target = str(profile_id or "").strip()
        if not target:
            raise ValueError("profile_id is required")
        username = self._display_name(target, config)
        if not self._enter_profile(target):
            return RecommendationRunResult(
                target,
                "",
                "running",
                username=username,
                message="该画像榜单正在生成",
            )
        run_id = str(self._run_id_factory())
        started_at = datetime.now(timezone.utc).isoformat()
        started_clock = time.monotonic()
        metrics: Dict[str, Any] = {
            "_profile_id": target,
            "_run_id": run_id,
            "trigger_reason": str(trigger_reason or "manual").strip()[:32],
            "agent_calls": 0,
            "refill_attempted": False,
            "copy_rewrite_attempted": False,
            "copy_rewrite_candidate_count": 0,
            "copy_rewrite_success_count": 0,
            "copy_template_fallback_count": 0,
            "stage_order": [],
            "stage_status": {},
            "stage_ms": {},
        }
        errors: List[str] = []
        try:
            logger.info("AgentRank 运行开始 profile_id=%s run_id=%s", target, run_id)

            self._start_stage(metrics, "probe")
            probe = getattr(self._playback_service, "probe", None)
            if callable(probe):
                try:
                    capability = await asyncio.to_thread(probe, target, config)
                    metrics["playback_probe_status"] = str(capability.status)
                    metrics["playback_probe_message"] = str(capability.message or "")
                except Exception as error:
                    errors.append(f"playback probe: {error}")
                    metrics["playback_probe_status"] = "transient_error"
                    metrics["playback_probe_message"] = "Playback Reporting 探测失败"
                    return self._failure(
                        target,
                        username,
                        run_id,
                        "playback_unavailable",
                        "Playback Reporting 探测失败，未调用 Agent",
                        started_at,
                        started_clock,
                        metrics,
                        errors,
                    )
                if not bool(getattr(capability, "ready", False)):
                    return self._failure(
                        target,
                        username,
                        run_id,
                        "playback_unavailable",
                        str(
                            getattr(capability, "message", "")
                            or "Playback Reporting 不可用，未调用 Agent"
                        ),
                        started_at,
                        started_clock,
                        metrics,
                        errors,
                    )
                self._finish_stage(metrics, "ready")
            else:
                metrics["playback_probe_status"] = "unavailable"
                metrics["playback_probe_message"] = "Playback Reporting 探测服务不可用"
                return self._failure(
                    target,
                    username,
                    run_id,
                    "playback_unavailable",
                    "Playback Reporting 探测服务不可用，未调用 Agent",
                    started_at,
                    started_clock,
                    metrics,
                    errors,
                )

            self._start_stage(metrics, "playback_snapshot")
            playback_snapshot = None
            if self._playback_service is not None:
                stage_clock = time.monotonic()
                try:
                    playback_snapshot = await asyncio.to_thread(
                        self._playback_service.collect, target, config
                    )
                    metrics["playback_source"] = playback_snapshot.source
                    metrics["playback_status"] = playback_snapshot.status
                    metrics["playback_confidence"] = playback_snapshot.confidence
                    metrics["playback_count"] = playback_snapshot.sample_count
                    metrics["playback_unmapped_count"] = playback_snapshot.unmapped_count
                except Exception as error:
                    errors.append(f"playback: {error}")
                    metrics["playback_source"] = "unavailable"
                    metrics["playback_status"] = "error"
                metrics["playback_collect_ms"] = max(
                    0, int((time.monotonic() - stage_clock) * 1000)
                )
            playback_count = (
                playback_snapshot.sample_count if playback_snapshot is not None else 0
            )
            metrics["profile_evidence_count"] = playback_count
            playback_status = (
                playback_snapshot.status if playback_snapshot is not None else "unavailable"
            )
            if playback_status not in {"ready", "cached"}:
                return self._failure(
                    target,
                    username,
                    run_id,
                    "playback_unavailable",
                    str(
                        getattr(playback_snapshot, "message", "")
                        or "Playback Reporting 不可用，未调用 Agent"
                    ),
                    started_at,
                    started_clock,
                    metrics,
                    errors,
                )
            if playback_count < int(config.get("minimum_samples") or 5):
                return self._failure(
                    target,
                    username,
                    run_id,
                    "sample_insufficient",
                    "真实播放样本不足，未调用 Agent",
                    started_at,
                    started_clock,
                    metrics,
                    errors,
                )
            self._finish_stage(metrics, "ready")

            self._start_stage(metrics, "policy")
            try:
                policy_snapshot = await asyncio.to_thread(
                    self._policy_service.refresh,
                    target,
                    config.get("weights") or {},
                    playback_snapshot,
                )
                confirmed_memory = self._repository.load_preference_memory(target)
                if confirmed_memory.memory_revision != policy_snapshot.memory_revision:
                    policy_snapshot = await asyncio.to_thread(
                        self._policy_service.refresh,
                        target,
                        config.get("weights") or {},
                        playback_snapshot,
                    )
                    confirmed_memory = self._repository.load_preference_memory(
                        target
                    )
                if confirmed_memory.memory_revision != policy_snapshot.memory_revision:
                    raise RuntimeError(
                        "preference memory changed after policy refresh"
                    )
            except Exception as error:
                errors.append(f"policy: {error}")
                return self._failure(
                    target,
                    username,
                    run_id,
                    "policy_failed",
                    "确定性策略生成失败，已保留旧画像和旧榜单",
                    started_at,
                    started_clock,
                    metrics,
                    errors,
                )
            metrics["policy_version"] = policy_snapshot.policy_version
            metrics["policy_memory_revision"] = policy_snapshot.memory_revision
            metrics["policy_algorithm_version"] = policy_snapshot.algorithm_version
            metrics["policy_evidence_count"] = policy_snapshot.evidence_count
            self._finish_stage(metrics, "ready")

            self._start_stage(metrics, "profile")
            profile_cache_enabled = bool(config.get("profile_cache_enabled", True))
            rebuild_profile = bool(config.get("rebuild_profile_each_run", False))
            previous_profile = (
                self._repository.load_profile(target)
                if profile_cache_enabled and not rebuild_profile
                else None
            )
            profile_preferences = self._repository.load_profile_preferences(target)
            metrics["profile_mode"] = (
                "incremental"
                if profile_cache_enabled and not rebuild_profile
                else "rebuild" if rebuild_profile else "stateless"
            )
            metrics["previous_profile_used"] = previous_profile is not None
            metrics["custom_preference_count"] = len(
                profile_preferences.custom_tags
            ) + len(profile_preferences.custom_negative_tags)
            metrics["archived_preference_count"] = len(
                profile_preferences.archived_tags
            ) + len(profile_preferences.archived_negative_tags)
            playback_fingerprint = playback_snapshot.fingerprint()
            preferences_fingerprint = profile_preferences.fingerprint()
            profile_prompt_text = str(
                config.get("profile_prompt") or DEFAULT_PROFILE_PROMPT
            ).strip()
            profile_prompt_fingerprint = hashlib.sha256(
                profile_prompt_text.encode("utf-8")
            ).hexdigest()
            profile_input_fingerprint = self._profile_input_fingerprint(
                playback_fingerprint,
                preferences_fingerprint,
                confirmed_memory,
                config,
            )
            profile_cache_reason = self._profile_cache_reason(
                profile_cache_enabled,
                rebuild_profile,
                previous_profile,
                playback_fingerprint,
                preferences_fingerprint,
                profile_prompt_fingerprint,
                profile_input_fingerprint,
            )
            metrics["profile_input_fingerprint"] = profile_input_fingerprint
            metrics["profile_cache_status"] = (
                "hit" if profile_cache_reason == "hit" else "miss"
            )
            metrics["profile_cache_miss_reason"] = (
                "" if profile_cache_reason == "hit" else profile_cache_reason
            )
            current_profile = (
                previous_profile
                if profile_cache_reason == "hit"
                else None
            )
            metrics["profile_agent_reused"] = current_profile is not None
            if current_profile is None:
                profile_parser = self._profile_parser
                if (
                    previous_profile is not None
                    and previous_profile.retrieval_resolution_version
                    >= RETRIEVAL_RESOLUTION_VERSION
                    and isinstance(profile_parser, ProfileOutputParser)
                ):
                    profile_parser = profile_parser.with_allowed_keyword_ids(
                        previous_profile.filters.get("keyword_ids") or []
                    )
                profile_playback, playback_evidence_fingerprints = (
                    self._incremental_playback_context(
                        playback_snapshot, previous_profile
                    )
                )
                profile_preference_context = profile_preferences.to_dict()
                profile_preference_context["confirmed_preferences"] = [
                    item.to_dict()
                    for item in confirmed_memory.active_items()
                ]
                metrics["profile_incremental"] = bool(
                    profile_playback.get("incremental")
                )
                metrics["profile_incremental_sample_count"] = len(
                    profile_playback.get("samples") or []
                )
                metrics["profile_removed_sample_count"] = len(
                    profile_playback.get("removed_stable_ids") or []
                )
                profile_context = build_trusted_context(
                    username=username,
                    run_id=run_id,
                    candidates=[],
                    archive_feedback={"entries": []},
                    weights={},
                    previous_profile=(
                        previous_profile.to_dict()
                        if previous_profile is not None
                        else None
                    ),
                    profile_preferences=profile_preference_context,
                    playback=profile_playback,
                    profile=None,
                    agent_role=PROFILE_AGENT_ROLE,
                )
                parsed_profile = None
                profile_prompt = build_profile_prompt(
                    profile_prompt=profile_prompt_text
                )
                profile_attempt_errors: List[str] = []
                for attempt in range(2):
                    stage_clock = time.monotonic()
                    call_entry: Optional[Dict[str, Any]] = None
                    metrics["agent_calls"] += 1
                    metrics["profile_agent_calls"] = (
                        metrics.get("profile_agent_calls", 0) + 1
                    )
                    try:
                        raw_profile = await self._run_agent_role(
                            PROFILE_AGENT_ROLE,
                            profile_prompt
                            + (
                                "\n\n上一次输出未通过严格校验。请重新读取受限工具数据，"
                                "这次只返回一个符合既定 schema 的 JSON 对象，禁止代码块、"
                                "解释、前后缀或额外字段。"
                                if attempt > 0
                                else ""
                            ),
                            profile_context,
                        )
                        call_entry = self._record_agent_provenance(
                            metrics,
                            PROFILE_AGENT_ROLE,
                            raw_profile,
                            stage="profile",
                            attempt=attempt + 1,
                            duration_ms=max(
                                0, int((time.monotonic() - stage_clock) * 1000)
                            ),
                        )
                        parsed_profile = profile_parser.parse(raw_profile)
                        if parsed_profile.profile.playback_count != playback_count:
                            raise AgentOutputError(
                                "profile.playback_count does not match playback sample count"
                            )
                        self._finish_agent_provenance(call_entry, "completed")
                        break
                    except AgentOutputError as error:
                        if call_entry is None:
                            call_entry = self._record_agent_provenance(
                                metrics,
                                PROFILE_AGENT_ROLE,
                                error,
                                stage="profile",
                                attempt=attempt + 1,
                                duration_ms=max(
                                    0,
                                    int((time.monotonic() - stage_clock) * 1000),
                                ),
                            )
                            self._finish_agent_provenance(call_entry, "failed", error)
                        else:
                            self._finish_agent_provenance(
                                call_entry, "validation_failed", error
                            )
                        detail = f"profile attempt {attempt + 1}: {error}"
                        if attempt == 0:
                            profile_attempt_errors.append(detail)
                            self._record_retry(metrics, "profile", attempt + 1, error)
                            continue
                        errors.extend(profile_attempt_errors)
                        errors.append(detail)
                        return self._failure(
                            target,
                            username,
                            run_id,
                            "profile_validation_failed",
                            "画像 Agent 输出校验失败，已保留旧画像和旧榜单",
                            started_at,
                            started_clock,
                            metrics,
                            errors,
                            agent_calls=int(metrics["agent_calls"]),
                        )
                    except Exception as error:
                        if call_entry is None:
                            call_entry = self._record_agent_provenance(
                                metrics,
                                PROFILE_AGENT_ROLE,
                                error,
                                stage="profile",
                                attempt=attempt + 1,
                                duration_ms=max(
                                    0,
                                    int((time.monotonic() - stage_clock) * 1000),
                                ),
                            )
                        self._finish_agent_provenance(call_entry, "failed", error)
                        detail = f"profile attempt {attempt + 1}: {error}"
                        if attempt == 0 and bool(getattr(error, "retryable", False)):
                            profile_attempt_errors.append(detail)
                            self._record_retry(metrics, "profile", attempt + 1, error)
                            continue
                        errors.extend(profile_attempt_errors)
                        errors.append(detail)
                        return self._failure(
                            target,
                            username,
                            run_id,
                            "profile_agent_failed",
                            "画像 Agent 调用失败，已保留旧画像和旧榜单",
                            started_at,
                            started_clock,
                            metrics,
                            errors,
                            agent_calls=int(metrics["agent_calls"]),
                        )
                    finally:
                        metrics["agent_ms"] = metrics.get("agent_ms", 0) + max(
                            0, int((time.monotonic() - stage_clock) * 1000)
                        )
                if parsed_profile is None:
                    raise RuntimeError("profile Agent ended without a validated profile")
                try:
                    effective_plan = RetrievalPlan(
                        filters=parsed_profile.retrieval_plan.filters,
                        ranking_tags=tuple(
                            profile_preferences.effective_ranking_tags(
                                parsed_profile.retrieval_plan.ranking_tags
                            )
                        ),
                    )
                    plan_resolution = await asyncio.to_thread(
                        self._retrieval_plan_resolver.resolve,
                        effective_plan,
                    )
                except Exception as error:
                    errors.append(f"retrieval resolution fallback: {error}")
                    plan_resolution = RetrievalPlanResolution(
                        plan=parsed_profile.retrieval_plan
                    )
                metrics.update(plan_resolution.metrics())
                resolved_plan, softened_media_types = self._soften_profile_media_types(
                    plan_resolution.plan
                )
                metrics["softened_profile_media_types"] = list(
                    softened_media_types
                )
                metrics["ranking_tag_count"] = len(resolved_plan.ranking_tags)
                generated_at = datetime.now(timezone.utc).isoformat()
                current_profile = UserProfile(
                    profile_id=target,
                    username=username,
                    summary=parsed_profile.profile.summary,
                    tags=profile_preferences.active_agent_tags(
                        parsed_profile.profile.tags
                    ),
                    negative_tags=profile_preferences.active_agent_negative_tags(
                        parsed_profile.profile.negative_tags
                    ),
                    playback_count=parsed_profile.profile.playback_count,
                    playback_fingerprint=playback_fingerprint,
                    preferences_fingerprint=preferences_fingerprint,
                    profile_prompt_fingerprint=profile_prompt_fingerprint,
                    profile_input_fingerprint=profile_input_fingerprint,
                    playback_evidence_fingerprints=playback_evidence_fingerprints,
                    filters=resolved_plan.filters.to_dict(),
                    ranking_tags=list(resolved_plan.ranking_tags),
                    run_id=run_id,
                    generated_at=generated_at,
                )
                try:
                    self._repository.save_profile(current_profile)
                except Exception as error:
                    errors.append(str(error))
                    return self._failure(
                        target,
                        username,
                        run_id,
                        "profile_save_failed",
                        "画像保存失败，已保留旧榜单",
                        started_at,
                        started_clock,
                        metrics,
                        errors,
                        agent_calls=int(metrics["agent_calls"]),
                    )

            self._finish_stage(
                metrics,
                "reused" if metrics["profile_agent_reused"] else "generated",
            )

            self._start_stage(metrics, "candidate")
            candidate_plan, softened_media_types = self._soften_profile_media_types(
                RetrievalPlan.from_dict(
                    {
                        "filters": current_profile.filters,
                        "ranking_tags": current_profile.ranking_tags,
                    }
                )
            )
            current_profile.filters = candidate_plan.filters.to_dict()
            current_profile.ranking_tags = list(candidate_plan.ranking_tags)
            if softened_media_types:
                metrics["softened_profile_media_types"] = list(
                    softened_media_types
                )
            else:
                metrics.setdefault("softened_profile_media_types", [])
            archive = self._repository.load_archive(target)
            archived_ids = self._archive_candidate_ids(archive)
            previous_board = self._repository.load_board(target)
            previous_board_candidate_ids = self._board_candidate_ids(previous_board)
            board_recency_weights = self._board_recency_weights(
                target, previous_board_candidate_ids
            )
            metrics["previous_board_candidate_count"] = len(
                previous_board_candidate_ids
            )
            metrics["board_recency_candidate_count"] = len(board_recency_weights)
            metrics["board_recency_penalized_candidate_count"] = sum(
                value < 1.0 for value in board_recency_weights.values()
            )
            disliked_ids = FeedbackActionService(
                self._repository
            ).active_disliked_candidate_ids(target)
            metrics["active_disliked_candidate_count"] = len(disliked_ids)
            negative_keywords = profile_preferences.effective_negative_tags(
                current_profile.negative_tags
            )
            stage_clock = time.monotonic()
            try:
                candidate_result = await asyncio.to_thread(
                    self._candidate_service.collect_and_freeze,
                    target,
                    run_id,
                    config.get("discovery_sources") or {},
                    int(config.get("candidate_pool_size") or 15),
                    candidate_plan,
                    playback_samples=playback_snapshot.samples,
                    archived_candidate_ids=archived_ids,
                    negative_keywords=negative_keywords,
                    profile_version={
                        "run_id": current_profile.run_id,
                        "schema_version": current_profile.schema_version,
                        "retrieval_resolution_version": (
                            current_profile.retrieval_resolution_version
                        ),
                        "profile_input_fingerprint": (
                            current_profile.profile_input_fingerprint
                        ),
                    },
                    disliked_candidate_ids=disliked_ids,
                    previous_board_candidate_ids=previous_board_candidate_ids,
                )
            except Exception as error:
                errors.append(f"candidate: {error}")
                return self._failure(
                    target,
                    username,
                    run_id,
                    "candidate_failed",
                    "候选采集失败，已保留当前画像和旧榜单",
                    started_at,
                    started_clock,
                    metrics,
                    errors,
                    agent_calls=int(metrics["agent_calls"]),
                )
            metrics["candidate_collect_ms"] = max(
                0, int((time.monotonic() - stage_clock) * 1000)
            )
            candidate_snapshot = getattr(candidate_result, "snapshot", None)
            candidates = (
                list(candidate_snapshot.candidates)
                if candidate_snapshot is not None
                else list(candidate_result.candidates)
            )
            stage_clock = time.monotonic()
            if candidate_snapshot is None:
                candidates, library_excluded = await asyncio.to_thread(
                    self._exclude_library_candidates, candidates
                )
            else:
                library_excluded = []
            metrics["library_check_ms"] = max(
                0, int((time.monotonic() - stage_clock) * 1000)
            )
            metrics["candidate_count"] = len(candidates)
            self._publish_progress(
                metrics,
                "candidate",
                f"已筛选 {len(candidates)} 个候选，正在整理候选池",
            )
            metrics["library_excluded_count"] = len(library_excluded)
            metrics["candidate_rejected_count"] = candidate_result.rejected_count
            metrics["source_errors"] = dict(candidate_result.source_errors)
            metrics["fetched_source_counts"] = dict(
                getattr(candidate_result, "fetched_source_counts", {}) or {}
            )
            metrics["candidate_source_counts"] = dict(
                getattr(candidate_result, "accepted_source_counts", {}) or {}
            )
            metrics["request_recipes"] = list(
                getattr(candidate_result, "request_recipes", []) or []
            )
            metrics["candidate_layer_counts"] = dict(
                getattr(candidate_result, "layer_counts", {}) or {}
            )
            metrics["candidate_exclusion_counts"] = dict(
                getattr(candidate_result, "exclusion_counts", {}) or {}
            )
            metrics["candidate_filter_errors"] = dict(
                getattr(candidate_result, "filter_errors", {}) or {}
            )
            metrics["candidate_snapshot_hash"] = str(
                getattr(candidate_snapshot, "content_hash", "") or ""
            )
            metrics["candidate_snapshot_generated_at"] = str(
                getattr(candidate_snapshot, "generated_at", "") or ""
            )
            metrics["candidate_snapshot_error"] = str(
                getattr(candidate_result, "snapshot_error", "") or ""
            )
            candidate_timings = dict(
                getattr(candidate_result, "timings_ms", {}) or {}
            )
            for timing_name, timing_value in candidate_timings.items():
                metrics[f"candidate_{timing_name}_ms"] = max(
                    0, int(timing_value or 0)
                )
            candidate_processing_counts = dict(
                getattr(candidate_result, "processing_counts", {}) or {}
            )
            metrics["candidate_processing_counts"] = candidate_processing_counts
            metrics["candidate_target"] = int(
                config.get("candidate_pool_size") or 15
            )
            metrics["candidate_survival_rate_used"] = float(
                getattr(candidate_result, "survival_rate_used", 0.0) or 0.0
            )
            metrics["candidate_survival_rate"] = float(
                getattr(candidate_result, "candidate_survival_rate", 0.0) or 0.0
            )
            metrics["candidate_recognition_cache_hit_count"] = max(
                0,
                int(
                    candidate_processing_counts.get(
                        "candidate_recognition_cache_hit_count", 0
                    )
                    or 0
                ),
            )
            metrics["candidate_recognition_cache_miss_count"] = max(
                0,
                int(
                    candidate_processing_counts.get(
                        "candidate_recognition_cache_miss_count", 0
                    )
                    or 0
                ),
            )
            minimum_frozen_candidates = max(
                0,
                int(
                    getattr(
                        candidate_result,
                        "minimum_frozen_candidates",
                        0,
                    )
                    or 0
                ),
            )
            metrics["minimum_frozen_candidates"] = minimum_frozen_candidates
            logger.info(
                "AgentRank TMDB候选 profile_id=%s run_id=%s accepted=%s rejected=%s source_errors=%s",
                target,
                run_id,
                len(candidates),
                candidate_result.rejected_count,
                len(candidate_result.source_errors),
            )
            if (
                candidate_result.status != "ready"
                or len(candidates) < minimum_frozen_candidates
            ):
                filter_failed = candidate_result.status == "candidate_filter_failed"
                snapshot_failed = (
                    candidate_result.status == "candidate_snapshot_failed"
                )
                return self._failure(
                    target,
                    username,
                    run_id,
                    (
                        "candidate_filter_failed"
                        if filter_failed
                        else (
                            "candidate_snapshot_failed"
                            if snapshot_failed
                            else "candidate_insufficient"
                        )
                    ),
                    (
                        "候选硬过滤失败，未调用排序 Agent"
                        if filter_failed
                        else (
                            "候选快照保存失败，未调用排序 Agent"
                            if snapshot_failed
                            else "发现候选不足，未调用排序 Agent"
                        )
                    ),
                    started_at,
                    started_clock,
                    metrics,
                    errors,
                    agent_calls=int(metrics["agent_calls"]),
                )

            self._record_rotation_signal_if_needed(target, previous_board, metrics)
            source_fingerprint = self._adaptive_source_fingerprint(
                current_profile, candidate_result, candidates
            )
            preference_fingerprint = self._adaptive_preference_fingerprint(
                target,
                current_profile,
                profile_preferences,
                confirmed_memory,
            )
            consumption_fingerprint = self._adaptive_consumption_fingerprint(
                previous_board
            )
            metrics["source_fingerprint"] = source_fingerprint
            metrics["preference_fingerprint"] = preference_fingerprint
            metrics["consumption_fingerprint"] = consumption_fingerprint
            previous_fingerprints = self._repository.load_adaptive_fingerprints(target)
            same_adaptive_inputs = bool(
                previous_fingerprints is not None
                and previous_fingerprints.complete
                and previous_fingerprints.source_fingerprint == source_fingerprint
                and previous_fingerprints.preference_fingerprint == preference_fingerprint
                and previous_fingerprints.consumption_fingerprint == consumption_fingerprint
            )
            current_consumption = (
                self._repository.load_board_consumption(
                    target, previous_board.run_id, previous_board.revision
                )
                if previous_board is not None
                else None
            )
            allow_no_change_skip = (
                str(trigger_reason or "manual").strip().casefold() == "scheduled"
                and previous_board is not None
                and same_adaptive_inputs
                and not bool(current_consumption and current_consumption.exposed)
            )
            metrics["adaptive_gate"] = (
                "skipped_no_change" if allow_no_change_skip else "run"
            )
            if allow_no_change_skip:
                metrics["ranking_agent_calls"] = 0
                metrics["recommendation_candidate_ids"] = self._board_candidate_ids(
                    previous_board
                )
                metrics["final_count"] = len(previous_board.recommendations)
                metrics["adaptive_gate_reason"] = "source_preference_consumption_unchanged"
                self._repository.save_adaptive_fingerprints(
                    AdaptiveFingerprints(
                        profile_id=target,
                        source_fingerprint=source_fingerprint,
                        preference_fingerprint=preference_fingerprint,
                        consumption_fingerprint=consumption_fingerprint,
                        generated_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
                self._finish_stage(metrics, "skipped_no_change")
                message = "来源、偏好和榜单消费均未变化，保留当前榜单且未调用排序 Agent"
                self._append_run(
                    target,
                    username,
                    run_id,
                    "skipped_no_change",
                    started_at,
                    started_clock,
                    message,
                    errors,
                    metrics,
                )
                return RecommendationRunResult(
                    profile_id=target,
                    run_id=run_id,
                    status="skipped_no_change",
                    username=username,
                    message=message,
                    final_count=len(previous_board.recommendations),
                    agent_calls=int(metrics.get("agent_calls", 0) or 0),
                    board=previous_board,
                )

            self._finish_stage(metrics, "ready")

            self._start_stage(metrics, "ranking")
            subscribed_ids: Set[str] = set()
            ranking_profile = current_profile.to_dict()
            ranking_profile["tags"] = profile_preferences.effective_tags(
                current_profile.tags
            )
            ranking_profile["negative_tags"] = (
                profile_preferences.effective_negative_tags(
                    current_profile.negative_tags
                )
            )
            trusted_weights = self._trusted_weights(
                config,
                policy_snapshot,
                confirmed_memory,
                profile_preferences,
                playback_snapshot,
            )
            ranking_context = build_trusted_context(
                username=username,
                run_id=run_id,
                candidates=[candidate.to_dict() for candidate in candidates],
                archive_feedback=archive.to_dict(),
                weights=trusted_weights,
                previous_profile=None,
                profile_preferences=profile_preferences.to_dict(),
                playback=playback_snapshot.to_dict(),
                profile=ranking_profile,
                agent_role=RANKING_AGENT_ROLE,
            )

            validation = None
            agent_order: Dict[str, int] = {}
            tournament_validation_drops: List[Dict[str, Any]] = []
            tournament_fallback_candidate_ids: List[str] = []
            base_ranking_prompt = build_ranking_prompt(
                max_recommendations=RANKING_OUTPUT_LIMIT,
                ranking_prompt=str(config.get("ranking_prompt") or ""),
                copy_prompt=str(config.get("copy_prompt") or ""),
            )
            analysis_prompt_fingerprint = self._analysis_builder.prompt_fingerprint(
                base_ranking_prompt,
                "",
            )
            ranking_attempt_errors: List[str] = []
            ranking_fallback_reason = ""
            ranking_fallback_errors: List[str] = []
            tournament_protocol = self._uses_tournament_protocol()
            if tournament_protocol:
                tournament = await self._run_tournament(
                    profile_id=target,
                    run_id=run_id,
                    username=username,
                    candidates=candidates,
                    current_profile=current_profile,
                    ranking_profile=ranking_profile,
                    trusted_weights=trusted_weights,
                    policy_snapshot=policy_snapshot,
                    confirmed_memory=confirmed_memory,
                    profile_preferences=profile_preferences,
                    playback_snapshot=playback_snapshot,
                    archived_ids=archived_ids,
                    disliked_ids=disliked_ids,
                    subscribed_ids=subscribed_ids,
                    config=config,
                    metrics=metrics,
                    previous_board_candidate_ids=previous_board_candidate_ids,
                    board_recency_weights=board_recency_weights,
                )
                validation = tournament.validation
                agent_order.update(tournament.agent_order or {})
                tournament_validation_drops = list(tournament.validation_drops or [])
                tournament_fallback_candidate_ids = list(
                    tournament.fallback_candidate_ids or []
                )
                ranking_fallback_reason = tournament.fallback_reason
                ranking_fallback_errors.extend(tournament.errors or ())
                analysis_prompt_fingerprint = (
                    self._analysis_builder.prompt_fingerprint(
                        tournament.prompt_fingerprint_source,
                        "",
                    )
                )
            for attempt in (() if tournament_protocol else range(2)):
                prompt = base_ranking_prompt
                if attempt:
                    prompt += (
                        "\n\n上一次输出未通过严格校验。请在本次独立会话中各读取一次受限工具数据，"
                        "这次只返回一个符合既定 schema 的 JSON 对象，禁止代码块、"
                        "解释、前后缀或额外字段。"
                    )
                call_entry: Optional[Dict[str, Any]] = None
                try:
                    metrics["agent_calls"] += 1
                    metrics["ranking_agent_calls"] = (
                        metrics.get("ranking_agent_calls", 0) + 1
                    )
                    stage_clock = time.monotonic()
                    raw_output = await self._run_agent_role(
                        RANKING_AGENT_ROLE, prompt, ranking_context
                    )
                    call_entry = self._record_agent_provenance(
                        metrics,
                        RANKING_AGENT_ROLE,
                        raw_output,
                        stage="ranking",
                        attempt=attempt + 1,
                        duration_ms=max(
                            0, int((time.monotonic() - stage_clock) * 1000)
                        ),
                    )
                    metrics["agent_ms"] = metrics.get("agent_ms", 0) + max(
                        0, int((time.monotonic() - stage_clock) * 1000)
                    )
                except Exception as error:
                    call_entry = self._record_agent_provenance(
                        metrics,
                        RANKING_AGENT_ROLE,
                        error,
                        stage="ranking",
                        attempt=attempt + 1,
                        duration_ms=max(
                            0, int((time.monotonic() - stage_clock) * 1000)
                        ),
                    )
                    self._finish_agent_provenance(call_entry, "failed", error)
                    metrics["agent_ms"] = metrics.get("agent_ms", 0) + max(
                        0, int((time.monotonic() - stage_clock) * 1000)
                    )
                    detail = f"attempt {attempt + 1}: {error}"
                    if attempt == 0 and bool(getattr(error, "retryable", False)):
                        ranking_attempt_errors.append(detail)
                        self._record_retry(metrics, "ranking", attempt + 1, error)
                        continue
                    ranking_fallback_errors.extend(ranking_attempt_errors)
                    ranking_fallback_errors.append(detail)
                    ranking_fallback_reason = "ranking_agent_failed"
                    logger.warning(
                        "AgentRank Agent失败，转安全候选保底 profile_id=%s run_id=%s calls=%s reason=%s",
                        target,
                        run_id,
                        metrics["agent_calls"],
                        error,
                    )
                    break
                try:
                    parsed = self._ranking_parser.parse(raw_output)
                    validation = self._validator.validate(
                        parsed,
                        candidates,
                        archived_ids,
                        subscribed_ids,
                        preference_evidence=[
                            *current_profile.tags,
                            *current_profile.ranking_tags,
                        ],
                        playback_samples=playback_snapshot.samples,
                        disliked_candidate_ids=disliked_ids,
                        policy_snapshot=policy_snapshot,
                        confirmed_memory=confirmed_memory,
                        profile_preferences=profile_preferences,
                        playback_snapshot=playback_snapshot,
                    )
                    if validation.support_warnings:
                        metrics.setdefault("support_warnings", []).extend(
                            validation.support_warnings
                        )
                    self._finish_agent_provenance(call_entry, "completed")
                    break
                except AgentOutputError as error:
                    self._finish_agent_provenance(
                        call_entry, "validation_failed", error
                    )
                    detail = f"attempt {attempt + 1}: {error}"
                    if attempt == 0:
                        ranking_attempt_errors.append(detail)
                        self._record_retry(metrics, "ranking", attempt + 1, error)
                        continue
                    ranking_fallback_errors.extend(ranking_attempt_errors)
                    ranking_fallback_errors.append(detail)
                    ranking_fallback_reason = "ranking_validation_failed"
                    break
                except Exception as error:
                    self._finish_agent_provenance(call_entry, "failed", error)
                    raise
            if validation is None:
                metrics["ranking_valid_count"] = 0
                metrics["ranking_reserve_count"] = 0
                metrics["validation_drops"] = [
                    item["reason"]
                    for item in tournament_validation_drops
                    if item.get("reason")
                ]
                metrics["validation_drop_details"] = tournament_validation_drops
                accepted: List[RecommendationItem] = []
            else:
                metrics["ranking_valid_count"] = len(validation.accepted)
                metrics["ranking_reserve_count"] = max(
                    0, len(validation.accepted) - RECOMMENDATION_LIMIT
                )
                accepted = list(validation.accepted)
                agent_order.update(
                    {
                        item.candidate_id: index
                        for index, item in enumerate(accepted)
                    }
                )
                metrics["validation_drops"] = [
                    drop.reason for drop in validation.dropped
                ]
                metrics["validation_drop_details"] = [
                    {
                        "candidate_id": drop.candidate_id,
                        "reason": drop.reason,
                        "index": drop.index,
                    }
                    for drop in validation.dropped
                ]

            copy_rewrite_candidate_ids = {
                drop.candidate_id
                for drop in (validation.dropped if validation is not None else ())
                if drop.reason in COPY_REWRITE_REASON_CODES
            }
            metrics["copy_rewrite_candidate_count"] = len(
                copy_rewrite_candidate_ids
            )

            if (
                not tournament_protocol
                and validation is not None
                and len(accepted) < RECOMMENDATION_LIMIT
            ):
                trusted_candidate_ids = {
                    candidate.candidate_id for candidate in candidates
                }
                refill_feedback = [
                    {"candidate_id": drop.candidate_id, "reason": drop.reason}
                    for drop in validation.dropped
                    if drop.candidate_id in trusted_candidate_ids
                ]
                refill_drop_reasons: List[str] = []
                for refill_attempt in range(1):
                    accepted_ids = {item.candidate_id for item in accepted}
                    remaining_candidates = [
                        candidate
                        for candidate in candidates
                        if candidate.candidate_id not in accepted_ids
                    ]
                    if (
                        not remaining_candidates
                        or len(accepted) >= RECOMMENDATION_LIMIT
                    ):
                        break
                    metrics["refill_attempted"] = True
                    if copy_rewrite_candidate_ids:
                        metrics["copy_rewrite_attempted"] = True
                    metrics["refill_agent_calls"] = refill_attempt + 1
                    refill_slots = RECOMMENDATION_LIMIT - len(accepted)
                    current_refill_prompt = build_refill_prompt(
                        [item.candidate_id for item in accepted],
                        refill_slots,
                        ranking_prompt=str(config.get("ranking_prompt") or ""),
                        copy_prompt=str(config.get("copy_prompt") or ""),
                        rejected_candidates=refill_feedback,
                    )
                    analysis_prompt_fingerprint = (
                        self._analysis_builder.prompt_fingerprint(
                            base_ranking_prompt,
                            current_refill_prompt,
                        )
                    )
                    stage_clock = time.monotonic()
                    call_entry: Optional[Dict[str, Any]] = None
                    metrics["agent_calls"] += 1
                    metrics["ranking_agent_calls"] = (
                        metrics.get("ranking_agent_calls", 0) + 1
                    )
                    try:
                        refill_output = await self._run_agent_role(
                            RANKING_AGENT_ROLE,
                            current_refill_prompt,
                            ranking_context,
                        )
                        call_entry = self._record_agent_provenance(
                            metrics,
                            RANKING_AGENT_ROLE,
                            refill_output,
                            stage="refill",
                            attempt=refill_attempt + 1,
                            duration_ms=max(
                                0,
                                int((time.monotonic() - stage_clock) * 1000),
                            ),
                        )
                        (
                            refill_parsed,
                            refill_parse_warnings,
                        ) = self._ranking_parser.parse_recoverable(refill_output)
                        if refill_parse_warnings:
                            metrics.setdefault("refill_parse_warnings", []).extend(
                                refill_parse_warnings
                            )
                        refill_validation = self._validator.validate(
                            refill_parsed,
                            remaining_candidates,
                            archived_ids,
                            subscribed_ids,
                            preference_evidence=[
                                *current_profile.tags,
                                *current_profile.ranking_tags,
                            ],
                            playback_samples=playback_snapshot.samples,
                            disliked_candidate_ids=disliked_ids,
                            policy_snapshot=policy_snapshot,
                            confirmed_memory=confirmed_memory,
                            profile_preferences=profile_preferences,
                            playback_snapshot=playback_snapshot,
                        )
                        if refill_validation.support_warnings:
                            metrics.setdefault("support_warnings", []).extend(
                                refill_validation.support_warnings
                            )
                        for item in refill_validation.accepted[:refill_slots]:
                            agent_order.setdefault(
                                item.candidate_id, len(agent_order)
                            )
                            accepted.append(item)
                        metrics["copy_rewrite_success_count"] = len(
                            copy_rewrite_candidate_ids
                            & {item.candidate_id for item in accepted}
                        )
                        round_drop_reasons = [
                            drop.reason for drop in refill_validation.dropped
                        ]
                        refill_drop_reasons.extend(round_drop_reasons)
                        metrics["refill_drops"] = refill_drop_reasons
                        if (
                            not refill_parsed.recommendations
                            and refill_parse_warnings
                        ):
                            self._finish_agent_provenance(
                                call_entry,
                                "validation_failed",
                                "; ".join(refill_parse_warnings),
                            )
                            ranking_fallback_reason = "refill_validation_failed"
                            ranking_fallback_errors.extend(
                                f"refill attempt {refill_attempt + 1}: {warning}"
                                for warning in refill_parse_warnings
                            )
                        else:
                            self._finish_agent_provenance(call_entry, "completed")
                    except AgentOutputError as error:
                        if call_entry is None:
                            call_entry = self._record_agent_provenance(
                                metrics,
                                RANKING_AGENT_ROLE,
                                error,
                                stage="refill",
                                attempt=refill_attempt + 1,
                                duration_ms=max(
                                    0,
                                    int((time.monotonic() - stage_clock) * 1000),
                                ),
                            )
                            self._finish_agent_provenance(call_entry, "failed", error)
                        else:
                            self._finish_agent_provenance(
                                call_entry, "validation_failed", error
                            )
                        detail = f"refill attempt {refill_attempt + 1}: {error}"
                        ranking_fallback_errors.append(detail)
                        ranking_fallback_reason = "refill_validation_failed"
                        break
                    except Exception as error:
                        if call_entry is None:
                            call_entry = self._record_agent_provenance(
                                metrics,
                                RANKING_AGENT_ROLE,
                                error,
                                stage="refill",
                                attempt=refill_attempt + 1,
                                duration_ms=max(
                                    0,
                                    int((time.monotonic() - stage_clock) * 1000),
                                ),
                            )
                        self._finish_agent_provenance(call_entry, "failed", error)
                        detail = f"refill attempt {refill_attempt + 1}: {error}"
                        ranking_fallback_errors.append(detail)
                        ranking_fallback_reason = "refill_agent_failed"
                        break
                    finally:
                        metrics["agent_ms"] = metrics.get("agent_ms", 0) + max(
                            0, int((time.monotonic() - stage_clock) * 1000)
                        )

            fallback_candidate_ids: Set[str] = set()
            if len(accepted) < RECOMMENDATION_LIMIT:
                ranking_fallback_reason = ranking_fallback_reason or (
                    "refill_insufficient"
                    if metrics.get("refill_attempted")
                    else "ranking_insufficient"
                )
                fallback_scoring_errors: List[str] = []
                fallback_candidates = candidates
                if tournament_protocol and tournament_fallback_candidate_ids:
                    finalist_ids = set(tournament_fallback_candidate_ids)
                    finalist_candidates = [
                        candidate
                        for candidate in candidates
                        if candidate.candidate_id in finalist_ids
                    ]
                    fallback_candidates = [
                        *finalist_candidates,
                        *[
                            candidate
                            for candidate in candidates
                            if candidate.candidate_id not in finalist_ids
                        ],
                    ]
                fallback_items = self._validator.build_fallback_items(
                    fallback_candidates,
                    accepted,
                    blocked_candidate_ids={
                        *archived_ids,
                        *disliked_ids,
                        *subscribed_ids,
                    },
                    preference_evidence=[
                        *current_profile.tags,
                        *current_profile.ranking_tags,
                    ],
                    limit=RECOMMENDATION_LIMIT,
                    policy_snapshot=policy_snapshot,
                    confirmed_memory=confirmed_memory,
                    profile_preferences=profile_preferences,
                    playback_snapshot=playback_snapshot,
                    scoring_errors=fallback_scoring_errors,
                )
                ranking_fallback_errors.extend(fallback_scoring_errors)
                accepted.extend(fallback_items)
                fallback_candidate_ids.update(
                    item.candidate_id for item in fallback_items
                )
                metrics["copy_template_fallback_count"] = len(
                    copy_rewrite_candidate_ids & fallback_candidate_ids
                )

            try:
                accepted = self._rank_final_items(
                    accepted,
                    candidates,
                    agent_order=agent_order,
                    preserve_agent_order=tournament_protocol,
                )[:RECOMMENDATION_LIMIT]
            except Exception as error:
                errors.append(f"stable ranking: {error}")
                return self._failure(
                    target,
                    username,
                    run_id,
                    "ranking_validation_failed",
                    "确定性排序失败，已保留当前画像和旧榜单",
                    started_at,
                    started_clock,
                    metrics,
                    errors,
                    agent_calls=int(metrics["agent_calls"]),
                )

            fallback_count = len(fallback_candidate_ids)
            metrics["ranking_fallback_count"] = fallback_count
            metrics["ranking_fallback_reason"] = (
                ranking_fallback_reason if fallback_count else ""
            )
            metrics["ranking_fallback_errors"] = (
                ranking_fallback_errors if fallback_count else []
            )
            metrics["archive_commit_excluded_count"] = 0
            metrics["dislike_commit_excluded_count"] = 0
            selection_source_counts = {
                source: sum(item.selection_source == source for item in accepted)
                for source in ("agent", "safe_fallback")
            }
            metrics["selection_source_counts"] = selection_source_counts
            metrics["agent_selected_count"] = selection_source_counts["agent"]
            metrics["safe_fallback_selected_count"] = selection_source_counts[
                "safe_fallback"
            ]

            # 只有完整的 Agent Top 5 才能进入保存阶段。
            # 补位和不足五条都只能作为失败诊断，不能覆盖上一版成功榜单。
            if (
                fallback_count
                or len(accepted) != RECOMMENDATION_LIMIT
                or selection_source_counts["agent"] != RECOMMENDATION_LIMIT
                or selection_source_counts["safe_fallback"] != 0
            ):
                failure_status = (
                    "recommendation_degraded"
                    if fallback_count or selection_source_counts["safe_fallback"]
                    else "ranking_validation_failed"
                    if not accepted
                    else "recommendation_incomplete"
                )
                failure_message = (
                    "Agent 榜单未通过校验，已保留上一版榜单；本轮未保存安全补位结果"
                    if fallback_count or selection_source_counts["safe_fallback"]
                    else "排序 Agent 没有安全可用推荐，已保留当前画像和旧榜单"
                    if not accepted
                    else f"Agent 仅生成 {selection_source_counts['agent']} 条有效推荐，已保留上一版榜单"
                )
                return self._failure(
                    target,
                    username,
                    run_id,
                    failure_status,
                    failure_message,
                    started_at,
                    started_clock,
                    metrics,
                    [*errors, *ranking_fallback_errors],
                    agent_calls=int(metrics["agent_calls"]),
                )

            if not accepted:
                errors.extend(ranking_fallback_errors)
                return self._failure(
                    target,
                    username,
                    run_id,
                    "ranking_validation_failed",
                    "排序 Agent 没有安全可用推荐，已保留当前画像和旧榜单",
                    started_at,
                    started_clock,
                    metrics,
                    errors,
                    agent_calls=int(metrics["agent_calls"]),
                )

            self._candidate_service.enrich_recommendation_sources(accepted)
            try:
                with self._repository.board_archive_guard(target):
                    latest_memory = self._repository.load_preference_memory(target)
                    if latest_memory.memory_revision != policy_snapshot.memory_revision:
                        errors.append(
                            "confirmed preference memory changed during ranking"
                        )
                        return self._failure(
                            target,
                            username,
                            run_id,
                            "policy_superseded",
                            "偏好记忆已更新，本轮旧策略结果未保存",
                            started_at,
                            started_clock,
                            metrics,
                            errors,
                            agent_calls=int(metrics["agent_calls"]),
                        )
                    latest_archive = self._repository.load_archive(target)
                    latest_archived_ids = self._archive_candidate_ids(latest_archive)
                    latest_disliked_ids = FeedbackActionService(
                        self._repository
                    ).active_disliked_candidate_ids(target)
                    archive_commit_excluded_ids = {
                        item.candidate_id
                        for item in accepted
                        if item.candidate_id in latest_archived_ids
                    }
                    dislike_commit_excluded_ids = {
                        item.candidate_id
                        for item in accepted
                        if item.candidate_id in latest_disliked_ids
                    }
                    commit_excluded_ids = {
                        *archive_commit_excluded_ids,
                        *dislike_commit_excluded_ids,
                    }
                    if commit_excluded_ids:
                        accepted = [
                            item
                            for item in accepted
                            if item.candidate_id not in commit_excluded_ids
                        ]
                        fallback_candidate_ids.difference_update(commit_excluded_ids)
                        commit_scoring_errors: List[str] = []
                        commit_fallback_items = self._validator.build_fallback_items(
                            candidates,
                            accepted,
                            blocked_candidate_ids={
                                *latest_archived_ids,
                                *latest_disliked_ids,
                                *subscribed_ids,
                            },
                            preference_evidence=[
                                *current_profile.tags,
                                *current_profile.ranking_tags,
                            ],
                            limit=RECOMMENDATION_LIMIT,
                            policy_snapshot=policy_snapshot,
                            confirmed_memory=confirmed_memory,
                            profile_preferences=profile_preferences,
                            playback_snapshot=playback_snapshot,
                            scoring_errors=commit_scoring_errors,
                        )
                        ranking_fallback_errors.extend(commit_scoring_errors)
                        accepted.extend(commit_fallback_items)
                        fallback_candidate_ids.update(
                            item.candidate_id for item in commit_fallback_items
                        )
                        self._candidate_service.enrich_recommendation_sources(
                            commit_fallback_items
                        )
                    try:
                        accepted = self._rank_final_items(
                            accepted,
                            candidates,
                            agent_order=agent_order,
                            preserve_agent_order=tournament_protocol,
                        )[:RECOMMENDATION_LIMIT]
                    except Exception as error:
                        errors.append(f"commit stable ranking: {error}")
                        return self._failure(
                            target,
                            username,
                            run_id,
                            "ranking_validation_failed",
                            "提交前确定性排序失败，已保留旧榜单",
                            started_at,
                            started_clock,
                            metrics,
                            errors,
                            agent_calls=int(metrics["agent_calls"]),
                        )

                    fallback_count = sum(
                        item.candidate_id in fallback_candidate_ids
                        for item in accepted
                    )
                    metrics["archive_commit_excluded_count"] = len(
                        archive_commit_excluded_ids
                    )
                    metrics["dislike_commit_excluded_count"] = len(
                        dislike_commit_excluded_ids
                    )
                    metrics["ranking_fallback_count"] = fallback_count
                    metrics["ranking_fallback_reason"] = (
                        (
                            ranking_fallback_reason
                            or (
                                "feedback_updated_during_run"
                                if archive_commit_excluded_ids
                                and dislike_commit_excluded_ids
                                else "dislike_updated_during_run"
                                if dislike_commit_excluded_ids
                                else "archive_updated_during_run"
                            )
                        )
                        if fallback_count
                        else ""
                    )
                    metrics["ranking_fallback_errors"] = (
                        ranking_fallback_errors if fallback_count else []
                    )
                    selection_source_counts = {
                        source: sum(
                            item.selection_source == source for item in accepted
                        )
                        for source in ("agent", "safe_fallback")
                    }
                    metrics["selection_source_counts"] = selection_source_counts
                    metrics["agent_selected_count"] = selection_source_counts[
                        "agent"
                    ]
                    metrics["safe_fallback_selected_count"] = (
                        selection_source_counts["safe_fallback"]
                    )
                    if (
                        fallback_count
                        or len(accepted) != RECOMMENDATION_LIMIT
                        or selection_source_counts["agent"] != RECOMMENDATION_LIMIT
                        or selection_source_counts["safe_fallback"] != 0
                    ):
                        failure_status = (
                            "recommendation_degraded"
                            if fallback_count
                            or selection_source_counts["safe_fallback"]
                            else "ranking_validation_failed"
                            if not accepted
                            else "recommendation_incomplete"
                        )
                        failure_message = (
                            "榜单提交期间反馈发生变化，已保留上一版榜单；本轮未保存安全补位结果"
                            if fallback_count
                            or selection_source_counts["safe_fallback"]
                            else "最新忽略或不喜欢记录生效后没有安全可用推荐，已保留旧榜单"
                            if not accepted
                            else f"榜单提交前仅剩 {selection_source_counts['agent']} 条 Agent 推荐，已保留上一版榜单"
                        )
                        return self._failure(
                            target,
                            username,
                            run_id,
                            failure_status,
                            failure_message,
                            started_at,
                            started_clock,
                            metrics,
                            [*errors, *ranking_fallback_errors],
                            agent_calls=int(metrics["agent_calls"]),
                        )
                    supported_items = [
                        item for item in accepted if item.support is not None
                    ]
                    metrics["support_scored_count"] = len(supported_items)
                    metrics["support_min"] = (
                        min(item.support.percentage for item in supported_items)
                        if supported_items
                        else 0
                    )
                    metrics["support_max"] = (
                        max(item.support.percentage for item in supported_items)
                        if supported_items
                        else 0
                    )
                    selection_source_counts = {
                        source: sum(
                            item.selection_source == source for item in accepted
                        )
                        for source in ("agent", "safe_fallback")
                    }
                    metrics["selection_source_counts"] = selection_source_counts
                    metrics["agent_selected_count"] = selection_source_counts[
                        "agent"
                    ]
                    metrics["safe_fallback_selected_count"] = (
                        selection_source_counts["safe_fallback"]
                    )

                    if not accepted:
                        errors.extend(ranking_fallback_errors)
                        return self._failure(
                            target,
                            username,
                            run_id,
                            "ranking_validation_failed",
                            "最新忽略或不喜欢记录生效后没有安全可用推荐，已保留旧榜单",
                            started_at,
                            started_clock,
                            metrics,
                            errors,
                            agent_calls=int(metrics["agent_calls"]),
                        )

                    status = (
                        "recommendation_incomplete"
                        if len(accepted) < RECOMMENDATION_LIMIT
                        else "recommendation_degraded"
                        if fallback_count and not selection_source_counts["agent"]
                        else "success"
                    )
                    if status != "success":
                        errors.extend(ranking_fallback_errors)
                    self._finish_stage(metrics, status)
                    self._start_stage(metrics, "save")
                    generated_at = datetime.now(timezone.utc).isoformat()
                    try:
                        analyses = [
                            self._analysis_builder.build(
                                target,
                                run_id,
                                item,
                                policy_snapshot,
                                analysis_prompt_fingerprint,
                            )
                            for item in accepted
                        ]
                        analysis_ids = {
                            item.candidate_id: item.analysis_id for item in analyses
                        }
                        for item in accepted:
                            item.analysis_id = analysis_ids[item.candidate_id]
                        metrics["recommendation_analysis_count"] = len(analyses)
                    except Exception as error:
                        errors.append(f"recommendation analysis: {error}")
                        return self._failure(
                            target,
                            username,
                            run_id,
                            "ranking_validation_failed",
                            "结构化Agent分析生成失败，已保留旧榜单",
                            started_at,
                            started_clock,
                            metrics,
                            errors,
                            agent_calls=int(metrics["agent_calls"]),
                        )
                    previous_board = self._repository.load_board(target)
                    board = RecommendationBoard(
                        profile_id=target,
                        username=username,
                        run_id=run_id,
                        status=status,
                        recommendations=accepted,
                        generated_at=generated_at,
                        message=(
                            f"榜单降级完成，安全候选池补位 {fallback_count} 条"
                            if status == "recommendation_degraded"
                            else "榜单生成成功"
                            if status == "success"
                            else f"仅生成 {len(accepted)} 条有效推荐"
                        ),
                        previous_run_id=(
                            previous_board.run_id if previous_board else None
                        ),
                        revision=(
                            previous_board.revision + 1 if previous_board else 1
                        ),
                    )
                    stage_clock = time.monotonic()
                    self._repository.save_board_with_recommendation_analyses(
                        board,
                        analyses,
                        limit=int(config.get("analysis_record_limit") or 500),
                    )
            except Exception as error:
                errors.append(str(error))
                return self._failure(
                    target,
                    username,
                    run_id,
                    "ranking_save_failed",
                    "榜单保存失败，已保留当前画像和旧榜单",
                    started_at,
                    started_clock,
                    metrics,
                    errors,
                    agent_calls=int(metrics["agent_calls"]),
                )
            metrics["save_ms"] = max(
                0, int((time.monotonic() - stage_clock) * 1000)
            )
            self._finish_stage(metrics, "saved")
            metrics["final_count"] = len(accepted)
            metrics["recommendation_candidate_ids"] = [
                item.candidate_id for item in accepted[:RECOMMENDATION_LIMIT]
            ]
            self._repository.save_adaptive_fingerprints(
                AdaptiveFingerprints(
                    profile_id=target,
                    source_fingerprint=str(metrics.get("source_fingerprint") or ""),
                    preference_fingerprint=str(
                        metrics.get("preference_fingerprint") or ""
                    ),
                    consumption_fingerprint=str(
                        metrics.get("consumption_fingerprint") or ""
                    ),
                    generated_at=generated_at,
                )
            )
            self._append_run(
                target,
                username,
                run_id,
                status,
                started_at,
                started_clock,
                board.message,
                errors,
                metrics,
            )
            logger.info(
                "AgentRank 运行完成 profile_id=%s run_id=%s status=%s recommendations=%s agent_calls=%s",
                target,
                run_id,
                status,
                len(accepted),
                metrics["agent_calls"],
            )
            return RecommendationRunResult(
                profile_id=target,
                username=username,
                run_id=run_id,
                status=status,
                message=board.message,
                final_count=len(accepted),
                agent_calls=int(metrics["agent_calls"]),
                board=board,
            )
        finally:
            self._leave_profile(target)
