"""按用户锁定的 Agent 榜单推荐编排服务。"""

import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Set

from ..agent_tools.context import build_trusted_context
from ..model.board import RecommendationBoard, RecommendationItem
from ..model.profile import UserProfile
from ..model.run import RecommendationRun
from ..storage.repository import AgentRankRepository
from .prompt import build_ranking_prompt, build_refill_prompt
from .validation import AgentOutputError, AgentOutputParser, RecommendationValidator


@dataclass
class RecommendationRunResult:
    """表示一次推荐请求的最终状态。"""

    username: str
    run_id: str
    status: str
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
    ):
        """注入可测试的领域依赖并初始化用户锁集合。"""
        self._repository = repository
        self._profile_service = profile_service
        self._candidate_service = candidate_service
        self.agent_adapter = agent_adapter
        self._run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)
        self._parser = parser or AgentOutputParser()
        self._validator = validator or RecommendationValidator()
        self._running_users: Set[str] = set()
        self._running_guard = threading.Lock()

    def _enter_user(self, username: str) -> bool:
        """原子登记运行用户；已运行时返回假。"""
        with self._running_guard:
            if username in self._running_users:
                return False
            self._running_users.add(username)
            return True

    def _leave_user(self, username: str) -> None:
        """释放用户运行标记。"""
        with self._running_guard:
            self._running_users.discard(username)

    @staticmethod
    def _trusted_weights(config: Mapping[str, Any]) -> Dict[str, Any]:
        """选择 Agent 允许读取的权重和筛选配置。"""
        return {
            "weights": dict(config.get("weights") or {}),
            "media_types": list(config.get("media_types") or []),
            "profile_scope": str(config.get("profile_scope") or "all"),
            "candidate_pool_size": int(config.get("candidate_pool_size") or 100),
            "confidence_threshold": float(config.get("confidence_threshold") or 0.0),
            "exclude_keywords": list(config.get("exclude_keywords") or []),
        }

    def _append_run(
        self,
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

    def _failure(
        self,
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
            username,
            run_id,
            status,
            started_at,
            started_clock,
            message,
            errors,
            metrics,
        )
        old_board = self._repository.load_board(username)
        return RecommendationRunResult(
            username=username,
            run_id=run_id,
            status=status,
            message=message,
            agent_calls=agent_calls,
            board=old_board,
        )

    async def run(
        self, username: str, config: Mapping[str, Any]
    ) -> RecommendationRunResult:
        """为一个用户执行完整推荐；同用户并发请求立即返回 running。"""
        target = str(username or "").strip()
        if not target:
            raise ValueError("username is required")
        if not self._enter_user(target):
            return RecommendationRunResult(target, "", "running", "该用户榜单正在生成")
        run_id = str(self._run_id_factory())
        started_at = datetime.now(timezone.utc).isoformat()
        started_clock = time.monotonic()
        metrics: Dict[str, Any] = {"agent_calls": 0, "refill_attempted": False}
        errors: List[str] = []
        try:
            profile_input = self._profile_service.collect(
                target,
                profile_scope=config.get("profile_scope", "all"),
                recent_days=int(config.get("recent_days") or 365),
                sample_limit=int(config.get("subscription_sample_limit") or 200),
                minimum_samples=int(config.get("minimum_samples") or 5),
            )
            metrics["subscription_count"] = profile_input.sample_count
            metrics["subscription_rejected_count"] = profile_input.rejected_count
            if profile_input.status != "ready":
                return self._failure(
                    target,
                    run_id,
                    "sample_insufficient",
                    "订阅样本不足，未调用 Agent",
                    started_at,
                    started_clock,
                    metrics,
                    errors,
                )

            candidate_result = self._candidate_service.collect_and_freeze(
                target,
                run_id,
                config.get("discovery_sources") or {},
                int(config.get("candidate_pool_size") or 100),
            )
            candidates = list(candidate_result.candidates)
            metrics["candidate_count"] = len(candidates)
            metrics["candidate_rejected_count"] = candidate_result.rejected_count
            metrics["source_errors"] = dict(candidate_result.source_errors)
            if candidate_result.status != "ready":
                return self._failure(
                    target,
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
            trusted_context = build_trusted_context(
                username=target,
                run_id=run_id,
                subscriptions=[sample.to_dict() for sample in profile_input.samples],
                candidates=[candidate.to_dict() for candidate in candidates],
                archive_feedback=archive.to_dict(),
                weights=self._trusted_weights(config),
            )

            validation = None
            for attempt in range(2):
                prompt = build_ranking_prompt()
                if attempt:
                    prompt += (
                        "\n\n上一次输出未通过严格校验。请重新读取受限工具数据，"
                        "这次只返回一个符合既定 schema 的 JSON 对象，禁止代码块、"
                        "解释、前后缀或额外字段。"
                    )
                try:
                    metrics["agent_calls"] += 1
                    raw_output = await self.agent_adapter.run(prompt, trusted_context)
                except Exception as error:
                    if attempt == 0 and bool(getattr(error, "retryable", False)):
                        errors.append(f"attempt 1: {error}")
                        continue
                    errors.append(str(error))
                    return self._failure(
                        target,
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
                    try:
                        refill_output = await self.agent_adapter.run(
                            build_refill_prompt(
                                [item.candidate_id for item in accepted],
                                10 - len(accepted),
                            ),
                            trusted_context,
                        )
                        metrics["agent_calls"] += 1
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

            status = "success" if len(accepted) >= 10 else "recommendation_incomplete"
            generated_at = datetime.now(timezone.utc).isoformat()
            profile = UserProfile(
                username=target,
                summary=validation.profile.summary,
                tags=list(validation.profile.tags),
                negative_tags=list(validation.profile.negative_tags),
                subscription_count=validation.profile.subscription_count,
                run_id=run_id,
                generated_at=generated_at,
            )
            board = RecommendationBoard(
                username=target,
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
            try:
                self._repository.save_profile_and_board(profile, board)
            except Exception as error:
                errors.append(str(error))
                return self._failure(
                    target,
                    run_id,
                    "validation_failed",
                    "画像与榜单保存失败，已恢复旧数据",
                    started_at,
                    started_clock,
                    metrics,
                    errors,
                    agent_calls=int(metrics["agent_calls"]),
                )
            metrics["final_count"] = len(accepted)
            self._append_run(
                target,
                run_id,
                status,
                started_at,
                started_clock,
                board.message,
                errors,
                metrics,
            )
            return RecommendationRunResult(
                username=target,
                run_id=run_id,
                status=status,
                message=board.message,
                final_count=len(accepted),
                agent_calls=int(metrics["agent_calls"]),
                board=board,
            )
        finally:
            self._leave_user(target)
