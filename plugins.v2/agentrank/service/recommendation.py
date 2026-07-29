"""按用户锁定的 Agent 榜单推荐编排服务。"""

import asyncio
import hashlib
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Set

from ..agent_tools.context import (
    PROFILE_AGENT_ROLE,
    RANKING_AGENT_ROLE,
    build_trusted_context,
)
from ..model.candidate import typed_tmdb_candidate_id
from ..model.config import configured_identities
from ..model.constants import RANKING_OUTPUT_LIMIT, RECOMMENDATION_LIMIT
from ..model.board import RecommendationBoard, RecommendationItem
from ..model.profile import (
    PROFILE_SCHEMA_VERSION,
    RETRIEVAL_RESOLUTION_VERSION,
    UserProfile,
)
from ..model.retrieval import RetrievalPlan
from ..model.run import RecommendationRun
from ..model.policy import PolicySnapshot
from ..storage.repository import AgentRankRepository
from .prompt import (
    DEFAULT_PROFILE_PROMPT,
    build_profile_prompt,
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
        method_name = (
            "run_profile" if role == PROFILE_AGENT_ROLE else "run_ranking"
        )
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
        entry = {
            "role": role,
            "provider_id": safe_text("provider_id"),
            "selected_provider_name": safe_text("selected_provider_name"),
            "provider": safe_text("provider"),
            "model": safe_text("model", "unknown"),
            "source": safe_text("source", "unknown"),
            "model_call_count": model_call_count,
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
            "media_types": list(config.get("media_types") or []),
            "candidate_pool_size": int(config.get("candidate_pool_size") or 100),
            "confidence_threshold": float(config.get("confidence_threshold") or 0.0),
            "exclude_keywords": list(config.get("exclude_keywords") or []),
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
        return "hit"

    @staticmethod
    def _start_stage(metrics: Dict[str, Any], stage: str) -> None:
        """开始一个可审计运行阶段，并记录稳定执行顺序。"""
        if metrics.get("_stage_name"):
            raise RuntimeError("previous recommendation stage is still active")
        metrics.setdefault("stage_order", []).append(stage)
        metrics["_stage_name"] = stage
        metrics["_stage_started_at"] = time.monotonic()

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

    async def run(
        self, profile_id: str, config: Mapping[str, Any]
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
            profile_cache_reason = self._profile_cache_reason(
                profile_cache_enabled,
                rebuild_profile,
                previous_profile,
                playback_fingerprint,
                preferences_fingerprint,
                profile_prompt_fingerprint,
            )
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
                    profile_preferences=profile_preferences.to_dict(),
                    playback=playback_snapshot.to_dict(),
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
                resolved_plan = plan_resolution.plan
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
            archive = self._repository.load_archive(target)
            archived_ids = self._archive_candidate_ids(archive)
            disliked_ids = FeedbackActionService(
                self._repository
            ).active_disliked_candidate_ids(target)
            metrics["active_disliked_candidate_count"] = len(disliked_ids)
            negative_keywords = list(config.get("exclude_keywords") or [])
            negative_keywords.extend(
                profile_preferences.effective_negative_tags(
                    current_profile.negative_tags
                )
            )
            stage_clock = time.monotonic()
            try:
                candidate_result = await asyncio.to_thread(
                    self._candidate_service.collect_and_freeze,
                    target,
                    run_id,
                    config.get("discovery_sources") or {},
                    int(config.get("candidate_pool_size") or 100),
                    RetrievalPlan.from_dict(
                        {
                            "filters": current_profile.filters,
                            "ranking_tags": current_profile.ranking_tags,
                        }
                    ),
                    playback_samples=playback_snapshot.samples,
                    archived_candidate_ids=archived_ids,
                    negative_keywords=negative_keywords,
                    profile_version={
                        "run_id": current_profile.run_id,
                        "schema_version": current_profile.schema_version,
                        "retrieval_resolution_version": (
                            current_profile.retrieval_resolution_version
                        ),
                    },
                    disliked_candidate_ids=disliked_ids,
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
            ranking_context = build_trusted_context(
                username=username,
                run_id=run_id,
                candidates=[candidate.to_dict() for candidate in candidates],
                archive_feedback=archive.to_dict(),
                weights=self._trusted_weights(
                    config,
                    policy_snapshot,
                    confirmed_memory,
                    profile_preferences,
                    playback_snapshot,
                ),
                previous_profile=None,
                profile_preferences=profile_preferences.to_dict(),
                playback=playback_snapshot.to_dict(),
                profile=ranking_profile,
                agent_role=RANKING_AGENT_ROLE,
            )

            validation = None
            agent_order: Dict[str, int] = {}
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
            for attempt in range(2):
                prompt = base_ranking_prompt
                if attempt:
                    prompt += (
                        "\n\n上一次输出未通过严格校验。请重新读取受限工具数据，"
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
                metrics["validation_drops"] = []
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

            copy_rewrite_candidate_ids = {
                drop.candidate_id
                for drop in (validation.dropped if validation is not None else ())
                if drop.reason in COPY_REWRITE_REASON_CODES
            }
            metrics["copy_rewrite_candidate_count"] = len(
                copy_rewrite_candidate_ids
            )

            if validation is not None and len(accepted) < RECOMMENDATION_LIMIT:
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
                fallback_items = self._validator.build_fallback_items(
                    candidates,
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
                accepted = self._ranker.rank(
                    accepted,
                    candidates,
                    agent_order=agent_order,
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
                        accepted = self._ranker.rank(
                            accepted,
                            candidates,
                            agent_order=agent_order,
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
                        "success"
                        if len(accepted) >= RECOMMENDATION_LIMIT
                        else "recommendation_incomplete"
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
                            f"榜单生成成功，安全候选池补位 {fallback_count} 条"
                            if status == "success" and fallback_count
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
