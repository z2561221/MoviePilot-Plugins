"""AgentRank 数据保留、脱敏导出和分级重置服务。"""

import hashlib
import hmac
import re
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping, Optional

class DataLifecycleError(Exception):
    """表示数据生命周期操作可安全显示给用户的错误。"""

    def __init__(self, code: str, message: str, status_code: int = 409):
        """保存稳定错误码、用户文案和 HTTP 状态码。"""
        self.code = str(code)
        self.message = str(message)
        self.status_code = int(status_code)
        super().__init__(self.message)


@dataclass(frozen=True)
class DataRetentionPolicy:
    """AgentRank 自有数据的有界保留策略。"""

    candidate_snapshot_limit: int = 20
    feedback_event_limit: int = 1000
    feedback_queue_limit: int = 200
    conversation_message_limit: int = 200
    attribution_record_limit: int = 500
    analysis_record_limit: int = 500

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] = None) -> "DataRetentionPolicy":
        """从配置读取安全有界的保留上限。"""
        raw = value if isinstance(value, Mapping) else {}

        def bounded(name: str, default: int, maximum: int) -> int:
            """读取一个正整数保留上限并在无效时回退默认值。"""
            try:
                return max(1, min(int(raw.get(name, default)), maximum))
            except (TypeError, ValueError):
                return default

        return cls(
            candidate_snapshot_limit=bounded("candidate_snapshot_limit", 20, 500),
            feedback_event_limit=bounded("feedback_event_limit", 1000, 100000),
            feedback_queue_limit=bounded("feedback_queue_limit", 200, 100000),
            conversation_message_limit=bounded(
                "conversation_message_limit", 200, 100000
            ),
            attribution_record_limit=bounded(
                "attribution_record_limit", 500, 100000
            ),
            analysis_record_limit=bounded("analysis_record_limit", 500, 100000),
        )

    def to_dict(self) -> Dict[str, int]:
        """返回可显示的保留策略，不包含任何用户数据。"""
        return {
            "candidate_snapshot_limit": self.candidate_snapshot_limit,
            "feedback_event_limit": self.feedback_event_limit,
            "feedback_queue_limit": self.feedback_queue_limit,
            "conversation_message_limit": self.conversation_message_limit,
            "attribution_record_limit": self.attribution_record_limit,
            "analysis_record_limit": self.analysis_record_limit,
        }


_URL_PATTERN = re.compile(r"(?i)\b(?:https?|ftp)://[^\s]+")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:authorization|cookie|api[_-]?key|llm[_-]?key|access[_-]?token|token)\b\s*[:=]\s*[^\s,;]+"
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
_HOST_PORT_PATTERN = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}:\d{2,6}")


def _redact_text(value: Any) -> str:
    """对导出文本去除 URL、授权片段和常见密钥赋值。"""
    text = str(value or "")
    text = _URL_PATTERN.sub("[已脱敏地址]", text)
    text = _HOST_PORT_PATTERN.sub("[已脱敏地址]", text)
    text = _BEARER_PATTERN.sub("[已脱敏凭据]", text)
    return _SECRET_ASSIGNMENT.sub("[已脱敏凭据]", text)


def _safe_scalar(value: Any) -> Any:
    """仅保留 JSON 基本值并对字符串执行脱敏。"""
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    return _redact_text(value)


def _safe_nonnegative_int(value: Any, default: int = 0) -> int:
    """把不可信导出计数规范为非负整数。"""
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return max(0, int(default))


class DataLifecycleService:
    """协调 profile 数据的保留、导出和两种重置。"""

    def __init__(self, repository: Any, config: Mapping[str, Any] = None):
        """绑定仓储并从当前配置构造有界保留策略。"""
        self.repository = repository
        self.config = dict(config or {})
        self.policy = DataRetentionPolicy.from_mapping(self.config)

    def prune_profile(self, profile_id: str) -> Dict[str, int]:
        """执行一次有界裁剪；任何失败都由调用方决定是否显式提示。"""
        target = str(profile_id or "").strip()
        if not target:
            raise DataLifecycleError("profile_id_required", "必须指定 profile_id", 422)
        result = {
            "candidate_snapshots": self.repository.prune_candidate_snapshots(
                target, self.policy.candidate_snapshot_limit
            ),
            "feedback_events": self.repository.prune_feedback_events(
                target, self.policy.feedback_event_limit
            ),
            "feedback_queue": self.repository.prune_learning_list(
                target, "feedback_queue", self.policy.feedback_queue_limit
            ),
            "conversation_messages": self.repository.prune_learning_list(
                target,
                "conversation_messages",
                self.policy.conversation_message_limit,
            ),
            "attribution": self.repository.prune_learning_list(
                target, "attribution", self.policy.attribution_record_limit
            ),
            "analysis": self.repository.prune_learning_list(
                target, "agent_analysis", self.policy.analysis_record_limit
            ),
            "memory_proposals": self.repository.prune_learning_list(
                target, "memory_proposals", self.policy.analysis_record_limit
            ),
            "pending_questions": self.repository.prune_learning_list(
                target, "pending_questions", self.policy.analysis_record_limit
            ),
        }
        return result

    @staticmethod
    def _safe_support(value: Any) -> Optional[Dict[str, Any]]:
        """按白名单导出可重算支持度，不复制任意嵌套载荷。"""
        if not isinstance(value, Mapping):
            return None
        contributions = []
        for item in value.get("contributions") or []:
            if not isinstance(item, Mapping):
                continue
            contributions.append(
                {
                    "dimension": _redact_text(item.get("dimension")),
                    "direction": _redact_text(item.get("direction")),
                    "user_value": _redact_text(item.get("user_value")),
                    "candidate_value": _redact_text(item.get("candidate_value")),
                    "user_refs": [
                        _safe_scalar(ref) for ref in item.get("user_refs") or []
                    ],
                    "candidate_ref": _safe_scalar(item.get("candidate_ref")),
                    "weight_units": int(item.get("weight_units") or 0),
                    "certainty_units": int(item.get("certainty_units") or 0),
                    "contribution_units": int(
                        item.get("contribution_units") or 0
                    ),
                }
            )
        return {
            "policy_version": _safe_scalar(value.get("policy_version")),
            "positive_units": int(value.get("positive_units") or 0),
            "counter_units": int(value.get("counter_units") or 0),
            "available_units": int(value.get("available_units") or 0),
            "net_units": int(value.get("net_units") or 0),
            "percentage": int(value.get("percentage") or 0),
            "contributions": contributions,
        }

    @staticmethod
    def _safe_recommendation(item: Mapping[str, Any]) -> Dict[str, Any]:
        """导出榜单条目的安全白名单。"""
        return {
            "candidate_id": _safe_scalar(item.get("candidate_id")),
            "rank": int(item.get("rank") or 0),
            "title": _redact_text(item.get("title")),
            "media_type": _redact_text(item.get("media_type")),
            "year": item.get("year"),
            "summary": _redact_text(item.get("summary")),
            "reason": _redact_text(item.get("reason")),
            "analysis_id": _safe_scalar(item.get("analysis_id")),
            "support": DataLifecycleService._safe_support(item.get("support")),
            "selection_source": (
                str(item.get("selection_source") or "legacy")
                if str(item.get("selection_source") or "legacy")
                in {"legacy", "agent", "safe_fallback"}
                else "legacy"
            ),
            "source_ids": {
                str(key): _safe_scalar(value)
                for key, value in dict(item.get("source_ids") or {}).items()
                if str(key) in {"tmdb", "douban", "bangumi", "anilist"}
            },
        }

    @staticmethod
    def _safe_metrics(metrics: Mapping[str, Any]) -> Dict[str, Any]:
        """只导出运行历史中可审计的模型来源和数量指标。"""
        allowed = {
            "elapsed_ms",
            "agent_calls",
            "model_call_count",
            "agent_model",
            "agent_provider",
            "agent_model_source",
            "agent_provenance",
            "profile_agent_model",
            "profile_agent_source",
            "ranking_agent_model",
            "ranking_agent_source",
            "copy_agent_model",
            "copy_agent_source",
            "final_count",
            "candidate_count",
            "profile_evidence_count",
            "playback_count",
            "policy_version",
            "policy_memory_revision",
            "policy_algorithm_version",
            "policy_evidence_count",
            "support_scored_count",
            "support_min",
            "support_max",
            "agent_selected_count",
            "safe_fallback_selected_count",
            "selection_source_counts",
            "recommendation_analysis_count",
            "copy_rewrite_attempted",
            "copy_rewrite_candidate_count",
            "copy_rewrite_success_count",
            "copy_template_fallback_count",
        }
        result: Dict[str, Any] = {}
        for key in allowed:
            if key not in (metrics or {}):
                continue
            value = metrics[key]
            if key == "agent_provenance" and isinstance(value, list):
                result[key] = [
                    {
                        "role": _redact_text(item.get("role"))[:32],
                        "stage": _redact_text(item.get("stage"))[:32],
                        "attempt": max(
                            1, _safe_nonnegative_int(item.get("attempt"), 1)
                        ),
                        "provider_id": _redact_text(item.get("provider_id"))[:160],
                        "selected_provider_name": _redact_text(
                            item.get("selected_provider_name")
                        )[:160],
                        "provider": _redact_text(item.get("provider"))[:160],
                        "model": _redact_text(item.get("model"))[:160],
                        "source": _redact_text(item.get("source"))[:32],
                        "model_call_count": _safe_nonnegative_int(
                            item.get("model_call_count")
                        ),
                        "duration_ms": _safe_nonnegative_int(
                            item.get("duration_ms")
                        ),
                        "status": _redact_text(item.get("status"))[:32],
                        "failure_reason": _redact_text(
                            item.get("failure_reason")
                        )[:240],
                    }
                    for item in value
                    if isinstance(item, Mapping)
                ]
            elif key == "selection_source_counts" and isinstance(value, Mapping):
                result[key] = {
                    source: max(0, int(value.get(source) or 0))
                    for source in ("agent", "safe_fallback")
                }
            else:
                result[key] = _safe_scalar(value)
        return result

    @staticmethod
    def _safe_analysis_evidence(value: Any) -> Dict[str, Any]:
        """按字段白名单导出一项分析证据并脱敏用户可见文本。"""
        raw = value.to_dict() if hasattr(value, "to_dict") else dict(value or {})
        return {
            "direction": _redact_text(raw.get("direction")),
            "dimension": _redact_text(raw.get("dimension")),
            "user_value": _redact_text(raw.get("user_value")),
            "candidate_value": _redact_text(raw.get("candidate_value")),
            "user_refs": [_safe_scalar(item) for item in raw.get("user_refs") or ()],
            "candidate_ref": _safe_scalar(raw.get("candidate_ref")),
            "weight_units": max(0, int(raw.get("weight_units") or 0)),
            "certainty_units": max(0, int(raw.get("certainty_units") or 0)),
            "contribution_units": max(0, int(raw.get("contribution_units") or 0)),
        }

    def export_profile(self, profile_id: str) -> Dict[str, Any]:
        """按字段白名单导出 profile，绝不复制原始插件载荷或思维链。"""
        target = str(profile_id or "").strip()
        if not target:
            raise DataLifecycleError("profile_id_required", "必须指定 profile_id", 422)
        repository = self.repository
        profile = repository.load_profile(target)
        board = repository.load_board(target)
        archive = repository.load_archive(target)
        preferences = repository.load_profile_preferences(target)
        playback = repository.load_playback_snapshot(target)
        history = repository.load_run_history(target)
        memory = repository.load_preference_memory(target)
        policy_snapshot = repository.load_policy_snapshot(target)
        feedback = repository.load_feedback_events(target)
        feedback_queue = repository.load_feedback_queue(target)
        feedback_understandings = repository.load_feedback_understandings(target)
        recommendation_analyses = repository.load_recommendation_analyses(target)
        memory_proposals = repository.load_memory_proposals(target)
        pending_questions = repository.load_pending_questions(target)
        conversation_thread = repository.load_conversation_thread(target)
        conversation_messages, conversation_commands = (
            repository.load_conversation_records(target)
        )
        outcome_attributions = repository.load_outcome_attributions(target)
        board_consumptions = repository.load_board_consumptions(target)
        short_term_signals = repository.load_short_term_signals(target)
        adaptive_fingerprints = repository.load_adaptive_fingerprints(target)
        learning_health = repository.build_learning_health(target)
        snapshot_refs = repository.candidate_snapshot_references(target)

        profile_data = None
        if profile is not None:
            profile_data = {
                "summary": _redact_text(profile.summary),
                "tags": [_redact_text(item) for item in profile.tags],
                "negative_tags": [_redact_text(item) for item in profile.negative_tags],
                "playback_count": profile.playback_count,
                "generated_at": _redact_text(profile.generated_at),
                "schema_version": profile.schema_version,
            }

        board_data = None
        if board is not None:
            board_data = {
                "run_id": _safe_scalar(board.run_id),
                "status": _redact_text(board.status),
                "generated_at": _redact_text(board.generated_at),
                "message": _redact_text(board.message),
                "recommendations": [
                    self._safe_recommendation(asdict(item))
                    for item in board.recommendations
                ],
            }

        feedback_data = [
            {
                "event_id": _safe_scalar(event.event_id),
                "sequence": event.sequence,
                "kind": _redact_text(event.kind),
                "candidate_id": _safe_scalar(event.candidate_id),
                "run_id": _safe_scalar(event.run_id),
                "analysis_id": _safe_scalar(event.analysis_id),
                "comment": _redact_text(event.comment),
                "created_at": _redact_text(event.created_at),
                "supersedes": _safe_scalar(event.supersedes),
                "status": _redact_text(event.status),
            }
            for event in feedback
        ]

        memory_data = [
            {
                "item_id": _safe_scalar(item.item_id),
                "category": _redact_text(item.category),
                "value": _redact_text(item.value),
                "polarity": _redact_text(item.polarity),
                "strength": item.strength,
                "certainty": item.certainty,
                "evidence_refs": [_safe_scalar(ref) for ref in item.evidence_refs],
                "source_event_sequence": item.source_event_sequence,
                "created_at": _redact_text(item.created_at),
                "status": _redact_text(item.status),
                "tombstone": item.tombstone,
                "supersedes": [_safe_scalar(ref) for ref in item.supersedes],
            }
            for item in memory.items
        ]

        return {
            "schema_version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "profile_id": _safe_scalar(target),
            "retention_policy": self.policy.to_dict(),
            "profile": profile_data,
            "preferences": {
                "custom_tags": [_redact_text(item) for item in preferences.custom_tags],
                "custom_negative_tags": [
                    _redact_text(item) for item in preferences.custom_negative_tags
                ],
                "archived_tags": [_redact_text(item) for item in preferences.archived_tags],
                "archived_negative_tags": [
                    _redact_text(item) for item in preferences.archived_negative_tags
                ],
            },
            "playback": (
                {
                    "source": _redact_text(playback.source),
                    "status": _redact_text(playback.status),
                    "confidence": _redact_text(playback.confidence),
                    "sample_count": playback.sample_count,
                    "mapped_count": playback.mapped_count,
                    "unmapped_count": playback.unmapped_count,
                    "synced_at": _redact_text(playback.synced_at),
                }
                if playback is not None
                else None
            ),
            "board": board_data,
            "archive": [
                {
                    "candidate_id": _safe_scalar(entry.candidate_id),
                    "original_rank": entry.original_rank,
                    "archived_at": _redact_text(entry.archived_at),
                    "reason": _redact_text(entry.reason),
                }
                for entry in archive.entries
            ],
            "run_history": [
                {
                    "run_id": _safe_scalar(run.run_id),
                    "status": _redact_text(run.status),
                    "started_at": _redact_text(run.started_at),
                    "finished_at": _redact_text(run.finished_at),
                    "message": _redact_text(run.message),
                    "metrics": self._safe_metrics(run.metrics),
                }
                for run in history
            ],
            "candidate_snapshots": [
                {
                    "run_id": _safe_scalar(item.get("run_id")),
                    "generated_at": _redact_text(item.get("generated_at")),
                }
                for item in snapshot_refs
            ],
            "feedback_events": feedback_data,
            "feedback_queue": [
                {
                    "job_id": _safe_scalar(job.job_id),
                    "event_id": _safe_scalar(job.event_id),
                    "event_sequence": job.event_sequence,
                    "status": _redact_text(job.status),
                    "attempts": job.attempts,
                    "max_attempts": job.max_attempts,
                    "created_at": _redact_text(job.created_at),
                    "updated_at": _redact_text(job.updated_at),
                    "next_attempt_at": _redact_text(job.next_attempt_at),
                }
                for job in feedback_queue
            ],
            "feedback_understandings": [
                {
                    "record_id": _safe_scalar(record.record_id),
                    "event_id": _safe_scalar(record.event_id),
                    "event_sequence": record.event_sequence,
                    "candidate_id": _safe_scalar(record.candidate_id),
                    "action": _redact_text(record.action),
                    "outcome": _redact_text(record.outcome),
                    "restatement": _redact_text(record.restatement),
                    "signals": [
                        {
                            "category": _redact_text(signal.category),
                            "value": _redact_text(signal.value),
                            "polarity": _redact_text(signal.polarity),
                            "certainty": signal.certainty,
                            "evidence_refs": [
                                _safe_scalar(ref) for ref in signal.evidence_refs
                            ],
                        }
                        for signal in record.signals
                    ],
                    "conflicts": [
                        {
                            str(key): _safe_scalar(value)
                            for key, value in dict(conflict).items()
                            if str(key)
                            in {"memory_item_id", "category", "value", "reason"}
                        }
                        for conflict in record.conflicts
                    ],
                    "uncertainties": [
                        _redact_text(item) for item in record.uncertainties
                    ],
                    "persona_version": _redact_text(record.persona_version),
                    "skills_version": _redact_text(record.skills_version),
                    "prompt_fingerprint": _redact_text(record.prompt_fingerprint),
                    "memory_revision": record.memory_revision,
                    "provider": _redact_text(record.provider),
                    "model": _redact_text(record.model),
                    "model_source": _redact_text(record.model_source),
                    "model_call_count": record.model_call_count,
                    "analysis_revision_id": _safe_scalar(
                        record.analysis_revision_id
                    ),
                    "analysis_revision_reason": _redact_text(
                        record.analysis_revision_reason
                    ),
                    "analysis_revision_note": _redact_text(
                        record.analysis_revision_note
                    ),
                    "created_at": _redact_text(record.created_at),
                    "status": _redact_text(record.status),
                }
                for record in feedback_understandings
            ],
            "recommendation_analyses": [
                {
                    "analysis_id": _safe_scalar(record.analysis_id),
                    "candidate_id": _safe_scalar(record.candidate_id),
                    "run_id": _safe_scalar(record.run_id),
                    "selection_source": _redact_text(record.selection_source),
                    "summary": _redact_text(record.summary),
                    "reason": _redact_text(record.reason),
                    "positive_evidence": [
                        self._safe_analysis_evidence(item)
                        for item in record.positive_evidence
                    ],
                    "counter_evidence": [
                        self._safe_analysis_evidence(item)
                        for item in record.counter_evidence
                    ],
                    "uncertainties": [_redact_text(item) for item in record.uncertainties],
                    "data_sources": [_redact_text(item) for item in record.data_sources],
                    "support_percentage": record.support_percentage,
                    "policy_version": _redact_text(record.policy_version),
                    "memory_revision": record.memory_revision,
                    "persona_version": _redact_text(record.persona_version),
                    "skills_version": _redact_text(record.skills_version),
                    "prompt_fingerprint": _safe_scalar(record.prompt_fingerprint),
                    "supersedes": _safe_scalar(record.supersedes),
                    "status": _redact_text(record.status),
                    "created_at": _redact_text(record.created_at),
                }
                for record in recommendation_analyses
            ],
            "memory_proposals": [
                {
                    "proposal_id": _safe_scalar(proposal.proposal_id),
                    "event_id": _safe_scalar(proposal.event_id),
                    "event_sequence": proposal.event_sequence,
                    "candidate_id": _safe_scalar(proposal.candidate_id),
                    "understanding_record_id": _safe_scalar(
                        proposal.understanding_record_id
                    ),
                    "restatement": _redact_text(proposal.restatement),
                    "changes": [
                        {
                            "change_id": _safe_scalar(change.change_id),
                            "operation": _redact_text(change.operation),
                            "category": _redact_text(change.category),
                            "value": _redact_text(change.value),
                            "polarity": _redact_text(change.polarity),
                            "certainty": change.certainty,
                            "evidence_refs": [
                                _safe_scalar(ref) for ref in change.evidence_refs
                            ],
                            "preview": _redact_text(change.preview),
                            "target_memory_item_ids": [
                                _safe_scalar(item_id)
                                for item_id in change.target_memory_item_ids
                            ],
                        }
                        for change in proposal.changes
                    ],
                    "evidence_refs": [
                        _safe_scalar(ref) for ref in proposal.evidence_refs
                    ],
                    "impact_preview": [
                        _redact_text(item) for item in proposal.impact_preview
                    ],
                    "expected_memory_revision": proposal.expected_memory_revision,
                    "created_at": _redact_text(proposal.created_at),
                    "expires_at": _redact_text(proposal.expires_at),
                    "status": _redact_text(proposal.status),
                    "supersedes": _safe_scalar(proposal.supersedes),
                    "resolved_at": _redact_text(proposal.resolved_at),
                    "resolved_by_mp_user_id": _safe_scalar(
                        proposal.resolved_by_mp_user_id
                    ),
                    "resolved_memory_revision": proposal.resolved_memory_revision,
                    "projected_memory_item_ids": [
                        _safe_scalar(item)
                        for item in proposal.projected_memory_item_ids
                    ],
                    "resolution_reason": _redact_text(
                        proposal.resolution_reason
                    ),
                }
                for proposal in memory_proposals
            ],
            "pending_questions": [
                {
                    "question_id": _safe_scalar(question.question_id),
                    "event_id": _safe_scalar(question.event_id),
                    "event_sequence": question.event_sequence,
                    "candidate_id": _safe_scalar(question.candidate_id),
                    "understanding_record_id": _safe_scalar(
                        question.understanding_record_id
                    ),
                    "question": _redact_text(question.question),
                    "options": [
                        {
                            "option_id": _safe_scalar(option.option_id),
                            "label": _redact_text(option.label),
                        }
                        for option in question.options
                    ],
                    "allow_custom_answer": question.allow_custom_answer,
                    "uncertainties": [
                        _redact_text(item) for item in question.uncertainties
                    ],
                    "evidence_refs": [
                        _safe_scalar(ref) for ref in question.evidence_refs
                    ],
                    "expected_memory_revision": question.expected_memory_revision,
                    "created_at": _redact_text(question.created_at),
                    "expires_at": _redact_text(question.expires_at),
                    "status": _redact_text(question.status),
                    "supersedes": _safe_scalar(question.supersedes),
                    "selected_option_id": _safe_scalar(
                        question.selected_option_id
                    ),
                    "answer_text": _redact_text(question.answer_text),
                    "answer_event_id": _safe_scalar(question.answer_event_id),
                    "answered_by_mp_user_id": _safe_scalar(
                        question.answered_by_mp_user_id
                    ),
                    "resolved_at": _redact_text(question.resolved_at),
                }
                for question in pending_questions
            ],
            "conversation": {
                "thread": (
                    {
                        "thread_id": _safe_scalar(conversation_thread.thread_id),
                        "revision": conversation_thread.revision,
                        "status": _redact_text(conversation_thread.status),
                        "summary": _redact_text(conversation_thread.summary),
                        "last_message_id": _safe_scalar(
                            conversation_thread.last_message_id
                        ),
                        "related_event_refs": [
                            _safe_scalar(item)
                            for item in conversation_thread.related_event_refs
                        ],
                        "related_analysis_ids": [
                            _safe_scalar(item)
                            for item in conversation_thread.related_analysis_ids
                        ],
                        "pending_command_ids": [
                            _safe_scalar(item)
                            for item in conversation_thread.pending_command_ids
                        ],
                        "created_at": _redact_text(
                            conversation_thread.created_at
                        ),
                        "updated_at": _redact_text(
                            conversation_thread.updated_at
                        ),
                    }
                    if conversation_thread is not None
                    else None
                ),
                "messages": [
                    {
                        "message_id": _safe_scalar(message.message_id),
                        "role": _redact_text(message.role),
                        "content": _redact_text(message.content),
                        "status": _redact_text(message.status),
                        "created_at": _redact_text(message.created_at),
                        "reply_to": _safe_scalar(message.reply_to),
                        "related_candidate_ids": [
                            _safe_scalar(item)
                            for item in message.related_candidate_ids
                        ],
                        "related_analysis_ids": [
                            _safe_scalar(item)
                            for item in message.related_analysis_ids
                        ],
                        "command_ids": [
                            _safe_scalar(item) for item in message.command_ids
                        ],
                        "error_code": _redact_text(message.error_code),
                        "error_message": _redact_text(message.error_message),
                        "provider": _redact_text(message.provider),
                        "model": _redact_text(message.model),
                    }
                    for message in conversation_messages
                ],
                "commands": [
                    {
                        "command_id": _safe_scalar(command.command_id),
                        "source_message_id": _safe_scalar(
                            command.source_message_id
                        ),
                        "kind": _redact_text(command.kind),
                        "title": _redact_text(command.title),
                        "preview": _redact_text(command.preview),
                        "payload": {
                            str(key): _safe_scalar(value)
                            for key, value in dict(command.payload).items()
                        },
                        "status": _redact_text(command.status),
                        "requires_superuser": command.requires_superuser,
                        "supersedes": _safe_scalar(command.supersedes),
                        "created_at": _redact_text(command.created_at),
                        "resolved_at": _redact_text(command.resolved_at),
                        "execution_code": _redact_text(command.execution_code),
                        "execution_message": _redact_text(
                            command.execution_message
                        ),
                    }
                    for command in conversation_commands
                ],
            },
            "preference_memory": {
                "memory_revision": memory.memory_revision,
                "last_event_sequence": memory.last_event_sequence,
                "items": memory_data,
            },
            "outcome_attributions": [
                {
                    "attribution_id": _safe_scalar(item.attribution_id),
                    "run_id": _safe_scalar(item.run_id),
                    "candidate_id": _safe_scalar(item.candidate_id),
                    "title": _redact_text(item.title),
                    "media_type": _redact_text(item.media_type),
                    "state": _redact_text(item.state),
                    "native_drawer_opened_at": _redact_text(
                        item.native_drawer_opened_at
                    ),
                    "subscription_observed_at": _redact_text(
                        item.subscription_observed_at
                    ),
                    "library_observed_at": _redact_text(
                        item.library_observed_at
                    ),
                    "playback_observed_at": _redact_text(
                        item.playback_observed_at
                    ),
                    "verification_status": _redact_text(
                        item.verification_status
                    ),
                    "verification_code": _redact_text(item.verification_code),
                    "last_checked_at": _redact_text(item.last_checked_at),
                    "revision": item.revision,
                }
                for item in outcome_attributions
            ],
            "board_consumptions": [
                {
                    "run_id": _safe_scalar(item.run_id),
                    "board_revision": item.board_revision,
                    "exposed_at": _redact_text(item.exposed_at),
                    "exposed_candidate_ids": [
                        _safe_scalar(candidate_id)
                        for candidate_id in item.exposed_candidate_ids
                    ],
                    "detail_opened_candidate_ids": [
                        _safe_scalar(candidate_id)
                        for candidate_id in item.detail_opened_candidate_ids
                    ],
                    "interaction_kinds": [
                        _redact_text(kind) for kind in item.interaction_kinds
                    ],
                    "exposure_count": item.exposure_count,
                    "detail_open_count": item.detail_open_count,
                }
                for item in board_consumptions
            ],
            "short_term_signals": [
                {
                    "kind": _redact_text(item.kind),
                    "candidate_id": _safe_scalar(item.candidate_id),
                    "run_id": _safe_scalar(item.run_id),
                    "board_revision": item.board_revision,
                    "strength": item.strength,
                    "decay_days": item.decay_days,
                    "observed_at": _redact_text(item.observed_at),
                    "source": _redact_text(item.source),
                    "polarity": _redact_text(item.polarity),
                }
                for item in short_term_signals
            ],
            "adaptive_fingerprints": (
                {
                    "source_fingerprint": _safe_scalar(
                        adaptive_fingerprints.source_fingerprint
                    ),
                    "preference_fingerprint": _safe_scalar(
                        adaptive_fingerprints.preference_fingerprint
                    ),
                    "consumption_fingerprint": _safe_scalar(
                        adaptive_fingerprints.consumption_fingerprint
                    ),
                    "generated_at": _redact_text(adaptive_fingerprints.generated_at),
                }
                if adaptive_fingerprints is not None
                else None
            ),
            "learning_health": learning_health.to_dict(),
            "policy_snapshot": (
                policy_snapshot.to_dict() if policy_snapshot is not None else None
            ),
        }

    def reset_learning(self, profile_id: str, confirmed: bool) -> Dict[str, Any]:
        """执行仅学习重置；未明确确认时不产生任何写入。"""
        if confirmed is not True:
            raise DataLifecycleError(
                "confirmation_required", "重置交互学习需要明确确认", 409
            )
        target = str(profile_id or "").strip()
        if not target:
            raise DataLifecycleError("profile_id_required", "必须指定 profile_id", 422)
        removed = self.repository.reset_learning_data(target)
        return {
            "profile_id": target,
            "mode": "learning",
            "removed_keys": len(removed),
            "preserved": [
                "profile_snapshot",
                "recommendation_board",
                "archive",
                "profile_preferences",
                "playback_snapshot",
                "run_history",
                "moviepilot_subscriptions",
                "moviepilot_library",
            ],
        }

    def prepare_full_reset(self, profile_id: str, requester_id: str) -> Dict[str, Any]:
        """生成短时一次性确认令牌，只持久化令牌哈希。"""
        target = str(profile_id or "").strip()
        requester = str(requester_id or "").strip()
        if not target:
            raise DataLifecycleError("profile_id_required", "必须指定 profile_id", 422)
        if not requester:
            raise DataLifecycleError("requester_required", "无法识别操作用户", 403)
        token = secrets.token_urlsafe(32)
        issued = datetime.now(timezone.utc)
        expires = issued + timedelta(minutes=5)
        record = {
            "token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
            "requester_id": requester,
            "issued_at": issued.isoformat(),
            "expires_at": expires.isoformat(),
        }
        self.repository.save_reset_confirmation(target, record)
        return {
            "profile_id": target,
            "confirmation_token": token,
            "expires_at": expires.isoformat(),
            "warning": "该令牌仅用于确认删除 AgentRank 自有数据，不会删除 MoviePilot 订阅或媒体库。",
        }

    def reset_full(
        self,
        profile_id: str,
        requester_id: str,
        confirmation_token: str,
    ) -> Dict[str, Any]:
        """校验一次性令牌后执行彻底重置；失败保留旧状态。"""
        target = str(profile_id or "").strip()
        requester = str(requester_id or "").strip()
        token = str(confirmation_token or "").strip()
        if not target:
            raise DataLifecycleError("profile_id_required", "必须指定 profile_id", 422)
        if not token:
            raise DataLifecycleError("confirmation_required", "需要清空全部数据确认令牌", 409)
        record = self.repository.load_reset_confirmation(target)
        if record is None:
            raise DataLifecycleError("confirmation_missing", "确认令牌不存在或已失效", 409)
        if str(record.get("requester_id") or "") != requester:
            raise DataLifecycleError("confirmation_forbidden", "确认令牌不属于当前用户", 403)
        try:
            expires = datetime.fromisoformat(str(record.get("expires_at") or ""))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
        except ValueError:
            expires = datetime.min.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expires:
            self.repository.delete_reset_confirmation(target)
            raise DataLifecycleError("confirmation_expired", "确认令牌已过期，请重新发起", 409)
        expected = str(record.get("token_hash") or "")
        actual = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if not expected or not hmac.compare_digest(expected, actual):
            raise DataLifecycleError("confirmation_invalid", "确认令牌不正确", 409)
        removed = self.repository.reset_all_profile_data(target)
        return {
            "profile_id": target,
            "mode": "full",
            "removed_keys": len(removed),
            "preserved": ["moviepilot_subscriptions", "moviepilot_library", "plugin_config"],
        }
