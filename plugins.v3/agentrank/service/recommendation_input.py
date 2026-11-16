"""Own probe, playback, policy and profile preparation as one input phase."""

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..agent_tools.context import PROFILE_AGENT_ROLE, build_trusted_context
from ..model.config import WEIGHT_DEFAULTS
from ..model.memory import PreferenceMemory
from ..model.playback import PlaybackSnapshot
from ..model.policy import PolicySnapshot
from ..model.profile import PROFILE_SCHEMA_VERSION, UserProfile
from ..model.profile_preferences import ProfilePreferences
from .prompt import DEFAULT_PROFILE_PROMPT, build_profile_prompt
from .recommendation_support import RecommendationRunResult, RecommendationRunSupport
from .validation import AgentOutputError

logger = logging.getLogger(__name__.rsplit(".", 1)[0] + ".recommendation")


@dataclass(frozen=True)
class RecommendationRunContext:
    """Carry run identity and shared diagnostics without copying phase artifacts."""

    profile_id: str
    username: str
    run_id: str
    started_at: str
    started_clock: float
    metrics: dict[str, Any]
    errors: list[str]


@dataclass(frozen=True)
class RecommendationInputs:
    """Return only the five artifacts consumed by subsequent recommendation phases."""

    playback_snapshot: PlaybackSnapshot
    policy_snapshot: PolicySnapshot
    confirmed_memory: PreferenceMemory
    current_profile: UserProfile
    profile_preferences: ProfilePreferences


class RecommendationInputStage(RecommendationRunSupport):
    """Own input preparation while reusing the run's diagnostics and role budget."""

    _playback_service: Any
    _policy_service: Any
    _profile_parser: Any

    @staticmethod
    def _profile_cache_reason(
        enabled: bool,
        forced_rebuild: bool,
        previous_profile: UserProfile | None,
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
    def _playback_evidence_fingerprints(playback_snapshot: Any) -> dict[str, str]:
        """按稳定样本身份计算逐条播放事实指纹。"""
        result: dict[str, str] = {}
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
        previous_profile: UserProfile | None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
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
        payload["full_sample_count"] = int(
            getattr(playback_snapshot, "sample_count", 0)
        )
        payload["removed_stable_ids"] = sorted(set(previous) - set(fingerprints))
        return payload, fingerprints

    async def _run_input_stage(
        self, context: RecommendationRunContext, config: Mapping[str, Any]
    ) -> RecommendationInputs | RecommendationRunResult:
        """Prepare validated inputs with the original phase and failure ordering."""
        target = context.profile_id
        username = context.username
        run_id = context.run_id
        started_at = context.started_at
        started_clock = context.started_clock
        metrics = context.metrics
        errors = context.errors

        self._start_stage(metrics, "probe")
        probe = getattr(self._playback_service, "probe", None)
        if callable(probe):
            capability = None
            try:
                capability = await asyncio.to_thread(probe, target, config)
                metrics["playback_probe_status"] = str(capability.status)
                metrics["playback_probe_message"] = str(capability.message or "")
            except Exception as error:
                errors.append(f"playback probe: {error}")
                metrics["playback_probe_status"] = "transient_error"
                metrics["playback_probe_message"] = "Playback Reporting 探测失败"
            probe_status = (
                str(metrics.get("playback_probe_status") or "").strip().casefold()
            )
            if probe_status in {
                "not_installed",
                "permission_error",
                "emby_unavailable",
            }:
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
            if probe_status == "transient_error":
                # 探测本身是轻量预检；瞬时失败不能截断 collect() 的快照回退。
                self._finish_stage(metrics, "degraded")
            elif bool(getattr(capability, "ready", False)):
                self._finish_stage(metrics, "ready")
            else:
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
                WEIGHT_DEFAULTS,
                playback_snapshot,
            )
            confirmed_memory = self._repository.load_preference_memory(target)
            if confirmed_memory.memory_revision != policy_snapshot.memory_revision:
                policy_snapshot = await asyncio.to_thread(
                    self._policy_service.refresh,
                    target,
                    WEIGHT_DEFAULTS,
                    playback_snapshot,
                )
                confirmed_memory = self._repository.load_preference_memory(target)
            if confirmed_memory.memory_revision != policy_snapshot.memory_revision:
                raise RuntimeError("preference memory changed after policy refresh")
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
            else "rebuild"
            if rebuild_profile
            else "stateless"
        )
        metrics["previous_profile_used"] = previous_profile is not None
        metrics["custom_preference_count"] = len(profile_preferences.custom_tags) + len(
            profile_preferences.custom_negative_tags
        )
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
        current_profile = previous_profile if profile_cache_reason == "hit" else None
        metrics["profile_agent_reused"] = current_profile is not None
        if current_profile is None:
            profile_parser = self._profile_parser
            profile_playback, playback_evidence_fingerprints = (
                self._incremental_playback_context(playback_snapshot, previous_profile)
            )
            profile_preference_context = profile_preferences.to_dict()
            profile_preference_context["confirmed_preferences"] = [
                item.to_dict() for item in confirmed_memory.active_items()
            ]
            metrics["profile_incremental"] = bool(profile_playback.get("incremental"))
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
                    previous_profile.to_dict() if previous_profile is not None else None
                ),
                profile_preferences=profile_preference_context,
                playback=profile_playback,
                profile=None,
                agent_role=PROFILE_AGENT_ROLE,
            )
            parsed_profile = None
            profile_prompt = build_profile_prompt(profile_prompt=profile_prompt_text)
            profile_attempt_errors: list[str] = []
            for attempt in range(2):
                stage_clock = time.monotonic()
                call_entry: dict[str, Any] | None = None
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
            generated_at = datetime.now(timezone.utc).isoformat()
            current_profile = UserProfile(
                profile_id=target,
                username=username,
                summary=parsed_profile.profile.summary,
                tags=profile_preferences.active_agent_tags(parsed_profile.profile.tags),
                negative_tags=profile_preferences.active_agent_negative_tags(
                    parsed_profile.profile.negative_tags
                ),
                playback_count=parsed_profile.profile.playback_count,
                playback_fingerprint=playback_fingerprint,
                preferences_fingerprint=preferences_fingerprint,
                profile_prompt_fingerprint=profile_prompt_fingerprint,
                profile_input_fingerprint=profile_input_fingerprint,
                playback_evidence_fingerprints=playback_evidence_fingerprints,
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

        return RecommendationInputs(
            playback_snapshot=playback_snapshot,
            policy_snapshot=policy_snapshot,
            confirmed_memory=confirmed_memory,
            current_profile=current_profile,
            profile_preferences=profile_preferences,
        )
