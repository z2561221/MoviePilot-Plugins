"""AgentRank 单次 Agent 会话的无副作用结果收集器。"""

from dataclasses import dataclass, field
import json
import re
from typing import Any, Dict, Mapping, Optional

from .context import (
    FINAL_AGENT_ROLE,
    PRELIMINARY_AGENT_ROLE,
    PROFILE_AGENT_ROLE,
    AgentRankTrustedContext,
    to_jsonable,
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
    context_read: bool = False
    _allowed_candidate_ids: frozenset[str] = field(init=False)
    _ordered_candidate_ids: tuple[str, ...] = field(init=False)
    _candidate_aliases: Dict[str, str] = field(init=False)

    def __post_init__(self) -> None:
        """按角色冻结允许提交的候选身份集合。"""
        candidates = list(self.trusted_context.candidates or ())
        if self.trusted_context.agent_role == PRELIMINARY_AGENT_ROLE:
            candidates = candidates[:5]
        elif self.trusted_context.agent_role == FINAL_AGENT_ROLE:
            candidates = candidates[:6]
        ordered_candidate_ids = [
            str(item.get("candidate_id") or "").strip()
            for item in candidates
            if isinstance(item, Mapping) and str(item.get("candidate_id") or "").strip()
        ]
        candidate_ids = frozenset(ordered_candidate_ids)
        constraints = self.trusted_context.submission_constraints or {}
        requested_ids = frozenset(
            str(item or "").strip()
            for item in constraints.get("allowed_candidate_ids") or ()
            if str(item or "").strip()
        )
        self._allowed_candidate_ids = (
            candidate_ids & requested_ids
            if self.trusted_context.agent_role == FINAL_AGENT_ROLE and requested_ids
            else candidate_ids
        )
        aliases: Dict[str, str] = {}
        allowed_order = [
            candidate_id
            for candidate_id in ordered_candidate_ids
            if candidate_id in self._allowed_candidate_ids
        ]
        self._ordered_candidate_ids = tuple(allowed_order)
        constraints = self.trusted_context.submission_constraints or {}
        explicit_refs = constraints.get("candidate_refs")
        if isinstance(explicit_refs, Mapping):
            for candidate_id, reference in explicit_refs.items():
                canonical = str(candidate_id or "").strip()
                ref = str(reference or "").strip()
                if canonical in self._allowed_candidate_ids and ref:
                    aliases[ref] = canonical
        for index, candidate_id in enumerate(allowed_order, start=1):
            aliases.setdefault(f"c{index}", candidate_id)
            aliases.setdefault(candidate_id, candidate_id)
            parts = candidate_id.split(":")
            if len(parts) == 3 and parts[0] == "tmdb":
                aliases.setdefault(f"tmdb:{parts[2]}", candidate_id)
                aliases.setdefault(parts[2], candidate_id)
        self._candidate_aliases = aliases

    @staticmethod
    def _evidence_key(value: Any) -> tuple[str, str, str]:
        """把证据声明收敛为可与候选选项精确比较的三元组。"""
        item = value if isinstance(value, Mapping) else {}
        return (
            str(item.get("dimension") or "").strip(),
            str(item.get("user_value") or "").strip(),
            str(item.get("candidate_value") or "").strip(),
        )

    def _validate_final_evidence(
        self, payload: Mapping[str, Any]
    ) -> Optional[SubmissionIssue]:
        """要求决赛逐字选择当前候选的已验证证据选项。"""
        constraints = self.trusted_context.submission_constraints or {}
        options_by_id = constraints.get("evidence_options")
        if not isinstance(options_by_id, Mapping) or not options_by_id:
            return None
        for index, recommendation in enumerate(payload.get("recommendations") or ()):
            if not isinstance(recommendation, Mapping):
                continue
            candidate_id = str(recommendation.get("candidate_id") or "").strip()
            raw_options = options_by_id.get(candidate_id)
            if not isinstance(raw_options, Mapping):
                return SubmissionIssue(
                    "evidence_options_unavailable",
                    f"recommendations.{index}.candidate_id",
                )
            for claim_key, option_key in (
                ("positive_evidence", "positive_evidence_options"),
                ("counter_evidence", "counter_evidence_options"),
            ):
                claims = list(recommendation.get(claim_key) or ())
                submitted = [self._evidence_key(item) for item in claims]
                allowed = {
                    self._evidence_key(item)
                    for item in raw_options.get(option_key) or ()
                    if isinstance(item, Mapping)
                }
                if len(submitted) != len(set(submitted)):
                    return SubmissionIssue(
                        "duplicate_evidence_option",
                        f"recommendations.{index}.{claim_key}",
                    )
                if any(item not in allowed for item in submitted):
                    return SubmissionIssue(
                        "unsupported_evidence_option",
                        f"recommendations.{index}.{claim_key}",
                    )
                if claim_key == "counter_evidence" and allowed and not submitted:
                    return SubmissionIssue(
                        "missing_counter_evidence_option",
                        f"recommendations.{index}.counter_evidence",
                    )
        return None

    def _canonicalize_final_evidence(
        self, payload: Mapping[str, Any]
    ) -> tuple[Optional[Dict[str, Any]], Optional[SubmissionIssue]]:
        """把 Agent 证据选择收敛为当前候选的已验证证据对象。"""
        constraints = self.trusted_context.submission_constraints or {}
        options_by_id = constraints.get("evidence_options")
        if not isinstance(options_by_id, Mapping) or not options_by_id:
            return dict(payload), None
        output = dict(payload)
        recommendations = []
        for index, raw_recommendation in enumerate(payload.get("recommendations") or ()):
            recommendation = dict(raw_recommendation)
            candidate_id = str(recommendation.get("candidate_id") or "").strip()
            raw_options = options_by_id.get(candidate_id)
            if not isinstance(raw_options, Mapping):
                return None, SubmissionIssue(
                    "evidence_options_unavailable",
                    f"recommendations.{index}.candidate_id",
                )
            for claim_key, option_key in (
                ("positive_evidence", "positive_evidence_options"),
                ("counter_evidence", "counter_evidence_options"),
            ):
                claims = []
                available = [
                    to_jsonable(item)
                    for item in raw_options.get(option_key) or ()
                    if isinstance(item, Mapping)
                ]
                prefix = "p" if option_key.startswith("positive") else "c"
                for claim in recommendation.get(claim_key) or ():
                    resolved = None
                    if isinstance(claim, Mapping) and claim.get("evidence_ref"):
                        raw_ref = str(claim.get("evidence_ref") or "").strip().lower()
                        try:
                            option_index = int(raw_ref[1:]) - 1
                        except (TypeError, ValueError):
                            option_index = -1
                        if raw_ref.startswith(prefix) and 0 <= option_index < len(available):
                            resolved = available[option_index]
                    elif isinstance(claim, Mapping):
                        claim_key_value = self._evidence_key(claim)
                        resolved = next(
                            (
                                item
                                for item in available
                                if self._evidence_key(item) == claim_key_value
                            ),
                            None,
                        )
                    if resolved is not None and self._evidence_key(resolved) not in {
                        self._evidence_key(item) for item in claims
                    }:
                        claims.append(resolved)

                # 证据是宿主已验证的事实，不属于 Agent 的排序决策。模型漏填、
                # 改写或误用引用时补回当前候选的冻结选项，保留候选顺序与文案。
                selected_keys = {self._evidence_key(item) for item in claims}
                claims = [
                    option
                    for option in available
                    if self._evidence_key(option) in selected_keys
                ]
                required_count = 2 if claim_key == "positive_evidence" else len(available)
                for option in available:
                    if len(claims) >= required_count:
                        break
                    if self._evidence_key(option) not in {
                        self._evidence_key(item) for item in claims
                    }:
                        claims.append(option)
                claim_keys = {self._evidence_key(item) for item in claims}
                claims = [
                    option
                    for option in available
                    if self._evidence_key(option) in claim_keys
                ]
                recommendation[claim_key] = claims

            # 匹配标签是已验证证据的展示投影。Agent 只给出一项时，用当前
            # 候选的冻结正向证据补足，避免合法决赛在后续展示校验被误丢弃。
            match_tags = []
            for value in recommendation.get("match_tags") or ():
                tag = str(value or "").strip()
                if 1 <= len(tag) <= 20 and tag not in match_tags:
                    match_tags.append(tag)
            for claim in recommendation.get("positive_evidence") or ():
                for field_name in ("candidate_value", "user_value"):
                    tag = str(claim.get(field_name) or "").strip()
                    if 1 <= len(tag) <= 20 and tag not in match_tags:
                        match_tags.append(tag)
                    if len(match_tags) >= 2:
                        break
                if len(match_tags) < 2:
                    dimension = str(claim.get("dimension") or "").strip().casefold()
                    dimension_label = {
                        "type": "类型",
                        "theme": "题材",
                        "language": "语言",
                        "region": "地区",
                        "year": "年份",
                        "rating": "评分",
                        "popularity": "热度",
                        "freshness": "新鲜度",
                        "novelty": "新颖度",
                        "quality": "质量",
                    }.get(dimension, dimension)
                    candidate_value = str(
                        claim.get("candidate_value") or ""
                    ).strip()
                    tag = "·".join(
                        value for value in (dimension_label, candidate_value) if value
                    )
                    if 1 <= len(tag) <= 20 and tag not in match_tags:
                        match_tags.append(tag)
                if len(match_tags) >= 2:
                    break
            recommendation["match_tags"] = match_tags[:10]
            recommendations.append(recommendation)
        output["recommendations"] = recommendations
        return output, None

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

    def mark_context_read(self) -> bool:
        """原子标记终结角色已读取上下文，拒绝 repair 再次读取。"""
        if self.context_read:
            return False
        self.context_read = True
        return True

    @staticmethod
    def _candidate_ids(payload: Mapping[str, Any], role: str) -> list[str]:
        """提取当前角色提交载荷中的候选身份。"""
        key = "judgments" if role == PRELIMINARY_AGENT_ROLE else "recommendations"
        return [
            str(item.get("candidate_id") or "").strip()
            for item in payload.get(key) or []
            if isinstance(item, Mapping)
        ]

    def _canonicalize_candidate_ids(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """把 Agent 提交的受信短引用映射回冻结候选真实 ID。"""
        if self.trusted_context.agent_role not in {
            PRELIMINARY_AGENT_ROLE,
            FINAL_AGENT_ROLE,
        }:
            return dict(payload)
        key = "judgments" if self.trusted_context.agent_role == PRELIMINARY_AGENT_ROLE else "recommendations"
        values = []
        for raw in payload.get(key) or ():
            item = dict(raw) if isinstance(raw, Mapping) else raw
            if isinstance(item, Mapping):
                item = dict(item)
                submitted = str(item.get("candidate_id") or "").strip()
                canonical = self._candidate_aliases.get(submitted)
                if canonical is None:
                    # 某些模型会把宿主展示的短引用轻微规范化为大写或
                    # 纯数字；只在当前冻结顺序内解析，不能接受任意外部 ID。
                    normalized = submitted.lower()
                    match = re.fullmatch(
                        r"(?:candidate(?:[_ :.-])?)?c?0*([1-9][0-9]*)",
                        normalized,
                    )
                    if match:
                        index = int(match.group(1)) - 1
                        if 0 <= index < len(self._ordered_candidate_ids):
                            canonical = self._ordered_candidate_ids[index]
                item["candidate_id"] = canonical or submitted
            values.append(item)
        return {**dict(payload), key: values}

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
        payload = self._canonicalize_candidate_ids(payload)
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
            if self.trusted_context.agent_role == FINAL_AGENT_ROLE:
                constraints = self.trusted_context.submission_constraints or {}
                previous_ids = {
                    str(item or "").strip()
                    for item in constraints.get("previous_board_candidate_ids") or ()
                    if str(item or "").strip()
                }
                minimum_new_items = max(
                    0,
                    int(constraints.get("minimum_new_items") or 0),
                )
                if previous_ids and minimum_new_items:
                    new_count = sum(item not in previous_ids for item in candidate_ids)
                    if new_count < minimum_new_items:
                        self.last_issue = SubmissionIssue(
                            "previous_board_overlap_exceeded",
                            "recommendations.candidate_id",
                        )
                        return self.last_issue
                canonical_payload, evidence_issue = self._canonicalize_final_evidence(payload)
                if evidence_issue is not None:
                    self.last_issue = evidence_issue
                    return self.last_issue
                payload = canonical_payload or payload
                evidence_issue = self._validate_final_evidence(payload)
                if evidence_issue is not None:
                    self.last_issue = evidence_issue
                    return self.last_issue
        if self.trusted_context.agent_role == PROFILE_AGENT_ROLE:
            expected_count = int(
                (self.trusted_context.playback or {}).get("sample_count") or 0
            )
            profile_preferences = self.trusted_context.profile_preferences or {}
            archived_values = [
                *(profile_preferences.get("archived_tags") or []),
                *(profile_preferences.get("archived_negative_tags") or []),
            ]
            archived_tags = {
                str(item or "").strip()
                for item in archived_values
                if str(item or "").strip()
            }
            profile_payload = dict(payload.get("profile") or {})
            profile_payload["playback_count"] = expected_count
            profile_payload["negative_tags"] = [
                item
                for item in profile_payload.get("negative_tags") or []
                if str(item or "").strip() not in archived_tags
            ]
            payload = {**payload, "profile": profile_payload}
        self.payload = dict(payload)
        self.last_issue = None
        return None

    def result_json(self) -> str:
        """返回既有领域 parser 可直接消费的紧凑 JSON。"""
        if self.payload is None:
            raise RuntimeError("AgentRank submission result is unavailable")
        return json.dumps(
            to_jsonable(self.payload),
            ensure_ascii=False,
            separators=(",", ":"),
        )


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
