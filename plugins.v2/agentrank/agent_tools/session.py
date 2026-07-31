"""AgentRank 单次 Agent 会话的无副作用结果收集器。"""

from dataclasses import dataclass, field
import json
from typing import Any, Dict, Mapping, Optional

from .context import (
    FINAL_AGENT_ROLE,
    PRELIMINARY_AGENT_ROLE,
    PROFILE_AGENT_ROLE,
    AgentRankTrustedContext,
)


RESULT_COLLECTOR_KEY = "agentrank_result_collector"
TERMINAL_AGENT_ROLES = frozenset(
    {PROFILE_AGENT_ROLE, PRELIMINARY_AGENT_ROLE, FINAL_AGENT_ROLE}
)
_EXPECTED_SUBMISSION_TOOLS = {
    PROFILE_AGENT_ROLE: "submit_agentrank_profile_result",
    PRELIMINARY_AGENT_ROLE: "submit_agentrank_batch_result",
    FINAL_AGENT_ROLE: "submit_agentrank_final_board",
}


@dataclass(frozen=True)
class SubmissionIssue:
    """一次可定向反馈给同一 Agent 会话的结构化错误。"""

    code: str
    field: str

    def to_dict(self) -> Dict[str, str]:
        """返回可安全反馈给当前 Agent 的错误字段。"""
        return {"code": self.code, "field": self.field}


@dataclass
class AgentRankSessionResultCollector:
    """只保存本会话临时提交，不接触仓储、订阅、通知或配置。"""

    trusted_context: AgentRankTrustedContext
    max_attempts: int = 2
    attempts: int = 0
    payload: Optional[Dict[str, Any]] = None
    last_issue: Optional[SubmissionIssue] = None
    _allowed_candidate_ids: frozenset[str] = field(init=False)

    def __post_init__(self) -> None:
        """按角色冻结允许提交的候选身份集合。"""
        candidates = list(self.trusted_context.candidates or ())
        if self.trusted_context.agent_role == PRELIMINARY_AGENT_ROLE:
            candidates = candidates[:5]
        elif self.trusted_context.agent_role == FINAL_AGENT_ROLE:
            candidates = candidates[:6]
        self._allowed_candidate_ids = frozenset(
            str(item.get("candidate_id") or "").strip()
            for item in candidates
            if isinstance(item, Mapping) and str(item.get("candidate_id") or "").strip()
        )

    @property
    def expected_tool(self) -> str:
        """返回当前角色唯一允许的终结提交工具。"""
        return _EXPECTED_SUBMISSION_TOOLS.get(self.trusted_context.agent_role, "")

    @property
    def submitted(self) -> bool:
        """判断当前会话是否已经接收合法终结结果。"""
        return self.payload is not None

    @property
    def can_repair(self) -> bool:
        """判断当前会话是否仍允许一次有界修正。"""
        return not self.submitted and self.attempts < self.max_attempts

    def reject(self, code: str, field_name: str) -> SubmissionIssue:
        """记录一次有界失败并返回稳定错误码与字段。"""
        if self.attempts >= self.max_attempts:
            issue = SubmissionIssue("repair_exhausted", field_name or "submission")
            self.last_issue = issue
            return issue
        self.attempts += 1
        issue = SubmissionIssue(str(code or "submission_invalid"), field_name or "submission")
        self.last_issue = issue
        return issue

    @staticmethod
    def _candidate_ids(payload: Mapping[str, Any], role: str) -> list[str]:
        """提取当前角色提交载荷中的候选身份。"""
        key = "judgments" if role == PRELIMINARY_AGENT_ROLE else "recommendations"
        return [
            str(item.get("candidate_id") or "").strip()
            for item in payload.get(key) or []
            if isinstance(item, Mapping)
        ]

    def submit(self, tool_name: str, payload: Mapping[str, Any]) -> SubmissionIssue | None:
        """校验角色、候选集合和幂等边界后接收一次临时结果。"""
        if self.submitted:
            return SubmissionIssue("duplicate_submission", "submission")
        if self.attempts >= self.max_attempts:
            return self.reject("repair_exhausted", "submission")
        self.attempts += 1
        if tool_name != self.expected_tool:
            self.last_issue = SubmissionIssue("wrong_submission_tool", "tool")
            return self.last_issue
        if self.trusted_context.agent_role in {
            PRELIMINARY_AGENT_ROLE,
            FINAL_AGENT_ROLE,
        }:
            candidate_ids = self._candidate_ids(payload, self.trusted_context.agent_role)
            if len(candidate_ids) != len(set(candidate_ids)):
                self.last_issue = SubmissionIssue(
                    "duplicate_candidate", "candidate_id"
                )
                return self.last_issue
            if any(item not in self._allowed_candidate_ids for item in candidate_ids):
                self.last_issue = SubmissionIssue(
                    "candidate_out_of_pool", "candidate_id"
                )
                return self.last_issue
            if (
                self.trusted_context.agent_role == PRELIMINARY_AGENT_ROLE
                and set(candidate_ids) != set(self._allowed_candidate_ids)
            ):
                self.last_issue = SubmissionIssue(
                    "missing_candidate", "judgments"
                )
                return self.last_issue
            if self.trusted_context.agent_role == PRELIMINARY_AGENT_ROLE:
                constraints = self.trusted_context.submission_constraints or {}
                if constraints.get("advance_quota") is not None:
                    quota = max(
                        1,
                        min(3, int(constraints.get("advance_quota") or 3)),
                    )
                    advance_count = sum(
                        bool(item.get("advance"))
                        for item in payload.get("judgments") or []
                        if isinstance(item, Mapping)
                    )
                    if advance_count > quota:
                        self.last_issue = SubmissionIssue(
                            "advance_quota_exceeded", "judgments.advance"
                        )
                        return self.last_issue
        if self.trusted_context.agent_role == PROFILE_AGENT_ROLE:
            expected_count = int(
                (self.trusted_context.playback or {}).get("sample_count") or 0
            )
            submitted_count = int(
                ((payload.get("profile") or {}).get("playback_count") or 0)
            )
            if submitted_count != expected_count:
                self.last_issue = SubmissionIssue(
                    "playback_count_mismatch", "profile.playback_count"
                )
                return self.last_issue
        self.payload = dict(payload)
        self.last_issue = None
        return None

    def result_json(self) -> str:
        """返回既有领域 parser 可直接消费的紧凑 JSON。"""
        if self.payload is None:
            raise RuntimeError("AgentRank submission result is unavailable")
        return json.dumps(self.payload, ensure_ascii=False, separators=(",", ":"))


def resolve_result_collector(agent_context: Mapping[str, Any]) -> AgentRankSessionResultCollector:
    """从工具上下文解析当前会话唯一结果收集器。"""
    collector = (
        agent_context.get(RESULT_COLLECTOR_KEY)
        if isinstance(agent_context, Mapping)
        else None
    )
    if not isinstance(collector, AgentRankSessionResultCollector):
        raise PermissionError("AgentRank result collector is missing or invalid")
    return collector
