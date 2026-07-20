"""按用户锁定的 Agent 榜单推荐编排服务。"""

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Set

from ..agent_tools.context import build_trusted_context
from ..model.config import configured_identities
from ..model.board import RecommendationBoard, RecommendationItem
from ..model.profile import UserProfile
from ..model.run import RecommendationRun
from ..storage.repository import AgentRankRepository
from .prompt import build_ranking_prompt, build_refill_prompt
from .validation import AgentOutputError, AgentOutputParser, RecommendationValidator


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
        profile_service: Any,
        candidate_service: Any,
        agent_adapter: Any,
        run_id_factory: Callable[[], str] = None,
        parser: AgentOutputParser = None,
        validator: RecommendationValidator = None,
        library_adapter: Any = None,
        playback_service: Any = None,
    ):
        """注入可测试的领域依赖并初始化用户锁集合。"""
        self._repository = repository
        self._profile_service = profile_service
        self._candidate_service = candidate_service
        self.agent_adapter = agent_adapter
        self._run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)
        self._parser = parser or AgentOutputParser()
        self._validator = validator or RecommendationValidator()
        self._library_adapter = library_adapter
        self._playback_service = playback_service
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
            "profile_scope": str(config.get("profile_scope") or "all"),
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
            stage_clock = time.monotonic()
            profile_input = await asyncio.to_thread(
                self._profile_service.collect,
                target,
                profile_scope=config.get("profile_scope", "all"),
                recent_days=int(config.get("recent_days") or 365),
                sample_limit=int(config.get("subscription_sample_limit") or 200),
                minimum_samples=int(config.get("minimum_samples") or 5),
            )
            metrics["profile_collect_ms"] = max(
                0, int((time.monotonic() - stage_clock) * 1000)
            )
            metrics["subscription_count"] = profile_input.sample_count
            metrics["subscription_rejected_count"] = profile_input.rejected_count
            logger.info(
                "AgentRank 画像样本 profile_id=%s run_id=%s accepted=%s rejected=%s status=%s",
                target,
                run_id,
                profile_input.sample_count,
                profile_input.rejected_count,
                profile_input.status,
            )
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
                    metrics["playback_source"] = "subscription"
                    metrics["playback_status"] = "error"
                metrics["playback_collect_ms"] = max(
                    0, int((time.monotonic() - stage_clock) * 1000)
                )
            playback_count = playback_snapshot.sample_count if playback_snapshot is not None else 0
            evidence_count = profile_input.sample_count + playback_count
            metrics["profile_evidence_count"] = evidence_count
            if profile_input.status != "ready" and evidence_count < int(
                config.get("minimum_samples") or 5
            ):
                return self._failure(
                    target,
                    username,
                    run_id,
                    "sample_insufficient",
                    "订阅与真实播放样本均不足，未调用 Agent",
                    started_at,
                    started_clock,
                    metrics,
                    errors,
                )

            stage_clock = time.monotonic()
            candidate_result = await asyncio.to_thread(
                self._candidate_service.collect_and_freeze,
                target,
                run_id,
                config.get("discovery_sources") or {},
                int(config.get("candidate_pool_size") or 50),
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
            logger.info(
                "AgentRank TMDB候选 profile_id=%s run_id=%s accepted=%s rejected=%s source_errors=%s",
                target,
                run_id,
                len(candidates),
                candidate_result.rejected_count,
                len(candidate_result.source_errors),
            )
            if candidate_result.status != "ready" or not candidates:
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
            subscribed_ids = {sample.stable_id for sample in profile_input.samples}
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
            trusted_context = build_trusted_context(
                username=username,
                run_id=run_id,
                subscriptions=[sample.to_dict() for sample in profile_input.samples],
                previous_profile=(
                    previous_profile.to_dict() if previous_profile is not None else None
                ),
                candidates=[candidate.to_dict() for candidate in candidates],
                archive_feedback=archive.to_dict(),
                weights=self._trusted_weights(config),
                profile_preferences=profile_preferences.to_dict(),
                playback=(
                    playback_snapshot.to_dict() if playback_snapshot is not None else {
                        "source": "subscription",
                        "confidence": "low",
                        "status": "unavailable",
                        "samples": [],
                    }
                ),
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
                    stage_clock = time.monotonic()
                    raw_output = await self.agent_adapter.run(prompt, trusted_context)
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
                        "agent_failed",
                        "内置 Agent 调用失败，已保留旧榜单",
                        started_at,
                        started_clock,
                        metrics,
                        errors,
                        agent_calls=int(metrics["agent_calls"]),
                    )
                try:
                    parsed = self._parser.parse(raw_output)
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
                        "validation_failed",
                        "Agent 输出结构校验失败，已保留旧榜单",
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
                    "validation_failed",
                    "Agent 输出没有安全可用推荐，已保留旧榜单",
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
                    try:
                        refill_output = await self.agent_adapter.run(
                            build_refill_prompt(
                                [item.candidate_id for item in accepted],
                                10 - len(accepted),
                                agent_prompt=str(config.get("agent_prompt") or ""),
                            ),
                            trusted_context,
                        )
                        refill_parsed = self._parser.parse(refill_output)
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
            profile = UserProfile(
                profile_id=target,
                username=username,
                summary=validation.profile.summary,
                tags=list(validation.profile.tags),
                negative_tags=list(validation.profile.negative_tags),
                subscription_count=validation.profile.subscription_count,
                run_id=run_id,
                generated_at=generated_at,
            )
            board = RecommendationBoard(
                profile_id=target,
                username=username,
                run_id=run_id,
                status=status,
                recommendations=accepted,
                generated_at=generated_at,
                message=("榜单生成成功" if status == "success" else f"仅生成 {len(accepted)} 条有效推荐"),
                previous_run_id=(
                    self._repository.load_board(target).run_id
                    if self._repository.load_board(target)
                    else None
                ),
            )
            stage_clock = time.monotonic()
            try:
                self._repository.save_profile_and_board(profile, board)
            except Exception as error:
                errors.append(str(error))
                return self._failure(
                    target,
                    username,
                    run_id,
                    "validation_failed",
                    "画像与榜单保存失败，已恢复旧数据",
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
