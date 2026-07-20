"""Agent 输出严格解析与确定性推荐校验。"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Sequence, Set

from ..model.board import RecommendationItem
from ..model.candidate import Candidate


FILLER_END_PATTERN = re.compile(r"(?:哈|呀|嘛|哒|喂)[。！？!?]?$")
VAGUE_REASON_PHRASES = ("神作", "必看", "肯定喜欢", "不能错过")


class AgentOutputError(ValueError):
    """表示 Agent 输出不满足结构或资源边界。"""


@dataclass(frozen=True)
class ParsedProfile:
    """表示通过结构校验的 Agent 用户画像。"""

    summary: str
    tags: List[str]
    negative_tags: List[str]
    playback_count: int


@dataclass(frozen=True)
class ParsedRecommendation:
    """表示尚未经过候选池校验的 Agent 推荐。"""

    candidate_id: str
    summary: str
    reason: str
    match_tags: List[str]
    confidence: int


@dataclass(frozen=True)
class ParsedAgentOutput:
    """表示一个完整且结构受限的 Agent JSON 对象。"""

    profile: ParsedProfile
    recommendations: List[ParsedRecommendation]


@dataclass(frozen=True)
class DroppedRecommendation:
    """记录被确定性安全门丢弃的推荐及原因。"""

    candidate_id: str
    reason: str
    index: int


@dataclass
class RecommendationValidationResult:
    """表示保持 Agent 顺序的通过项与丢弃证据。"""

    profile: ParsedProfile
    accepted: List[RecommendationItem] = field(default_factory=list)
    dropped: List[DroppedRecommendation] = field(default_factory=list)


class AgentOutputParser:
    """仅接受一个有界 JSON 对象并执行嵌套结构校验。"""

    def __init__(
        self,
        max_bytes: int = 262_144,
        max_recommendations: int = 10,
        max_tags: int = 20,
        max_string_chars: int = 200,
    ):
        """设置输出资源边界。"""
        self._max_bytes = max(1, int(max_bytes))
        self._max_recommendations = max(1, min(int(max_recommendations), 10))
        self._max_tags = max(1, int(max_tags))
        self._max_string_chars = max(10, int(max_string_chars))

    @staticmethod
    def _exact_keys(value: Mapping[str, Any], expected: Set[str], label: str) -> None:
        """要求对象键集合精确匹配 schema。"""
        actual = set(value)
        if actual != expected:
            raise AgentOutputError(
                f"{label} keys must be exactly {sorted(expected)}; got {sorted(actual)}"
            )

    def _string(self, value: Any, label: str, maximum: int = None) -> str:
        """读取有界字符串并拒绝非字符串值。"""
        if not isinstance(value, str):
            raise AgentOutputError(f"{label} must be a string")
        limit = maximum or self._max_string_chars
        if len(value) > limit:
            raise AgentOutputError(f"{label} exceeds {limit} characters")
        return value

    def _tags(self, value: Any, label: str, maximum: int = None) -> List[str]:
        """读取有界字符串标签列表。"""
        if not isinstance(value, list):
            raise AgentOutputError(f"{label} must be a list")
        limit = maximum or self._max_tags
        if len(value) > limit:
            raise AgentOutputError(f"{label} exceeds {limit} tags")
        return [self._string(item, f"{label} item", 20) for item in value]

    def parse(self, output: str) -> ParsedAgentOutput:
        """解析严格单对象输出，拒绝 Markdown、前缀、尾注和多值。"""
        if not isinstance(output, str):
            raise AgentOutputError("Agent output must be text")
        byte_count = len(output.encode("utf-8"))
        if byte_count > self._max_bytes:
            raise AgentOutputError(
                f"Agent output exceeds {self._max_bytes} bytes ({byte_count} bytes)"
            )
        try:
            value = json.loads(output)
        except json.JSONDecodeError as error:
            raise AgentOutputError(f"Agent output must be one JSON object: {error.msg}") from error
        if not isinstance(value, dict):
            raise AgentOutputError("Agent output root must be an object")
        self._exact_keys(value, {"profile", "recommendations"}, "root")

        profile_value = value["profile"]
        if not isinstance(profile_value, dict):
            raise AgentOutputError("profile must be an object")
        self._exact_keys(
            profile_value,
            {"summary", "tags", "negative_tags", "playback_count"},
            "profile",
        )
        playback_count = profile_value["playback_count"]
        if isinstance(playback_count, bool) or not isinstance(playback_count, int):
            raise AgentOutputError("profile.playback_count must be an integer")
        if playback_count < 0:
            raise AgentOutputError("profile.playback_count must be non-negative")
        profile = ParsedProfile(
            summary=self._string(profile_value["summary"], "profile.summary"),
            tags=self._tags(profile_value["tags"], "profile.tags"),
            negative_tags=self._tags(
                profile_value["negative_tags"], "profile.negative_tags"
            ),
            playback_count=playback_count,
        )

        recommendations_value = value["recommendations"]
        if not isinstance(recommendations_value, list):
            raise AgentOutputError("recommendations must be a list")
        if len(recommendations_value) > self._max_recommendations:
            raise AgentOutputError(
                f"recommendations exceeds {self._max_recommendations} items"
            )
        recommendations: List[ParsedRecommendation] = []
        for index, item in enumerate(recommendations_value):
            if not isinstance(item, dict):
                raise AgentOutputError(f"recommendations[{index}] must be an object")
            if "reason" not in item and "summary" in item:
                item = dict(item)
                item["reason"] = item["summary"]
            self._exact_keys(
                item,
                {"candidate_id", "reason", "summary", "match_tags", "confidence"},
                f"recommendations[{index}]",
            )
            confidence = item["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, int):
                raise AgentOutputError(
                    f"recommendations[{index}].confidence must be an integer"
                )
            recommendations.append(
                ParsedRecommendation(
                    candidate_id=self._string(
                        item["candidate_id"],
                        f"recommendations[{index}].candidate_id",
                        128,
                    ),
                    summary=self._string(
                        item["summary"], f"recommendations[{index}].summary", 100
                    ),
                    reason=self._string(
                        item["reason"], f"recommendations[{index}].reason", 100
                    ),
                    match_tags=self._tags(
                        item["match_tags"],
                        f"recommendations[{index}].match_tags",
                        10,
                    ),
                    confidence=confidence,
                )
            )
        return ParsedAgentOutput(profile=profile, recommendations=recommendations)


def fallback_summary(candidate: Candidate) -> str:
    """按媒体类型返回确定、可读的中文作品简介。"""
    summaries = {
        "movie": "光影故事缓缓铺展人物命运新篇章",
        "tv": "连环剧情逐步揭开人物命运新篇章",
        "anime": "动画世界热烈展开青春奇幻冒险路",
    }
    return summaries.get(candidate.media_type, "精彩故事生动呈现人物命运新篇章")


class RecommendationValidator:
    """依据冻结候选、订阅和归档集合执行确定性安全校验。"""

    @staticmethod
    def _bounded_text(value: str, minimum: int, maximum: int) -> bool:
        """校验自然文案的非空长度边界。"""
        text = str(value or "").strip()
        return minimum <= len(text) <= maximum

    @staticmethod
    def _match_tags(tags: Sequence[str]) -> List[str]:
        """返回非空、去重且保持顺序的匹配证据标签。"""
        result: List[str] = []
        for item in tags or []:
            text = str(item or "").strip()
            if text and text not in result:
                result.append(text)
        return result

    def validate(
        self,
        parsed: ParsedAgentOutput,
        candidates: Sequence[Candidate],
        archived_candidate_ids: Set[str],
        subscribed_candidate_ids: Set[str],
    ) -> RecommendationValidationResult:
        """按 Agent 原顺序校验并丰富通过项，绝不按媒体属性重排。"""
        candidate_map: Dict[str, Candidate] = {
            candidate.candidate_id: candidate for candidate in candidates
        }
        archived = set(archived_candidate_ids or set())
        subscribed = set(subscribed_candidate_ids or set())
        seen: Set[str] = set()
        result = RecommendationValidationResult(profile=parsed.profile)
        for index, recommendation in enumerate(parsed.recommendations):
            candidate_id = recommendation.candidate_id
            candidate = candidate_map.get(candidate_id)
            if candidate is None:
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "unknown_candidate", index)
                )
                continue
            if candidate_id in seen:
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "duplicate_candidate", index)
                )
                continue
            seen.add(candidate_id)
            if candidate_id in archived:
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "archived_candidate", index)
                )
                continue
            if candidate_id in subscribed:
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "subscribed_candidate", index)
                )
                continue
            if not 0 <= recommendation.confidence <= 100:
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "invalid_confidence", index)
                )
                continue
            summary = recommendation.summary.strip()
            reason = recommendation.reason.strip()
            match_tags = self._match_tags(recommendation.match_tags)
            if not self._bounded_text(summary, 12, 40):
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "invalid_summary", index)
                )
                continue
            if (
                not self._bounded_text(reason, 20, 60)
                or reason == summary
                or any(phrase in reason for phrase in VAGUE_REASON_PHRASES)
                or FILLER_END_PATTERN.search(reason)
            ):
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "invalid_reason", index)
                )
                continue
            if len(match_tags) < 2 or not any(tag in reason for tag in match_tags):
                result.dropped.append(
                    DroppedRecommendation(
                        candidate_id, "insufficient_match_evidence", index
                    )
                )
                continue
            result.accepted.append(
                RecommendationItem(
                    candidate_id=candidate_id,
                    rank=len(result.accepted) + 1,
                    summary=summary,
                    reason=reason,
                    confidence=recommendation.confidence,
                    title=candidate.title,
                    media_type=candidate.media_type,
                    year=candidate.year,
                    source_ids=dict(candidate.source_ids),
                    sources=list(candidate.sources),
                    poster_path=candidate.poster_path,
                    backdrop_path=candidate.backdrop_path,
                    match_tags=match_tags,
                )
            )
        return result
