"""Agent 输出严格解析与确定性推荐校验。"""

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from ..model.board import RecommendationItem
from ..model.candidate import Candidate
from ..model.constants import RANKING_OUTPUT_LIMIT, RECOMMENDATION_LIMIT
from ..model.retrieval import (
    ISO_639_1_CODES,
    MEDIA_TYPES,
    SORT_OPTIONS,
    TMDB_GENRE_IDS,
    RetrievalFilters,
)
from .scoring import DeterministicSupportScorer, StableRecommendationRanker


FILLER_END_PATTERN = re.compile(r"(?:哈|呀|嘛|哒|喂)[。！？!?]?$")
# 播放事件数不能被文案伪装成“看完 X 次”或“X 次看完”；电视剧的完成
# 语义只能由集数与整剧状态表达。
AMBIGUOUS_WATCH_COUNT_PATTERN = re.compile(
    r"(?:"
    r"(?:看完|看了|看过|追完|追过|重看|观看|播放)(?:了)?\s*\d+\s*(?:次|遍)"
    r"|\d+\s*(?:次|遍)\s*(?:看完|看了|看过|追完|追过|重看|观看|播放)"
    r")"
)
EXPLICIT_PLAYBACK_TITLE_PATTERN = re.compile(
    r"(?:你|用户)?(?:最近|此前|曾经|又|多次|反复|完整)?"
    r"(?:看过|看完|追完|追过|重看(?:过)?|反复看(?:过)?|播放(?:过)?|多次播放)"
    r"(?:了)?\s*([^，。；！？!?]{2,48})"
)
PLAYBACK_EXAMPLE_PATTERN = re.compile(r"(?:例如|比如|譬如|如)([^，。；！？!?]{2,48})")
PERSON_HISTORY_PATTERN = re.compile(
    r"(?:你|用户)?(?:最近|一直|经常|常常|常|爱|喜欢|偏爱|关注|看过)"
    r"\s*([^，。；！？!?、]{2,20}?)"
    r"(?:参演|主演|出演|执导|导演的作品|的作品)"
)
USER_HISTORY_CUE_PATTERN = re.compile(
    r"(?:你|用户).{0,8}(?:看过|看完|追完|追过|重看|反复看|常看|爱看|喜欢|偏爱|播放)"
)
CANDIDATE_ROLE_CLAIM_PATTERN = re.compile(
    r"([^，。；！？!?]{1,32}?)(执导|导演|主演|参演|出演)"
)
PLAYBACK_CLAIM_SPLIT_PATTERN = re.compile(r"(?:、|/|以及|还有|和|与|及|并且|并)")
CLAIM_DIGIT_ALIASES = str.maketrans(
    {"0": "零", "1": "一", "2": "二", "3": "三", "4": "四", "5": "五"}
)
CLAIM_NOISE_TERMS = (
    "用户",
    "最近",
    "此前",
    "曾经",
    "多次",
    "反复",
    "完整",
    "常常",
    "一直",
    "这部",
    "本片",
    "该片",
    "作品",
    "影片",
    "电影",
    "剧集",
    "动画",
    "由",
    "著名",
    "知名",
    "实力派",
    "老牌",
    "新锐",
    "演员",
    "明星",
    "阵容",
    "群星",
    "众多",
    "多位",
    "全员",
)
CLAIM_CONNECTOR_TERMS = (
    "和",
    "与",
    "及",
    "、",
    "以及",
    "还有",
    "并且",
    "并",
    "/",
    "联合",
    "携手",
    "等",
)
PLAYBACK_GENERIC_MARKER_PATTERN = re.compile(
    r"等(?:很多|多部|不少|若干|几部|多种|各种|多类|一类|这类|大量)?"
)
PLAYBACK_DISPLAY_NOISE_TERMS = (
    "这部",
    "本片",
    "该片",
    "作品",
    "影片",
    "电影",
    "剧集",
    "电视剧",
    "动画",
    "动漫",
    "番剧",
    "纪录片",
    "综艺",
)
GENERIC_PLAYBACK_QUANTITY_TERMS = (
    "很多",
    "多部",
    "不少",
    "若干",
    "几部",
    "多种",
    "各种",
    "多类",
    "一类",
    "这类",
    "大量",
)
GENERIC_PLAYBACK_NOUN_TERMS = (
    "题材",
    "类型",
    "风格",
    "作品",
    "电影",
    "影片",
    "剧集",
    "电视剧",
    "动画",
    "动漫",
    "番剧",
    "纪录片",
    "综艺",
    "片",
    "剧",
)
GENERIC_PLAYBACK_CATEGORY_TERMS = (
    "科幻",
    "悬疑",
    "犯罪",
    "动作",
    "冒险",
    "喜剧",
    "爱情",
    "恐怖",
    "惊悚",
    "奇幻",
    "动画",
    "动漫",
    "国漫",
    "日漫",
    "美漫",
    "历史",
    "战争",
    "家庭",
    "剧情",
    "纪录",
    "音乐",
    "体育",
    "修仙",
    "武侠",
    "古装",
    "校园",
    "职场",
    "推理",
    "侦探",
    "末日",
    "赛博",
    "机甲",
    "穿越",
    "异世界",
    "华语",
    "日系",
    "欧美",
    "韩剧",
    "美剧",
    "英剧",
    "短剧",
    "长剧",
)
VAGUE_REASON_PHRASES = (
    "神作",
    "必看",
    "肯定喜欢",
    "一定喜欢",
    "绝对喜欢",
    "不能错过",
    "不容错过",
    "不可错过",
    "值得一看",
    "强烈推荐",
    "非常推荐",
    "一定要看",
    "不看可惜",
)
PROCESS_REASON_PHRASES = (
    "画像检索",
    "画像标签",
    "匹配画像",
    "符合画像",
    "检索策略",
    "检索结果",
    "候选池",
    "召回来源",
    "来源名称",
    "Agent判断",
    "模型判断",
    "算法推荐",
    "安全过滤",
)
GENERIC_REASON_PATTERN = re.compile(
    r"^(?:这部|本片|作品)?(?:包含|具备|属于|符合|匹配).{1,14}(?:元素|要素|题材|类型|画像)?[。！？]?$"
)
REGION_LABELS = {
    "CN": "中国",
    "HK": "中国香港",
    "TW": "中国台湾",
    "JP": "日本",
    "KR": "韩国",
    "US": "美国",
    "GB": "英国",
    "FR": "法国",
    "DE": "德国",
    "IN": "印度",
    "TH": "泰国",
}
RECOMMENDATION_COPY_LIMIT = 30
INCOMPLETE_COPY_ENDINGS = ("，", "、", "；", "：")
COPY_PAIR_MARKS = (
    ("《", "》"),
    ("〈", "〉"),
    ("“", "”"),
    ("（", "）"),
    ("【", "】"),
    ("「", "」"),
    ("『", "』"),
    ("(", ")"),
    ("[", "]"),
)
COPY_TERMINAL_MARKS = ("。", "！", "？", ".", "!", "?")
INCOMPLETE_COPY_SUFFIXES = (
    "并且",
    "以及",
    "因为",
    "所以",
    "如果",
    "虽然",
    "但是",
    "并",
    "而",
    "且",
    "与",
    "和",
    "及",
    "或",
    "在",
    "从",
    "向",
    "对",
    "把",
    "将",
    "被",
    "为",
    "以",
    "由",
    "因",
    "但",
    "却",
    "让",
    "使",
    "给",
    "跟",
    "同",
    "像",
    "如",
    "若",
)
INCOMPLETE_LATIN_END_PATTERN = re.compile(
    r"(?i)(?:^|\s)(?:and|or|but|with|of|in|on|at|to|for|from|by|the|a|an)$"
)
COPY_REWRITE_REASON_CODES = frozenset(
    {
        "invalid_summary",
        "summary_too_long",
        "invalid_reason",
        "reason_too_long",
        "process_or_generic_reason",
        "missing_counter_evidence",
    }
)


def compact_profile_text(value: str, maximum: int) -> str:
    """仅对画像长摘要按自然标点收束，不用于推荐或简介文案。"""
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= maximum:
        return text
    window = text[:maximum]
    boundary = max(window.rfind(mark) for mark in "。！？；，、")
    if boundary >= max(1, maximum // 2):
        return window[: boundary + 1].strip().rstrip("，、；：")
    return window.strip()


def is_process_or_generic_reason(value: str) -> bool:
    """拒绝以画像、检索过程或单个宽泛分类充当推荐理由。"""
    text = "".join(str(value or "").split())
    return any(phrase in text for phrase in PROCESS_REASON_PHRASES) or bool(
        GENERIC_REASON_PATTERN.fullmatch(text)
    )


def has_unbalanced_copy_pairs(value: str) -> bool:
    """判断推荐文案是否包含未闭合的常用成对标点。"""
    text = str(value or "")
    for left, right in COPY_PAIR_MARKS:
        depth = 0
        for character in text:
            if character == left:
                depth += 1
            elif character == right:
                depth -= 1
                if depth < 0:
                    return True
        if depth:
            return True
    return False


def is_complete_recommendation_copy(value: str) -> bool:
    """判断三十字内文案是否避开可确定识别的机械截断与残句。"""
    text = " ".join(str(value or "").split()).strip()
    if not text or len(text) > RECOMMENDATION_COPY_LIMIT:
        return False
    if text.endswith(INCOMPLETE_COPY_ENDINGS) or has_unbalanced_copy_pairs(text):
        return False
    if text.endswith(("…", "...", "—", "-", "/", "\\")):
        return False
    core = text.rstrip("。！？.!? ”》）】\"'").strip()
    if not core:
        return False
    if any(core.endswith(suffix) for suffix in INCOMPLETE_COPY_SUFFIXES):
        return False
    if INCOMPLETE_LATIN_END_PATTERN.search(core):
        return False
    terminal_text = text.rstrip("”》〉）】」』\"'")
    if len(text) == RECOMMENDATION_COPY_LIMIT and not terminal_text.endswith(
        COPY_TERMINAL_MARKS
    ):
        return False
    return True


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
class ParsedProfilePlan:
    """表示通过结构和资源安全门的稳定画像。"""

    profile: ParsedProfile


# 兼容调用方对“画像输出”名称的语义引用，同时保持新 schema 名称明确。
ParsedProfileOutput = ParsedProfilePlan


@dataclass(frozen=True)
class ParsedEvidenceClaim:
    """表示排序 Agent 对用户证据与候选事实关系的结构化声明。"""

    dimension: str
    user_value: str
    candidate_value: str


@dataclass(frozen=True)
class ParsedRecommendation:
    """表示尚未经过候选池校验的 Agent 推荐。"""

    candidate_id: str
    summary: str
    reason: str
    match_tags: List[str]
    confidence: Optional[int]
    fit_score: Optional[int]
    positive_evidence: List[ParsedEvidenceClaim] = field(default_factory=list)
    counter_evidence: List[ParsedEvidenceClaim] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedRankingOutput:
    """表示排序 Agent 结构受限的推荐 JSON 对象。"""

    recommendations: List[ParsedRecommendation]


@dataclass(frozen=True)
class DroppedRecommendation:
    """记录被确定性安全门丢弃的推荐及原因。"""

    candidate_id: str
    reason: str
    index: int


@dataclass
class RecommendationValidationResult:
    """表示带 Agent 原始顺序的通过项与丢弃证据。"""

    accepted: List[RecommendationItem] = field(default_factory=list)
    dropped: List[DroppedRecommendation] = field(default_factory=list)
    support_warnings: List[str] = field(default_factory=list)


class _StrictOutputParser:
    """提供两个 Agent 输出 parser 共用的资源与字段边界。"""

    def __init__(
        self,
        max_bytes: int = 262_144,
        max_recommendations: int = RECOMMENDATION_LIMIT,
        max_tags: int = 20,
        max_string_chars: int = 200,
    ):
        """设置输出资源边界。"""
        self._max_bytes = max(1, int(max_bytes))
        self._max_recommendations = max(
            1, min(int(max_recommendations), RANKING_OUTPUT_LIMIT)
        )
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

    def _object(self, output: str) -> Dict[str, Any]:
        """解析一个有界 JSON 对象，拒绝 Markdown、前缀和多值。"""
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
            raise AgentOutputError(
                f"Agent output must be one JSON object: {error.msg}"
            ) from error
        if not isinstance(value, dict):
            raise AgentOutputError("Agent output root must be an object")
        return value

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


class ProfileOutputParser(_StrictOutputParser):
    """只接受画像 Agent 的稳定 profile 根对象。"""

    def __init__(
        self,
        max_bytes: int = 262_144,
        max_recommendations: int = RECOMMENDATION_LIMIT,
        max_tags: int = 20,
        max_string_chars: int = 200,
        allowed_keyword_ids: Optional[Iterable[int]] = None,
        allowed_genre_ids: Optional[Iterable[int]] = None,
        known_keyword_ids: Optional[Iterable[int]] = None,
    ):
        """设置画像与检索计划的资源边界及可信 ID 集合。"""
        super().__init__(max_bytes, max_recommendations, max_tags, max_string_chars)
        keyword_ids = (
            allowed_keyword_ids
            if allowed_keyword_ids is not None
            else known_keyword_ids
        )
        self._allowed_keyword_ids = frozenset(
            self._positive_ids(keyword_ids or (), "allowed_keyword_ids")
        )
        self._allowed_genre_ids = frozenset(
            self._positive_ids(
                allowed_genre_ids if allowed_genre_ids is not None else TMDB_GENRE_IDS,
                "allowed_genre_ids",
            )
        )

    def with_allowed_keyword_ids(
        self, allowed_keyword_ids: Optional[Iterable[int]] = None
    ) -> "ProfileOutputParser":
        """返回继承当前边界并追加可信关键词 ID 的独立解析器。"""
        return ProfileOutputParser(
            max_bytes=self._max_bytes,
            max_recommendations=self._max_recommendations,
            max_tags=self._max_tags,
            max_string_chars=self._max_string_chars,
            allowed_keyword_ids={
                *self._allowed_keyword_ids,
                *self._positive_ids(
                    allowed_keyword_ids or (), "allowed_keyword_ids"
                ),
            },
            allowed_genre_ids=self._allowed_genre_ids,
        )

    @staticmethod
    def _positive_ids(value: Iterable[int], label: str) -> List[int]:
        """校验 parser 自身使用的可信正整数 ID 集合。"""
        result: List[int] = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
                raise ValueError(f"{label} must contain positive integers")
            if item not in result:
                result.append(item)
        return result

    def _id_list(
        self, value: Any, label: str, allowed: Set[int], maximum: int = 20
    ) -> List[int]:
        """读取只允许来自可信集合的唯一整数 ID 列表。"""
        if not isinstance(value, list):
            raise AgentOutputError(f"{label} must be a list")
        if len(value) > maximum:
            raise AgentOutputError(f"{label} exceeds {maximum} ids")
        result: List[int] = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
                raise AgentOutputError(f"{label} must contain positive integer ids")
            if item not in allowed:
                raise AgentOutputError(f"{label} contains unknown id {item}")
            if item in result:
                raise AgentOutputError(f"{label} contains duplicate id {item}")
            result.append(item)
        return result

    def _enum_list(
        self, value: Any, label: str, allowed: Set[str], maximum: int
    ) -> List[str]:
        """读取只允许固定枚举且保持顺序的字符串列表。"""
        if not isinstance(value, list):
            raise AgentOutputError(f"{label} must be a list")
        if len(value) > maximum:
            raise AgentOutputError(f"{label} exceeds {maximum} items")
        result: List[str] = []
        for item in value:
            if not isinstance(item, str) or item not in allowed:
                raise AgentOutputError(f"{label} contains unknown enum {item!r}")
            if item in result:
                raise AgentOutputError(f"{label} contains duplicate enum {item!r}")
            result.append(item)
        return result

    @staticmethod
    def _optional_integer(
        value: Any, label: str, minimum: int, maximum: int
    ) -> Optional[int]:
        """读取允许为空且处于边界内的整数。"""
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise AgentOutputError(f"{label} must be an integer or null")
        if not minimum <= value <= maximum:
            raise AgentOutputError(f"{label} must be between {minimum} and {maximum}")
        return value

    @staticmethod
    def _optional_number(
        value: Any, label: str, minimum: float, maximum: float
    ) -> Optional[float]:
        """读取允许为空且处于边界内的有限数值。"""
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AgentOutputError(f"{label} must be a number or null")
        numeric = float(value)
        if not math.isfinite(numeric) or not minimum <= numeric <= maximum:
            raise AgentOutputError(f"{label} must be between {minimum} and {maximum}")
        return numeric

    def _ranking_tags(self, value: Any) -> List[str]:
        """读取仅供排序语义使用的自由标签。"""
        if not isinstance(value, list):
            raise AgentOutputError("ranking_tags must be a list")
        if len(value) > self._max_tags:
            raise AgentOutputError(f"ranking_tags exceeds {self._max_tags} tags")
        result: List[str] = []
        for index, item in enumerate(value):
            if not isinstance(item, str):
                raise AgentOutputError(f"ranking_tags[{index}] must be a string")
            text = item.strip()
            if not 1 <= len(text) <= 40:
                raise AgentOutputError(
                    f"ranking_tags[{index}] must contain 1 to 40 characters"
                )
            if any(ord(char) < 32 for char in text):
                raise AgentOutputError(
                    f"ranking_tags[{index}] contains control characters"
                )
            if text in result:
                raise AgentOutputError(f"ranking_tags contains duplicate tag {text!r}")
            result.append(text)
        return result

    def _filters(self, value: Any) -> RetrievalFilters:
        """解析结构化过滤条件并拒绝自由语义与未知字段。"""
        if not isinstance(value, dict):
            raise AgentOutputError("filters must be an object")
        expected = {
            "media_types",
            "genre_ids",
            "keyword_ids",
            "original_languages",
            "year_min",
            "year_max",
            "rating_min",
            "vote_count_min",
            "sort_by",
        }
        self._exact_keys(value, expected, "filters")
        media_types = self._enum_list(
            value["media_types"], "filters.media_types", set(MEDIA_TYPES), 3
        )
        genre_ids = self._id_list(
            value["genre_ids"], "filters.genre_ids", set(self._allowed_genre_ids)
        )
        keyword_ids = self._id_list(
            value["keyword_ids"],
            "filters.keyword_ids",
            set(self._allowed_keyword_ids),
        )
        languages = self._enum_list(
            value["original_languages"],
            "filters.original_languages",
            set(ISO_639_1_CODES),
            10,
        )
        year_min = self._optional_integer(
            value["year_min"], "filters.year_min", 1870, 2100
        )
        year_max = self._optional_integer(
            value["year_max"], "filters.year_max", 1870, 2100
        )
        if year_min is not None and year_max is not None and year_min > year_max:
            raise AgentOutputError("filters.year_min must not exceed year_max")
        rating_min = self._optional_number(
            value["rating_min"], "filters.rating_min", 0.0, 10.0
        )
        vote_count_min = self._optional_integer(
            value["vote_count_min"], "filters.vote_count_min", 0, 2_000_000_000
        )
        sort_by = value["sort_by"]
        if not isinstance(sort_by, str) or sort_by not in SORT_OPTIONS:
            raise AgentOutputError(f"filters.sort_by contains unknown enum {sort_by!r}")
        return RetrievalFilters(
            media_types=tuple(media_types),
            genre_ids=tuple(genre_ids),
            keyword_ids=tuple(keyword_ids),
            original_languages=tuple(languages),
            year_min=year_min,
            year_max=year_max,
            rating_min=rating_min,
            vote_count_min=vote_count_min,
            sort_by=sort_by,
        )

    def _profile(self, value: Any) -> ParsedProfile:
        """解析画像主体字段并保持既有播放计数校验。"""
        if not isinstance(value, dict):
            raise AgentOutputError("profile must be an object")
        self._exact_keys(
            value,
            {"summary", "tags", "negative_tags", "playback_count"},
            "profile",
        )
        playback_count = value["playback_count"]
        if isinstance(playback_count, bool) or not isinstance(playback_count, int):
            raise AgentOutputError("profile.playback_count must be an integer")
        if playback_count < 0:
            raise AgentOutputError("profile.playback_count must be non-negative")
        return ParsedProfile(
            summary=compact_profile_text(
                self._string(value["summary"], "profile.summary", 2000), 200
            ),
            tags=self._tags(value["tags"], "profile.tags"),
            negative_tags=self._tags(value["negative_tags"], "profile.negative_tags"),
            playback_count=playback_count,
        )

    def parse(self, output: str) -> ParsedProfilePlan:
        """解析稳定画像并拒绝检索策略或额外根字段。"""
        value = self._object(output)
        self._exact_keys(value, {"profile"}, "root")
        return ParsedProfilePlan(
            profile=self._profile(value["profile"]),
        )


class RankingOutputParser(_StrictOutputParser):
    """只接受排序 Agent 的独立 recommendations 根对象。"""

    _LEGACY_RECOMMENDATION_KEYS = {
        "candidate_id",
        "reason",
        "summary",
        "match_tags",
        "confidence",
    }
    _RECOMMENDATION_KEYS = {
        "candidate_id",
        "fit_score",
        "reason",
        "summary",
        "match_tags",
        "positive_evidence",
        "counter_evidence",
    }
    _EVIDENCE_KEYS = {"dimension", "user_value", "candidate_value"}
    _EVIDENCE_DIMENSIONS = {
        "type",
        "theme",
        "actor",
        "director",
        "region",
        "year",
        "rating",
        "heat",
        "freshness",
        "similarity",
    }

    def _evidence_claims(
        self,
        value: Any,
        label: str,
        maximum: int = 8,
    ) -> List[ParsedEvidenceClaim]:
        """读取有界证据声明列表并拒绝未知维度或额外字段。"""
        if not isinstance(value, list):
            raise AgentOutputError(f"{label} must be a list")
        if len(value) > maximum:
            raise AgentOutputError(f"{label} exceeds {maximum} items")
        result = []
        for index, item in enumerate(value):
            if not isinstance(item, Mapping):
                raise AgentOutputError(f"{label}[{index}] must be an object")
            self._exact_keys(item, self._EVIDENCE_KEYS, f"{label}[{index}]")
            dimension = self._string(
                item["dimension"], f"{label}[{index}].dimension", 20
            ).casefold()
            if dimension not in self._EVIDENCE_DIMENSIONS:
                raise AgentOutputError(
                    f"{label}[{index}].dimension is unsupported"
                )
            result.append(
                ParsedEvidenceClaim(
                    dimension=dimension,
                    user_value=self._string(
                        item["user_value"],
                        f"{label}[{index}].user_value",
                        80,
                    ),
                    candidate_value=self._string(
                        item["candidate_value"],
                        f"{label}[{index}].candidate_value",
                        80,
                    ),
                )
            )
        return result

    def _recommendation_values(self, output: str) -> List[Any]:
        """读取通过根结构和数量边界校验的推荐原始列表。"""
        value = self._object(output)
        self._exact_keys(value, {"recommendations"}, "root")
        recommendations = value["recommendations"]
        if not isinstance(recommendations, list):
            raise AgentOutputError("recommendations must be a list")
        if len(recommendations) > self._max_recommendations:
            raise AgentOutputError(
                f"recommendations exceeds {self._max_recommendations} items"
            )
        return recommendations

    def _recommendation(
        self,
        item: Any,
        index: int,
        *,
        ignore_extra_keys: bool = False,
    ) -> ParsedRecommendation:
        """解析一条推荐，可在补选阶段忽略已记录的无关额外字段。"""
        if not isinstance(item, dict):
            raise AgentOutputError(f"recommendations[{index}] must be an object")
        normalized = dict(item)
        if "reason" not in normalized and "summary" in normalized:
            normalized["reason"] = normalized["summary"]
        if "summary" not in normalized and "reason" in normalized:
            normalized["summary"] = ""
        actual_keys = set(normalized)
        schema_keys = (
            self._RECOMMENDATION_KEYS
            if self._RECOMMENDATION_KEYS <= actual_keys
            else self._LEGACY_RECOMMENDATION_KEYS
            if self._LEGACY_RECOMMENDATION_KEYS <= actual_keys
            else None
        )
        if schema_keys is None:
            raise AgentOutputError(
                f"recommendations[{index}] must use the evidence schema"
            )
        if ignore_extra_keys:
            normalized = {
                key: normalized[key] for key in schema_keys
            }
        else:
            self._exact_keys(
                normalized,
                schema_keys,
                f"recommendations[{index}]",
            )
        confidence = normalized.get("confidence")
        if schema_keys == self._LEGACY_RECOMMENDATION_KEYS and (
            isinstance(confidence, bool) or not isinstance(confidence, int)
        ):
            raise AgentOutputError(
                f"recommendations[{index}].confidence must be an integer"
            )
        fit_score = (
            confidence
            if schema_keys == self._LEGACY_RECOMMENDATION_KEYS
            else normalized.get("fit_score")
        )
        if schema_keys == self._RECOMMENDATION_KEYS and (
            isinstance(fit_score, bool)
            or not isinstance(fit_score, int)
            or not 0 <= fit_score <= 100
        ):
            raise AgentOutputError(
                f"recommendations[{index}].fit_score must be an integer between 0 and 100"
            )
        return ParsedRecommendation(
            candidate_id=self._string(
                normalized["candidate_id"],
                f"recommendations[{index}].candidate_id",
                128,
            ),
            summary=self._string(
                normalized["summary"], f"recommendations[{index}].summary", 100
            ),
            reason=self._string(
                normalized["reason"], f"recommendations[{index}].reason", 100
            ),
            match_tags=self._tags(
                normalized["match_tags"],
                f"recommendations[{index}].match_tags",
                10,
            ),
            confidence=confidence,
            fit_score=fit_score,
            positive_evidence=(
                self._evidence_claims(
                    normalized["positive_evidence"],
                    f"recommendations[{index}].positive_evidence",
                )
                if schema_keys == self._RECOMMENDATION_KEYS
                else []
            ),
            counter_evidence=(
                self._evidence_claims(
                    normalized["counter_evidence"],
                    f"recommendations[{index}].counter_evidence",
                )
                if schema_keys == self._RECOMMENDATION_KEYS
                else []
            ),
        )

    def parse(self, output: str) -> ParsedRankingOutput:
        """解析推荐列表并拒绝任何画像字段。"""
        recommendations = [
            self._recommendation(item, index)
            for index, item in enumerate(self._recommendation_values(output))
        ]
        return ParsedRankingOutput(recommendations=recommendations)

    def parse_recoverable(
        self, output: str
    ) -> Tuple[ParsedRankingOutput, List[str]]:
        """逐条恢复补选输出，保留合法条目并返回结构告警。"""
        recommendations: List[ParsedRecommendation] = []
        warnings: List[str] = []
        for index, item in enumerate(self._recommendation_values(output)):
            extra_keys = (
                sorted(
                    set(item)
                    - (
                        self._RECOMMENDATION_KEYS
                        if self._RECOMMENDATION_KEYS <= set(item)
                        else self._LEGACY_RECOMMENDATION_KEYS
                    )
                )
                if isinstance(item, dict)
                else []
            )
            try:
                recommendation = self._recommendation(
                    item,
                    index,
                    ignore_extra_keys=True,
                )
            except AgentOutputError as error:
                warnings.append(str(error))
                continue
            if extra_keys:
                warnings.append(
                    f"recommendations[{index}] ignored extra keys {extra_keys}"
                )
            recommendations.append(recommendation)
        return ParsedRankingOutput(recommendations=recommendations), warnings


def fallback_summary(candidate: Candidate) -> str:
    """按媒体类型返回确定、可读的中文作品简介。"""
    overview = " ".join(str(candidate.overview or "").split()).strip()
    if (
        overview
        and is_complete_recommendation_copy(overview)
    ):
        return overview
    genre = next(
        (
            "".join(str(item or "").split()).strip("，。；、|/")
            for item in candidate.genres or ()
            if "".join(str(item or "").split()).strip("，。；、|/")
        ),
        "",
    )
    if genre and len(genre) <= 8:
        return f"围绕{genre}题材展开的完整故事。"
    summaries = {
        "movie": "光影故事铺展人物命运的新篇章。",
        "tv": "连环剧情逐步揭开人物命运的新篇章。",
        "anime": "动画世界展开一段青春奇幻冒险。",
    }
    return summaries.get(candidate.media_type, "故事生动呈现人物命运的新篇章。")


def fallback_reason(tags: Sequence[str]) -> str:
    """根据已验证短标签生成三十字内且语义完整的保底理由。"""
    safe_tags = [str(item or "").strip() for item in tags or () if str(item or "").strip()]
    if safe_tags:
        return f"作品具备{safe_tags[-1]}要素，经安全过滤保底补位。"
    return "作品通过本轮安全过滤，作为榜单保底补位。"


class RecommendationValidator:
    """依据冻结候选、订阅和归档集合执行确定性安全校验。"""

    def __init__(self, support_scorer: Any = None) -> None:
        """注入确定性支持度评分器。"""
        self._support_scorer = support_scorer or DeterministicSupportScorer()
        self._ranker = StableRecommendationRanker()

    @staticmethod
    def _match_tags(tags: Sequence[str]) -> List[str]:
        """返回单项不超过五字、去重且保持顺序的标签。"""
        result: List[str] = []
        for item in tags or []:
            text = "".join(str(item or "").split()).strip("，。；、|/")[:5]
            text = REGION_LABELS.get(text.upper(), text)
            if text and text not in result:
                result.append(text)
        return result

    @staticmethod
    def _supported_tag(tag: str, evidence: Sequence[str]) -> bool:
        """判断短标签能否回溯到一项明确证据。"""
        normalized = ["".join(str(item or "").split()) for item in evidence]
        return any(tag in item or item in tag for item in normalized if item)

    @staticmethod
    def _mentioned_in_reason(label: str, reason: str) -> bool:
        """判断理由是否明确提到完整标签或其地区与主题组合。"""
        normalized_label = "".join(str(label or "").split())
        normalized_reason = "".join(str(reason or "").split())
        if not normalized_label or not normalized_reason:
            return False
        if normalized_label in normalized_reason:
            return True
        regions = tuple(REGION_LABELS.values()) + ("国产", "国漫")
        region = next((item for item in regions if item in normalized_label), "")
        theme = normalized_label.replace(region, "", 1) if region else ""
        return bool(region and len(theme) >= 2 and region in normalized_reason and theme in normalized_reason)

    def _preference_label_in_reason(self, value: str, reason: str) -> str:
        """从画像证据与理由共同提炼不超过五字的偏好标签。"""
        label = self._evidence_label(value)
        if label and self._mentioned_in_reason(label, reason):
            return label
        evidence = "".join(str(value or "").split())
        normalized_reason = "".join(str(reason or "").split())
        region_groups = (
            (("日本", "日式"), "日本"),
            (("中国香港", "香港", "港式"), "港式"),
            (("韩国", "韩式", "韩剧"), "韩国"),
            (("中国", "国产", "国漫"), "国产"),
        )
        has_region = any(
            alias in evidence
            for aliases, _ in region_groups
            for alias in aliases
        )
        themes = (
            "修仙玄幻",
            "真人秀",
            "纪录片",
            "科幻",
            "奇幻",
            "悬疑",
            "复仇",
            "古装",
            "动画",
            "动作",
            "喜剧",
            "剧情",
        )
        for aliases, region_label in region_groups:
            if not any(alias in evidence for alias in aliases):
                continue
            if not any(alias in normalized_reason for alias in aliases):
                continue
            for theme in themes:
                if theme in evidence and theme in normalized_reason:
                    combined = f"{region_label}{theme}"
                    if len(combined) <= 5:
                        return combined
        if has_region:
            return ""
        for theme in themes:
            if theme in evidence and theme in normalized_reason:
                return theme[:5]
        return ""

    @staticmethod
    def _evidence_label(value: str) -> str:
        """把结构化证据收束为不超过五字的可读标签。"""
        text = "".join(str(value or "").split()).strip("，。；、|/")
        text = REGION_LABELS.get(text.upper(), text)
        original_text = text
        for suffix in ("偏好", "题材", "类型", "作品"):
            if text.endswith(suffix) and len(text) - len(suffix) >= 2:
                text = text[: -len(suffix)]
        if len(text) > 5:
            for suffix in ("动画", "电影", "剧集"):
                if text.endswith(suffix) and len(text) - len(suffix) >= 2:
                    text = text[: -len(suffix)]
                    break
        if len(text) > 5 and text == original_text:
            return ""
        return text[:5]

    def _evidence_tags(
        self,
        tags: Sequence[str],
        reason: str,
        candidate: Candidate,
        preference_evidence: Sequence[str],
    ) -> List[str]:
        """固定收束为一枚用户证据标签和一枚作品事实标签。"""
        normalized = self._match_tags(tags)
        if not preference_evidence:
            return normalized[:2]
        preference_tag_evidence = [
            item for item in preference_evidence if self._evidence_label(item)
        ]
        candidate_evidence = [
            *candidate.genres,
            *candidate.regions,
            *candidate.actors,
            *candidate.directors,
            candidate.title,
            candidate.overview,
            str(candidate.year or ""),
        ]
        if not any(
            str(item or "").strip()
            for item in [
                *candidate.genres,
                *candidate.regions,
                *candidate.actors,
                *candidate.directors,
                candidate.overview,
            ]
        ):
            return normalized[:2]
        preference = next(
            (
                label
                for item in preference_tag_evidence
                if (label := self._preference_label_in_reason(item, reason))
            ),
            "",
        )
        if not preference:
            preference = next(
                (
                    tag
                    for tag in normalized
                    if self._supported_tag(tag, preference_tag_evidence)
                    and self._mentioned_in_reason(tag, reason)
                ),
                "",
            )
        fact = next(
            (
                tag
                for tag in normalized
                if tag != preference
                and not self._supported_tag(tag, preference_tag_evidence)
                and self._supported_tag(tag, candidate_evidence)
                and self._mentioned_in_reason(tag, reason)
            ),
            "",
        )
        if not fact:
            structured_facts = [
                *candidate.genres,
                *candidate.regions,
                *candidate.actors,
                *candidate.directors,
            ]
            fact = next(
                (
                    label
                    for item in structured_facts
                    if (label := self._evidence_label(item))
                    and label != preference
                    and self._mentioned_in_reason(label, reason)
                ),
                "",
            )
        if not preference:
            preference = ""
        return [tag for tag in (preference, fact) if tag]

    @staticmethod
    def _evidence_claim_key(claim: Any) -> Tuple[str, str, str]:
        """把证据声明规范为可与宿主冻结选项比较的三元组。"""
        source = claim if isinstance(claim, Mapping) else None
        return tuple(
            str(
                (
                    source.get(field_name)
                    if source is not None
                    else getattr(claim, field_name, "")
                )
                or ""
            ).strip()
            for field_name in ("dimension", "user_value", "candidate_value")
        )

    @classmethod
    def _verified_evidence_tags(
        cls,
        claims: Sequence[Any],
    ) -> List[str]:
        """从已验证正向证据投影一枚用户标签和一枚作品标签。"""
        type_labels = {"movie": "电影", "tv": "剧集", "anime": "动画"}
        dimension_labels = {
            "type": ("类型偏好", "类型匹配"),
            "theme": ("题材偏好", "题材匹配"),
            "actor": ("演员偏好", "演员契合"),
            "director": ("导演偏好", "导演契合"),
            "region": ("地区偏好", "地区匹配"),
            "year": ("年代偏好", "年代匹配"),
            "rating": ("评分偏好", "评分匹配"),
            "heat": ("热度偏好", "热度匹配"),
            "freshness": ("新片偏好", "新片匹配"),
            "similarity": ("相似偏好", "相似匹配"),
        }
        user_labels: List[str] = []
        candidate_labels: List[str] = []
        user_fallbacks: List[str] = []
        candidate_fallbacks: List[str] = []
        for claim in claims or ():
            key = cls._evidence_claim_key(claim)
            dimension = key[0].removesuffix("_weight").casefold()
            user_fallback, candidate_fallback = dimension_labels.get(
                dimension,
                ("偏好证据", "作品事实"),
            )
            if user_fallback not in user_fallbacks:
                user_fallbacks.append(user_fallback)
            if candidate_fallback not in candidate_fallbacks:
                candidate_fallbacks.append(candidate_fallback)
            for raw_value, target in (
                (key[1], user_labels),
                (key[2], candidate_labels),
            ):
                localized = type_labels.get(raw_value.casefold(), raw_value)
                label = cls._evidence_label(localized)
                if label and label not in target:
                    target.append(label)

        selected: List[str] = []
        for label in [*user_labels, *user_fallbacks]:
            if label not in selected:
                selected.append(label)
                break
        for label in [*candidate_labels, *candidate_fallbacks]:
            if label not in selected:
                selected.append(label)
            if len(selected) >= 2:
                break
        for label in [
            *user_labels,
            *candidate_labels,
            *user_fallbacks,
            *candidate_fallbacks,
        ]:
            if label not in selected:
                selected.append(label)
            if len(selected) >= 2:
                break
        return selected[:2]

    @staticmethod
    def _playback_field(value: Any, name: str) -> Any:
        """兼容播放样本字典与领域对象读取单个安全字段。"""
        if isinstance(value, Mapping):
            return value.get(name)
        return getattr(value, name, None)

    @staticmethod
    def _claim_text(value: Any) -> str:
        """移除片名与理由中的展示符号，生成确定性比较文本。"""
        return re.sub(
            r"[\s《》〈〉「」『』【】\[\]（）()，,。.!！?？；;：:、/\\·•_\-]+",
            "",
            str(value or ""),
        ).casefold()

    @classmethod
    def _claim_alias_text(cls, value: Any) -> str:
        """生成支持常见数字简称的比较文本。"""
        return cls._claim_text(value).translate(CLAIM_DIGIT_ALIASES)

    @staticmethod
    def _is_subsequence(needle: str, haystack: str) -> bool:
        """判断较短片名是否按顺序出现在完整片名中。"""
        if len(needle) < 3 or not haystack:
            return False
        cursor = 0
        for character in needle:
            cursor = haystack.find(character, cursor)
            if cursor < 0:
                return False
            cursor += 1
        return True

    @classmethod
    def _playback_claim_parts(cls, value: Any) -> List[str]:
        """按明确连接词拆分一段可能包含多个播放片名的声明。"""
        text = str(value or "").strip()
        if not text:
            return []
        return [
            part.strip()
            for part in PLAYBACK_CLAIM_SPLIT_PATTERN.split(text)
            if part.strip()
        ]

    @classmethod
    def _claim_person_text(cls, value: Any) -> str:
        """移除人物经历或主创短语中的叙述噪声。"""
        text = cls._claim_text(value)
        normalized_terms = [
            cls._claim_text(term)
            for term in sorted(CLAIM_NOISE_TERMS, key=len, reverse=True)
        ]
        changed = True
        while text and changed:
            changed = False
            for term in normalized_terms:
                if term and text.startswith(term):
                    text = text[len(term) :]
                    changed = True
                if term and text.endswith(term):
                    text = text[: -len(term)]
                    changed = True
        return text

    @classmethod
    def _playback_evidence(cls, samples: Iterable[Any]) -> tuple[Set[str], str]:
        """汇总真实播放片名及样本明确文本，供理由声明回溯。"""
        titles: Set[str] = set()
        searchable: List[str] = []
        for sample in samples or ():
            title = str(cls._playback_field(sample, "title") or "").strip()
            normalized_title = cls._claim_text(title)
            if normalized_title:
                titles.add(normalized_title)
                searchable.append(normalized_title)
            overview = cls._claim_text(cls._playback_field(sample, "overview"))
            if overview:
                searchable.append(overview)
            genres = cls._playback_field(sample, "genres") or []
            for genre in genres if isinstance(genres, (list, tuple, set)) else [genres]:
                normalized_genre = cls._claim_text(genre)
                if normalized_genre:
                    searchable.append(normalized_genre)
        return titles, "|".join(searchable)

    @classmethod
    def _generic_playback_claim_supported(
        cls, value: Any, searchable: str
    ) -> bool:
        """仅接受可由播放字段回溯的泛题材或泛作品类别声明。"""
        claim = cls._claim_alias_text(value)
        if not cls._generic_playback_claim_shape(claim):
            return False
        normalized_categories = [
            cls._claim_alias_text(term)
            for term in GENERIC_PLAYBACK_CATEGORY_TERMS
            if cls._claim_alias_text(term) in claim
        ]
        if not normalized_categories:
            return True
        evidence = cls._claim_alias_text(searchable)
        return bool(evidence) and all(term in evidence for term in normalized_categories)

    @classmethod
    def _generic_playback_claim_shape(cls, value: Any) -> bool:
        """判断文本是否只是泛类别表达，而不是残留了具体片名。"""
        claim = cls._claim_alias_text(value)
        if not claim:
            return True
        normalized_nouns = tuple(
            cls._claim_alias_text(term) for term in GENERIC_PLAYBACK_NOUN_TERMS
        )
        if claim in normalized_nouns:
            return True
        quantities = tuple(
            cls._claim_alias_text(term) for term in GENERIC_PLAYBACK_QUANTITY_TERMS
        )
        categories = [
            cls._claim_alias_text(term)
            for term in GENERIC_PLAYBACK_CATEGORY_TERMS
            if cls._claim_alias_text(term) in claim
        ]
        has_generic_noun = any(term in claim for term in normalized_nouns)
        has_quantity = any(term in claim for term in quantities)
        if not has_generic_noun and not has_quantity:
            return False
        remainder = claim
        removable = sorted(
            {
                *normalized_nouns,
                *quantities,
                *categories,
                cls._claim_alias_text("相关"),
                cls._claim_alias_text("这类"),
                cls._claim_alias_text("一类"),
                cls._claim_alias_text("等"),
                cls._claim_alias_text("的"),
            },
            key=len,
            reverse=True,
        )
        for term in removable:
            if term:
                remainder = remainder.replace(term, "")
        return not remainder

    @classmethod
    def _display_noise_only(cls, value: Any) -> bool:
        """判断片名后剩余文本是否仅是“这部作品”等展示性套话。"""
        residual = cls._claim_text(value)
        for term in sorted(
            (
                *PLAYBACK_DISPLAY_NOISE_TERMS,
                *GENERIC_PLAYBACK_CATEGORY_TERMS,
                *CLAIM_CONNECTOR_TERMS,
            ),
            key=len,
            reverse=True,
        ):
            normalized = cls._claim_text(term)
            if normalized:
                residual = residual.replace(normalized, "")
        return not residual

    @classmethod
    def _single_title_alias_match(cls, value: Any, titles: Set[str]) -> bool:
        """判断一段独立文本是否是播放快照中的片名或保守简称。"""
        claim = cls._claim_alias_text(value)
        if not claim:
            return False
        for title in titles:
            normalized_title = cls._claim_alias_text(title)
            if len(normalized_title) < 2:
                continue
            if (
                claim == normalized_title
                or claim in normalized_title
                or cls._is_subsequence(claim, normalized_title)
            ):
                return True
        return False

    @classmethod
    def _explicit_title_sequence_supported(
        cls, value: Any, titles: Set[str]
    ) -> bool:
        """逐项核对没有连接词但连续列出的多个播放片名。"""
        remaining = cls._claim_alias_text(value)
        if not remaining:
            return False
        aliases = sorted(
            {
                cls._claim_alias_text(title)
                for title in titles
                if len(cls._claim_alias_text(title)) >= 2
            },
            key=len,
            reverse=True,
        )
        while remaining:
            matches = [
                (remaining.find(alias), alias)
                for alias in aliases
                if alias and alias in remaining
            ]
            if not matches:
                return cls._single_title_alias_match(remaining, titles)
            start, alias = min(matches, key=lambda item: (item[0], -len(item[1])))
            if start > 0:
                return False
            remaining = remaining[len(alias) :]
        return True

    @classmethod
    def _title_claim_supported(
        cls, value: str, titles: Set[str], searchable: str = ""
    ) -> bool:
        """判断观看声明中的具体片名是否存在于真实播放快照。"""
        claim = cls._claim_alias_text(value)
        if not claim:
            return True
        for title in titles:
            normalized_title = cls._claim_alias_text(title)
            if len(normalized_title) < 2:
                continue
            if (
                claim == normalized_title
                or claim in normalized_title
                or cls._is_subsequence(claim, normalized_title)
            ):
                return True
            if normalized_title in claim:
                residual = claim.replace(normalized_title, "", 1)
                if cls._display_noise_only(residual):
                    return True
        return cls._generic_playback_claim_supported(value, searchable)

    @classmethod
    def _playback_claim_supported(
        cls, value: Any, titles: Set[str], searchable: str = ""
    ) -> bool:
        """判断一段单片名或多片名播放声明是否可回溯。"""
        parts = cls._playback_claim_parts(value)
        if len(parts) > 1:
            return all(
                cls._playback_claim_supported(part, titles, searchable)
                for part in parts
            )
        raw = str(value or "").strip()
        marker = PLAYBACK_GENERIC_MARKER_PATTERN.search(raw)
        if marker:
            explicit_titles = raw[: marker.start()]
            generic_tail = raw[marker.end() :]
            if cls._explicit_title_sequence_supported(explicit_titles, titles):
                return cls._generic_playback_claim_shape(
                    f"多部{generic_tail}"
                ) or cls._generic_playback_claim_shape(generic_tail)
            return False
        return cls._title_claim_supported(raw, titles, searchable)

    @classmethod
    def _role_claim_supported(
        cls, value: Any, known_people: Iterable[Any]
    ) -> bool:
        """判断主创短语中的人物是否全部存在于候选结构化证据。"""
        text = cls._claim_person_text(value)
        for marker in ("执导", "导演", "主演", "参演", "出演"):
            normalized_marker = cls._claim_text(marker)
            if normalized_marker in text:
                text = text.rsplit(normalized_marker, 1)[-1]
        for person in sorted(
            (cls._claim_alias_text(item) for item in known_people or () if item),
            key=len,
            reverse=True,
        ):
            if person:
                text = text.replace(person, "")
        for connector in CLAIM_CONNECTOR_TERMS:
            text = text.replace(cls._claim_text(connector), "")
        return not text

    @classmethod
    def _unsupported_candidate_claim(
        cls, reason: str, candidate: Candidate
    ) -> bool:
        """拒绝无法从冻结候选演员或导演字段回溯的主创断言。"""
        actors = list(getattr(candidate, "actors", None) or ())
        directors = list(getattr(candidate, "directors", None) or ())
        for matched in CANDIDATE_ROLE_CLAIM_PATTERN.finditer(reason):
            clause, role = matched.groups()
            known_people = directors if role in {"执导", "导演"} else actors
            if not cls._role_claim_supported(clause, known_people):
                return True
        return False

    @classmethod
    def _unsupported_playback_claim(
        cls, reason: str, playback_samples: Iterable[Any]
    ) -> bool:
        """拒绝无法从真实播放片名或样本字段回溯的用户经历。"""
        samples = list(playback_samples or ())
        if not samples:
            # 兼容直接调用验证器的旧测试与离线工具；运行主链始终传入真实快照。
            return False
        titles, searchable = cls._playback_evidence(samples)
        for matched in EXPLICIT_PLAYBACK_TITLE_PATTERN.finditer(reason):
            if not cls._playback_claim_supported(
                matched.group(1), titles, searchable
            ):
                return True
        if USER_HISTORY_CUE_PATTERN.search(reason):
            for matched in PLAYBACK_EXAMPLE_PATTERN.finditer(reason):
                examples = cls._playback_claim_parts(matched.group(1))
                for example in examples:
                    if not cls._title_claim_supported(example, titles, searchable):
                        return True
        for matched in PERSON_HISTORY_PATTERN.finditer(reason):
            person = cls._claim_person_text(matched.group(1))
            if person and person not in searchable:
                return True
        return False

    @classmethod
    def _fallback_tags(
        cls,
        candidate: Candidate,
        _preference_evidence: Sequence[str],
    ) -> List[str]:
        """只从候选结构化事实中提取保底条目的可回溯短标签。"""
        media_type_label = {
            "movie": "电影",
            "tv": "剧集",
            "anime": "动画",
        }.get(str(candidate.media_type or "").casefold(), "影视")
        facts = [
            *candidate.genres,
            *candidate.regions,
            *candidate.actors,
            *candidate.directors,
            media_type_label,
            candidate.title,
        ]
        return cls._match_tags(facts)[:2]

    def build_fallback_items(
        self,
        candidates: Sequence[Candidate],
        accepted: Sequence[RecommendationItem],
        blocked_candidate_ids: Iterable[str] = (),
        preference_evidence: Sequence[str] = (),
        limit: int = RECOMMENDATION_LIMIT,
        policy_snapshot: Any = None,
        confirmed_memory: Any = None,
        profile_preferences: Any = None,
        playback_snapshot: Any = None,
        scoring_errors: Optional[List[str]] = None,
    ) -> List[RecommendationItem]:
        """用同一策略评分并构建不重复、不编造经历的安全补位。"""
        target_limit = max(1, min(int(limit), RECOMMENDATION_LIMIT))
        remaining_slots = max(0, target_limit - len(accepted or ()))
        if remaining_slots <= 0:
            return []
        errors = scoring_errors if scoring_errors is not None else []
        if any(
            value is None
            for value in (
                policy_snapshot,
                confirmed_memory,
                profile_preferences,
                playback_snapshot,
            )
        ):
            errors.append("support_context_unavailable")
            return []
        accepted_ids = {item.candidate_id for item in accepted or ()}
        blocked_ids = {
            str(candidate_id or "").strip()
            for candidate_id in blocked_candidate_ids or ()
            if str(candidate_id or "").strip()
        }
        result: List[RecommendationItem] = []
        for candidate in candidates or ():
            if (
                candidate.candidate_id in accepted_ids
                or candidate.candidate_id in blocked_ids
            ):
                continue
            accepted_ids.add(candidate.candidate_id)
            tags = self._fallback_tags(candidate, preference_evidence)
            reason = fallback_reason(tags)
            try:
                scoring = self._support_scorer.score_candidate(
                    candidate,
                    policy_snapshot,
                    (),
                    (),
                    confirmed_memory,
                    profile_preferences,
                    playback_snapshot,
                )
            except Exception:
                errors.append(f"{candidate.candidate_id}:support_scoring_failed")
                continue
            if scoring.verified_counter_count > 0:
                continue
            result.append(
                RecommendationItem(
                    candidate_id=candidate.candidate_id,
                    rank=1,
                    summary=fallback_summary(candidate),
                    reason=reason,
                    confidence=scoring.score.percentage,
                    support=scoring.score,
                    selection_source="safe_fallback",
                    title=candidate.title,
                    original_title=candidate.original_title,
                    names=list(candidate.names),
                    media_type=candidate.media_type,
                    year=candidate.year,
                    media_source=candidate.media_source,
                    media_id=candidate.media_id,
                    source_ids=dict(candidate.source_ids),
                    sources=list(candidate.sources),
                    poster_path=candidate.poster_path,
                    backdrop_path=candidate.backdrop_path,
                    match_tags=tags,
                    in_library=bool(candidate.metadata.get("in_library")),
                    subscribed=bool(candidate.metadata.get("subscribed")),
                    watch_status=str(
                        candidate.metadata.get("watch_status") or "unwatched"
                    ),
                )
            )
        ranked = self._ranker.rank(result, candidates, agent_order={})
        return ranked[:remaining_slots]

    def validate(
        self,
        parsed: ParsedRankingOutput,
        candidates: Sequence[Candidate],
        archived_candidate_ids: Set[str],
        subscribed_candidate_ids: Set[str],
        preference_evidence: Sequence[str] = (),
        playback_samples: Iterable[Any] = (),
        disliked_candidate_ids: Set[str] = None,
        policy_snapshot: Any = None,
        confirmed_memory: Any = None,
        profile_preferences: Any = None,
        playback_snapshot: Any = None,
        agent_fit_scores: Optional[Mapping[str, int]] = None,
    ) -> RecommendationValidationResult:
        """按 Agent 原顺序校验并保留决赛最终评分，最终排序由编排器完成。"""
        candidate_map: Dict[str, Candidate] = {
            candidate.candidate_id: candidate for candidate in candidates
        }
        normalized_fit_scores: Dict[str, int] = {}
        for raw_candidate_id, raw_score in dict(agent_fit_scores or {}).items():
            if isinstance(raw_score, bool):
                continue
            try:
                score = int(raw_score)
            except (TypeError, ValueError):
                continue
            candidate_id = str(raw_candidate_id or "").strip()
            if candidate_id and 0 <= score <= 100:
                normalized_fit_scores[candidate_id] = score
        archived = set(archived_candidate_ids or set())
        # 已订阅但未观看的候选仍可推荐；订阅服务在动作执行时做幂等复核。
        subscribed = set(subscribed_candidate_ids or set())
        disliked = set(disliked_candidate_ids or set())
        seen: Set[str] = set()
        result = RecommendationValidationResult()
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
            if candidate_id in disliked:
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "disliked_candidate", index)
                )
                continue
            if candidate_id in archived:
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "archived_candidate", index)
                )
                continue
            deterministic_support = policy_snapshot is not None
            if deterministic_support and recommendation.confidence is not None:
                result.dropped.append(
                    DroppedRecommendation(
                        candidate_id, "legacy_evidence_schema", index
                    )
                )
                continue
            if not deterministic_support and (
                recommendation.confidence is None
                or not 0 <= recommendation.confidence <= 100
            ):
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "invalid_confidence", index)
                )
                continue
            summary = " ".join(str(recommendation.summary or "").split()).strip()
            reason = " ".join(str(recommendation.reason or "").split()).strip()
            if not summary:
                summary = fallback_summary(candidate)
            if len(summary) > RECOMMENDATION_COPY_LIMIT:
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "summary_too_long", index)
                )
                continue
            if len(reason) > RECOMMENDATION_COPY_LIMIT:
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "reason_too_long", index)
                )
                continue
            match_tags = (
                []
                if deterministic_support
                else self._evidence_tags(
                    recommendation.match_tags,
                    reason,
                    candidate,
                    preference_evidence,
                )
            )
            unsupported_playback_claim = self._unsupported_playback_claim(
                reason, playback_samples
            )
            unsupported_candidate_claim = self._unsupported_candidate_claim(
                reason, candidate
            )
            process_or_generic_reason = is_process_or_generic_reason(reason)
            if not is_complete_recommendation_copy(summary):
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "invalid_summary", index)
                )
                continue
            if (
                not reason
                or reason == summary
                or not is_complete_recommendation_copy(reason)
                or any(phrase in reason for phrase in VAGUE_REASON_PHRASES)
                or FILLER_END_PATTERN.search(reason)
                or AMBIGUOUS_WATCH_COUNT_PATTERN.search(reason)
                or unsupported_playback_claim
                or unsupported_candidate_claim
                or process_or_generic_reason
            ):
                result.dropped.append(
                    DroppedRecommendation(
                        candidate_id,
                        "ambiguous_playback_count"
                        if AMBIGUOUS_WATCH_COUNT_PATTERN.search(reason)
                        else "process_or_generic_reason"
                        if process_or_generic_reason
                        else "unsupported_playback_claim"
                        if unsupported_playback_claim
                        else "invalid_reason",
                        index,
                    )
                )
                continue
            if not deterministic_support and len(match_tags) < 2:
                result.dropped.append(
                    DroppedRecommendation(
                        candidate_id, "insufficient_match_evidence", index
                    )
                )
                continue
            support = None
            confidence = int(recommendation.confidence or 0)
            fit_score = recommendation.fit_score
            if fit_score is None:
                fit_score = normalized_fit_scores.get(candidate_id)
            if (
                isinstance(fit_score, bool)
                or not isinstance(fit_score, int)
                or not 0 <= fit_score <= 100
            ):
                result.dropped.append(
                    DroppedRecommendation(candidate_id, "invalid_fit_score", index)
                )
                continue
            if deterministic_support:
                scoring = self._support_scorer.score_candidate(
                    candidate,
                    policy_snapshot,
                    recommendation.positive_evidence,
                    recommendation.counter_evidence,
                    confirmed_memory,
                    profile_preferences,
                    playback_snapshot,
                )
                if scoring.unsupported_claims:
                    result.support_warnings.extend(
                        f"{candidate_id}:{warning}"
                        for warning in scoring.unsupported_claims
                    )
                if scoring.verified_positive_count < 2:
                    result.dropped.append(
                        DroppedRecommendation(
                            candidate_id,
                            "insufficient_verified_evidence",
                            index,
                        )
                    )
                    continue
                verified_options = self._support_scorer.verified_evidence_options(
                    candidate,
                    policy_snapshot,
                    confirmed_memory,
                    profile_preferences,
                    playback_snapshot,
                )
                allowed_positive = {
                    self._evidence_claim_key(claim)
                    for claim in verified_options.get("positive_evidence_options") or ()
                }
                verified_positive_claims = [
                    claim
                    for claim in recommendation.positive_evidence
                    if self._evidence_claim_key(claim) in allowed_positive
                ]
                match_tags = self._verified_evidence_tags(
                    verified_positive_claims,
                )
                if len(match_tags) < 2:
                    result.dropped.append(
                        DroppedRecommendation(
                            candidate_id, "insufficient_match_evidence", index
                        )
                    )
                    continue
                if (
                    scoring.verified_counter_count > 0
                    and scoring.verified_counter_claim_count < 1
                ):
                    result.dropped.append(
                        DroppedRecommendation(
                            candidate_id,
                            "missing_counter_evidence",
                            index,
                        )
                    )
                    continue
                support = scoring.score
                confidence = support.percentage
            result.accepted.append(
                RecommendationItem(
                    candidate_id=candidate_id,
                    rank=len(result.accepted) + 1,
                    summary=summary,
                    reason=reason,
                    confidence=confidence,
                    fit_score=fit_score,
                    support=support,
                    selection_source="agent",
                    title=candidate.title,
                    original_title=candidate.original_title,
                    names=list(candidate.names),
                    media_type=candidate.media_type,
                    year=candidate.year,
                    media_source=candidate.media_source,
                    media_id=candidate.media_id,
                    source_ids=dict(candidate.source_ids),
                    sources=list(candidate.sources),
                    poster_path=candidate.poster_path,
                    backdrop_path=candidate.backdrop_path,
                    match_tags=match_tags,
                    in_library=bool(candidate.metadata.get("in_library")),
                    subscribed=bool(candidate.metadata.get("subscribed")),
                    watch_status=str(
                        candidate.metadata.get("watch_status") or "unwatched"
                    ),
                )
            )
        return result
