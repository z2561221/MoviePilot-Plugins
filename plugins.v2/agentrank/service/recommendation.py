"""按用户锁定的 Agent 榜单推荐编排服务。"""

import asyncio
import logging
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
from ..model.config import configured_identities
from ..model.board import RecommendationBoard, RecommendationItem
from ..model.profile import (
    PROFILE_SCHEMA_VERSION,
    RETRIEVAL_RESOLUTION_VERSION,
    UserProfile,
)
from ..model.retrieval import RetrievalPlan
from ..model.run import RecommendationRun
from ..storage.repository import AgentRankRepository
from .prompt import build_profile_prompt, build_ranking_prompt, build_refill_prompt
from .keyword_resolution import (
    ControlledRetrievalPlanResolver,
    RetrievalPlanResolution,
)
from .validation import (
    AgentOutputError,
    ProfileOutputParser,
    RankingOutputParser,
    RecommendationValidator,
)


logger = logging.getLogger(__name__)


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
    ):
        """注入可测试的领域依赖并初始化用户锁集合。"""
        self._repository = repository
        self._candidate_service = candidate_service
        self.agent_adapter = agent_adapter
        self._run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)
        self._profile_parser = profile_parser or ProfileOutputParser()
        self._ranking_parser = ranking_parser or parser or RankingOutputParser()
        self._validator = validator or RecommendationValidator()
        self._library_adapter = library_adapter
        self._playback_service = playback_service
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
    def _display_name(profile_id: str, config: Mapping[str, Any]) -> str:
        """返回 profile_id 对应的 Emby 显示名。"""
        for identity in configured_identities(config):
            if identity.profile_id == profile_id:
                return identity.username
        return ""

    @staticmethod
    def _trusted_weights(config: Mapping[str, Any]) -> Dict[str, Any]:
        """选择 Agent 允许读取的权重和筛选配置。"""
        return {
            "weights": dict(config.get("weights") or {}),
            "media_types": list(config.get("media_types") or []),
            "candidate_pool_size": int(config.get("candidate_pool_size") or 50),
            "confidence_threshold": float(config.get("confidence_threshold") or 0.0),
            "exclude_keywords": list(config.get("exclude_keywords") or []),
        }

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
        metrics: Dict[str, Any] = {"agent_calls": 0, "refill_attempted": False}
        errors: List[str] = []
        try:
            logger.info("AgentRank 运行开始 profile_id=%s run_id=%s", target, run_id)
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
            playback_fingerprint = playback_snapshot.fingerprint()
            current_profile = (
                previous_profile
                if previous_profile is not None
                and previous_profile.schema_version >= PROFILE_SCHEMA_VERSION
                and previous_profile.retrieval_resolution_version
                >= RETRIEVAL_RESOLUTION_VERSION
                and previous_profile.playback_fingerprint == playback_fingerprint
                else None
            )
            metrics["profile_agent_reused"] = current_profile is not None
            if current_profile is None:
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
                for attempt in range(2):
                    stage_clock = time.monotonic()
                    metrics["agent_calls"] += 1
                    metrics["profile_agent_calls"] = (
                        metrics.get("profile_agent_calls", 0) + 1
                    )
                    try:
                        raw_profile = await self._run_agent_role(
                            PROFILE_AGENT_ROLE,
                            build_profile_prompt(
                                agent_prompt=str(config.get("agent_prompt") or "")
                            ),
                            profile_context,
                        )
                        parsed_profile = self._profile_parser.parse(raw_profile)
                        if parsed_profile.profile.playback_count != playback_count:
                            raise AgentOutputError(
                                "profile.playback_count does not match playback sample count"
                            )
                        break
                    except AgentOutputError as error:
                        errors.append(f"profile attempt {attempt + 1}: {error}")
                        if attempt == 0:
                            continue
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
                        if attempt == 0 and bool(getattr(error, "retryable", False)):
                            errors.append(f"profile attempt 1: {error}")
                            continue
                        errors.append(str(error))
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
                    plan_resolution = await asyncio.to_thread(
                        self._retrieval_plan_resolver.resolve,
                        parsed_profile.retrieval_plan,
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
                    tags=list(parsed_profile.profile.tags),
                    negative_tags=list(parsed_profile.profile.negative_tags),
                    playback_count=parsed_profile.profile.playback_count,
                    playback_fingerprint=playback_fingerprint,
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

            stage_clock = time.monotonic()
            candidate_result = await asyncio.to_thread(
                self._candidate_service.collect_and_freeze,
                target,
                run_id,
                config.get("discovery_sources") or {},
                int(config.get("candidate_pool_size") or 50),
                RetrievalPlan.from_dict(
                    {
                        "filters": current_profile.filters,
                        "ranking_tags": current_profile.ranking_tags,
                    }
                ),
                playback_samples=playback_snapshot.samples,
            )
            metrics["candidate_collect_ms"] = max(
                0, int((time.monotonic() - stage_clock) * 1000)
            )
            candidates = list(candidate_result.candidates)
            stage_clock = time.monotonic()
            candidates, library_excluded = await asyncio.to_thread(
                self._exclude_library_candidates, candidates
            )
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
                return self._failure(
                    target,
                    username,
                    run_id,
                    "candidate_insufficient",
                    "发现候选不足，未调用 Agent",
                    started_at,
                    started_clock,
                    metrics,
                    errors,
                )

            archive = self._repository.load_archive(target)
            archived_ids = {entry.candidate_id for entry in archive.entries}
            subscribed_ids: Set[str] = set()
            ranking_context = build_trusted_context(
                username=username,
                run_id=run_id,
                candidates=[candidate.to_dict() for candidate in candidates],
                archive_feedback=archive.to_dict(),
                weights=self._trusted_weights(config),
                previous_profile=None,
                profile_preferences=profile_preferences.to_dict(),
                playback=playback_snapshot.to_dict(),
                profile=current_profile.to_dict(),
                agent_role=RANKING_AGENT_ROLE,
            )

            validation = None
            for attempt in range(2):
                prompt = build_ranking_prompt(
                    agent_prompt=str(config.get("agent_prompt") or "")
                )
                if attempt:
                    prompt += (
                        "\n\n上一次输出未通过严格校验。请重新读取受限工具数据，"
                        "这次只返回一个符合既定 schema 的 JSON 对象，禁止代码块、"
                        "解释、前后缀或额外字段。"
                    )
                try:
                    metrics["agent_calls"] += 1
                    metrics["ranking_agent_calls"] = (
                        metrics.get("ranking_agent_calls", 0) + 1
                    )
                    stage_clock = time.monotonic()
                    raw_output = await self._run_agent_role(
                        RANKING_AGENT_ROLE, prompt, ranking_context
                    )
                    metrics["agent_ms"] = metrics.get("agent_ms", 0) + max(
                        0, int((time.monotonic() - stage_clock) * 1000)
                    )
                except Exception as error:
                    metrics["agent_ms"] = metrics.get("agent_ms", 0) + max(
                        0, int((time.monotonic() - stage_clock) * 1000)
                    )
                    if attempt == 0 and bool(getattr(error, "retryable", False)):
                        errors.append(f"attempt 1: {error}")
                        continue
                    errors.append(str(error))
                    logger.warning(
                        "AgentRank Agent失败 profile_id=%s run_id=%s calls=%s reason=%s",
                        target,
                        run_id,
                        metrics["agent_calls"],
                        error,
                    )
                    return self._failure(
                        target,
                        username,
                        run_id,
                        "ranking_agent_failed",
                        "排序 Agent 调用失败，已保留当前画像和旧榜单",
                        started_at,
                        started_clock,
                        metrics,
                        errors,
                        agent_calls=int(metrics["agent_calls"]),
                    )
                try:
                    parsed = self._ranking_parser.parse(raw_output)
                    validation = self._validator.validate(
                        parsed, candidates, archived_ids, subscribed_ids
                    )
                    break
                except AgentOutputError as error:
                    errors.append(f"attempt {attempt + 1}: {error}")
                    if attempt == 0:
                        continue
                    return self._failure(
                        target,
                        username,
                        run_id,
                        "ranking_validation_failed",
                        "排序 Agent 输出校验失败，已保留当前画像和旧榜单",
                        started_at,
                        started_clock,
                        metrics,
                        errors,
                        agent_calls=int(metrics["agent_calls"]),
                    )
            if validation is None:
                raise RuntimeError("Agent validation retry loop ended without a result")
            accepted: List[RecommendationItem] = list(validation.accepted)
            metrics["validation_drops"] = [drop.reason for drop in validation.dropped]
            if not accepted:
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

            if len(accepted) < 10:
                accepted_ids = {item.candidate_id for item in accepted}
                remaining_candidates = [
                    candidate
                    for candidate in candidates
                    if candidate.candidate_id not in accepted_ids
                ]
                if remaining_candidates:
                    metrics["refill_attempted"] = True
                    stage_clock = time.monotonic()
                    metrics["agent_calls"] += 1
                    metrics["ranking_agent_calls"] = (
                        metrics.get("ranking_agent_calls", 0) + 1
                    )
                    try:
                        refill_output = await self._run_agent_role(
                            RANKING_AGENT_ROLE,
                            build_refill_prompt(
                                [item.candidate_id for item in accepted],
                                10 - len(accepted),
                                agent_prompt=str(config.get("agent_prompt") or ""),
                            ),
                            ranking_context,
                        )
                        refill_parsed = self._ranking_parser.parse(refill_output)
                        refill_validation = self._validator.validate(
                            refill_parsed,
                            remaining_candidates,
                            archived_ids,
                            subscribed_ids,
                        )
                        for item in refill_validation.accepted[: 10 - len(accepted)]:
                            item.rank = len(accepted) + 1
                            accepted.append(item)
                        metrics["refill_drops"] = [
                            drop.reason for drop in refill_validation.dropped
                        ]
                    except Exception as error:
                        errors.append(f"refill: {error}")
                    finally:
                        metrics["agent_ms"] = metrics.get("agent_ms", 0) + max(
                            0, int((time.monotonic() - stage_clock) * 1000)
                        )

            status = "success" if len(accepted) >= 10 else "recommendation_incomplete"
            generated_at = datetime.now(timezone.utc).isoformat()
            previous_board = self._repository.load_board(target)
            board = RecommendationBoard(
                profile_id=target,
                username=username,
                run_id=run_id,
                status=status,
                recommendations=accepted,
                generated_at=generated_at,
                message=("榜单生成成功" if status == "success" else f"仅生成 {len(accepted)} 条有效推荐"),
                previous_run_id=previous_board.run_id if previous_board else None,
            )
            stage_clock = time.monotonic()
            try:
                self._repository.save_board(board)
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
