"""Share run diagnostics, role invocation and bounded failure settlement."""

import logging
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..agent_tools.context import (
    FINAL_AGENT_ROLE,
    PRELIMINARY_AGENT_ROLE,
    PROFILE_AGENT_ROLE,
    RANKING_AGENT_ROLE,
    RETRIEVAL_AGENT_ROLE,
)
from ..model.board import RecommendationBoard
from ..model.config import configured_identities
from ..model.run import RecommendationRun
from ..storage.repository import AgentRankRepository

logger = logging.getLogger(__name__.rsplit(".", 1)[0] + ".recommendation")

_PROVENANCE_URL_PATTERN = re.compile(r"(?i)\b(?:https?|ftp)://[^\s]+")

_PROVENANCE_SECRET_PATTERN = re.compile(
    r"(?i)\b(?:authorization|cookie|api[_-]?key|llm[_-]?key|access[_-]?token|token)\b\s*[:=]\s*[^\s,;]+"
)

_PROVENANCE_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")

_PROVENANCE_HOST_PORT_PATTERN = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}:\d{2,6}")


def _safe_agent_failure_reason(value: Any) -> str:
    """把逐调用失败原因收敛为无地址和凭据的短文本。"""
    text = " ".join(str(value or "").split()).strip()
    text = _PROVENANCE_URL_PATTERN.sub("[已脱敏地址]", text)
    text = _PROVENANCE_HOST_PORT_PATTERN.sub("[已脱敏地址]", text)
    text = _PROVENANCE_BEARER_PATTERN.sub("[已脱敏凭据]", text)
    return _PROVENANCE_SECRET_PATTERN.sub("[已脱敏凭据]", text)[:240]


def _classify_agent_failure(value: Any) -> str:
    """把失败摘要归入有限类别，避免按供应商原文做长期统计。"""
    text = _safe_agent_failure_reason(value).casefold()
    if "reasoning_text" in text:
        return "upstream_reasoning"
    if "404 page not found" in text or "http 404" in text:
        return "upstream_http_not_found"
    if "tool_choice" in text:
        return "tool_choice_unsupported"
    if "already returned" in text:
        return "repeated_context_read"
    if "schema" in text:
        return "schema_validation"
    if "submission" in text:
        return "submission_required"
    if "terminal" in text:
        return "host_lifecycle"
    return "agent_execution"


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
    board: RecommendationBoard | None = None


class RecommendationRunSupport:
    """Provide phase diagnostics and settlement without retaining run-local state."""

    _repository: AgentRankRepository
    agent_adapter: Any
    _progress_callback: Callable[[Mapping[str, Any]], Any] | None

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
            RETRIEVAL_AGENT_ROLE: "run_retrieval",
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
        metrics: dict[str, Any],
        role: str,
        value: Any,
        *,
        stage: str,
        attempt: int,
        duration_ms: int,
    ) -> dict[str, Any]:
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
            "failure_class": str(raw.get("repair_failure_class") or "").strip()[:64],
            "repair_kind": str(raw.get("repair_kind") or "").strip()[:32],
            "repair_recovered": bool(raw.get("repair_recovered", False)),
        }
        for diagnostic_key in ("model_diagnostics", "output_diagnostics"):
            if isinstance(raw.get(diagnostic_key), list):
                entry[diagnostic_key] = raw[diagnostic_key][:12]
        entries = metrics.setdefault("agent_provenance", [])
        entries.append(entry)
        metrics["model_call_count"] = (
            int(metrics.get("model_call_count", 0) or 0) + model_call_count
        )
        metrics[f"{role}_model_call_count"] = (
            int(metrics.get(f"{role}_model_call_count", 0) or 0) + model_call_count
        )
        metrics["agent_repair_count"] = (
            int(metrics.get("agent_repair_count", 0) or 0) + repair_count
        )
        metrics[f"{role}_repair_count"] = (
            int(metrics.get(f"{role}_repair_count", 0) or 0) + repair_count
        )
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
        metrics["agent_model_source"] = sources[0] if len(sources) == 1 else "mixed"
        return entry

    @staticmethod
    def _finish_agent_provenance(
        entry: dict[str, Any] | None, status: str, failure_reason: Any = ""
    ) -> None:
        """完成一条逐调用记录并仅保存安全失败摘要。"""
        if not isinstance(entry, dict):
            return
        entry["status"] = str(status or "failed").strip()[:32]
        entry["failure_reason"] = _safe_agent_failure_reason(failure_reason)
        if entry["failure_reason"] and not entry.get("failure_class"):
            entry["failure_class"] = _classify_agent_failure(failure_reason)

    @staticmethod
    def _display_name(profile_id: str, config: Mapping[str, Any]) -> str:
        """返回 profile_id 对应的 Emby 显示名。"""
        for identity in configured_identities(config):
            if identity.profile_id == profile_id:
                return identity.username
        return ""

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

    def _start_stage(self, metrics: dict[str, Any], stage: str) -> None:
        """开始一个可审计运行阶段，并记录稳定执行顺序。"""
        if metrics.get("_stage_name"):
            raise RuntimeError("previous recommendation stage is still active")
        metrics.setdefault("stage_order", []).append(stage)
        metrics["_stage_name"] = stage
        metrics["_stage_started_at"] = time.monotonic()
        self._publish_progress(metrics, stage)

    @staticmethod
    def _finish_stage(metrics: dict[str, Any], status: str) -> None:
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
        metrics: dict[str, Any], stage: str, attempt: int, error: BaseException
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
        errors: list[str],
        metrics: dict[str, Any],
    ) -> None:
        """写入包含耗时和关键计数的有界运行历史。"""
        final_metrics = dict(metrics)
        final_metrics.pop("_stage_name", None)
        final_metrics.pop("_stage_started_at", None)
        final_metrics.pop("_profile_id", None)
        final_metrics.pop("_run_id", None)
        self._derive_agent_outcome_metrics(final_metrics)
        final_metrics["elapsed_ms"] = max(
            0, int((time.monotonic() - started_clock) * 1000)
        )
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

    @staticmethod
    def _derive_agent_outcome_metrics(metrics: dict[str, Any]) -> None:
        """从逐调用记录生成首轮、修正和失败统计，供 API 与页面审计。"""
        calls = [
            item
            for item in metrics.get("agent_provenance", ())
            if isinstance(item, Mapping)
        ]
        first_pass = 0
        repaired = 0
        failed = 0
        failure_classes: dict[str, int] = {}
        repair_kinds: dict[str, int] = {}
        role_counts: dict[str, dict[str, int]] = {}
        for item in calls:
            role = str(item.get("role") or "agent").strip()[:32] or "agent"
            status = str(item.get("status") or "pending").strip()
            is_repaired = (
                bool(item.get("repair_recovered"))
                or int(item.get("repair_count") or 0) > 0
            )
            bucket = role_counts.setdefault(
                role,
                {"first_pass_success": 0, "repair_success": 0, "terminal_failure": 0},
            )
            if status == "completed" and is_repaired:
                repaired += 1
                bucket["repair_success"] += 1
            elif status == "completed":
                first_pass += 1
                bucket["first_pass_success"] += 1
            elif status in {"failed", "validation_failed"}:
                failed += 1
                bucket["terminal_failure"] += 1
            failure_class = str(item.get("failure_class") or "").strip()[:64]
            if failure_class:
                failure_classes[failure_class] = (
                    failure_classes.get(failure_class, 0) + 1
                )
            repair_kind = str(item.get("repair_kind") or "").strip()[:32]
            if repair_kind:
                repair_kinds[repair_kind] = repair_kinds.get(repair_kind, 0) + 1
        metrics["agent_first_pass_success_count"] = first_pass
        metrics["agent_repair_success_count"] = repaired
        metrics["agent_terminal_failure_count"] = failed
        metrics["agent_failure_class_counts"] = failure_classes
        metrics["agent_repair_kind_counts"] = repair_kinds
        metrics["agent_outcome_by_role"] = role_counts

    def _failure(
        self,
        profile_id: str,
        username: str,
        run_id: str,
        status: str,
        message: str,
        started_at: str,
        started_clock: float,
        metrics: dict[str, Any],
        errors: list[str],
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
