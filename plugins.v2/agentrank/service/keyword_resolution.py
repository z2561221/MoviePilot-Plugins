"""画像检索计划的固定词表与 TMDB 关键词安全解析。"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from ..adapter.tmdb_keyword import (
    TmdbKeywordAdapter,
    TmdbKeywordProviderError,
    TmdbKeywordRecord,
)
from ..model.retrieval import RetrievalFilters, RetrievalPlan


def normalize_term(value: Any) -> str:
    """用稳定 Unicode 规则规范化题材、语言和关键词别名。"""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    text = re.sub(r"[-_/]+", " ", text)
    return re.sub(r"\s+", " ", text)


def _aliases(entries: Mapping[Any, Iterable[str]]) -> Dict[str, Tuple[Any, str]]:
    """构造规范化别名到 ID 与规范名的只读前置映射。"""
    result: Dict[str, Tuple[Any, str]] = {}
    for identifier, names in entries.items():
        values = [str(name).strip() for name in names if str(name or "").strip()]
        if not values:
            continue
        canonical = normalize_term(values[0])
        for name in values:
            result[normalize_term(name)] = (identifier, canonical)
    return result


GENRE_ALIASES = _aliases(
    {
        12: ("冒险", "adventure"),
        14: ("奇幻", "fantasy"),
        16: ("动画", "动漫", "anime", "animation"),
        18: ("剧情", "drama"),
        27: ("恐怖", "horror"),
        28: ("动作", "action"),
        35: ("喜剧", "comedy"),
        36: ("历史", "history"),
        37: ("西部", "western"),
        53: ("惊悚", "惊险", "thriller"),
        80: ("犯罪", "crime"),
        99: ("纪录片", "纪录", "documentary"),
        878: ("科幻", "科幻小说", "science fiction", "sci fi", "sci-fi"),
        9648: ("悬疑", "推理", "mystery"),
        10402: ("音乐", "music"),
        10749: ("爱情", "浪漫", "romance"),
        10751: ("家庭", "family"),
        10752: ("战争", "war"),
        10759: ("动作冒险", "action adventure", "action & adventure"),
        10762: ("儿童", "kids"),
        10763: ("新闻", "news"),
        10764: ("真人秀", "reality"),
        10765: ("科幻奇幻", "science fiction fantasy", "sci-fi fantasy"),
        10766: ("肥皂剧", "soap"),
        10767: ("脱口秀", "talk"),
        10768: ("战争政治", "war politics", "war & politics"),
        10770: ("电视电影", "tv movie"),
    }
)

LANGUAGE_ALIASES = _aliases(
    {
        "zh": ("zh", "中文", "汉语", "国语", "普通话", "chinese", "mandarin"),
        "en": ("en", "英语", "英文", "english"),
        "ja": ("ja", "日语", "日文", "japanese"),
        "ko": ("ko", "韩语", "韩文", "korean"),
        "fr": ("fr", "法语", "french"),
        "de": ("de", "德语", "german"),
        "es": ("es", "西班牙语", "spanish"),
        "it": ("it", "意大利语", "italian"),
        "pt": ("pt", "葡萄牙语", "portuguese"),
        "ru": ("ru", "俄语", "russian"),
        "th": ("th", "泰语", "thai"),
        "vi": ("vi", "越南语", "vietnamese"),
        "hi": ("hi", "印地语", "hindi"),
        "ar": ("ar", "阿拉伯语", "arabic"),
        "tr": ("tr", "土耳其语", "turkish"),
        "pl": ("pl", "波兰语", "polish"),
        "nl": ("nl", "荷兰语", "dutch"),
        "sv": ("sv", "瑞典语", "swedish"),
    }
)

DEFAULT_KEYWORD_QUERY_ALIASES = {
    normalize_term("时间旅行"): "time travel",
    normalize_term("时空旅行"): "time travel",
    normalize_term("太空歌剧"): "space opera",
    normalize_term("赛博朋克"): "cyberpunk",
    normalize_term("反乌托邦"): "dystopia",
    normalize_term("平行宇宙"): "parallel universe",
}


@dataclass(frozen=True)
class TermResolution:
    """记录一个自由标签的解析状态与安全降级原因。"""

    term: str
    kind: str
    status: str
    value: Any = None
    match_type: str = ""
    canonical_name: str = ""
    reason: str = ""


@dataclass(frozen=True)
class RetrievalPlanResolution:
    """表示解析后的检索计划与每个标签的确定性观测结果。"""

    plan: RetrievalPlan
    outcomes: Tuple[TermResolution, ...] = ()

    def metrics(self) -> Dict[str, int]:
        """汇总解析成功与降级计数，供运行历史使用。"""
        metrics = {
            "resolved_genre_count": 0,
            "resolved_language_count": 0,
            "resolved_keyword_count": 0,
            "ranking_tag_fallback_count": 0,
            "ambiguous_keyword_count": 0,
            "keyword_not_found_count": 0,
            "keyword_unavailable_count": 0,
        }
        for outcome in self.outcomes:
            if outcome.status == "resolved":
                metrics[f"resolved_{outcome.kind}_count"] += 1
            elif outcome.kind == "keyword":
                metrics[
                    {
                        "ambiguous": "ambiguous_keyword_count",
                        "not_found": "keyword_not_found_count",
                        "unavailable": "keyword_unavailable_count",
                    }.get(outcome.status, "ranking_tag_fallback_count")
                ] += 1
                metrics["ranking_tag_fallback_count"] += 1
        return metrics


class ControlledRetrievalPlanResolver:
    """将画像自由标签解析为固定白名单或唯一可信 TMDB 关键词 ID。"""

    def __init__(
        self,
        keyword_searcher: Any = None,
        keyword_aliases: Optional[Mapping[str, Any]] = None,
        max_keyword_lookups: int = 8,
    ):
        """绑定可注入关键词搜索器与可信别名，限制外部查询次数。"""
        self._keyword_searcher = keyword_searcher
        self._keyword_aliases = dict(DEFAULT_KEYWORD_QUERY_ALIASES)
        for alias, target in (keyword_aliases or {}).items():
            self._keyword_aliases[normalize_term(alias)] = target
        self._max_keyword_lookups = max(0, int(max_keyword_lookups))

    @staticmethod
    def _append_unique(values: List[Any], value: Any, limit: int) -> bool:
        """向有界列表追加唯一值并返回是否成功。"""
        if value in values:
            return True
        if len(values) >= limit:
            return False
        values.append(value)
        return True

    @staticmethod
    def _direct_alias(value: Any, term: str) -> Optional[TmdbKeywordRecord]:
        """把可信别名配置转换为无需再次搜索的关键词记录。"""
        if isinstance(value, TmdbKeywordRecord):
            return value
        if isinstance(value, Mapping):
            return TmdbKeywordRecord.from_payload(value)
        if isinstance(value, bool):
            return None
        try:
            keyword_id = int(value)
        except (TypeError, ValueError):
            return None
        if keyword_id <= 0:
            return None
        return TmdbKeywordRecord(keyword_id=keyword_id, name=term)

    def _resolve_keyword(
        self, term: str, lookup_count: int
    ) -> TermResolution:
        """按精确名称或可信别名执行唯一关键词解析。"""
        normalized = normalize_term(term)
        alias = self._keyword_aliases.get(normalized)
        if alias is not None and not isinstance(alias, str):
            record = self._direct_alias(alias, term)
            if record is not None:
                return TermResolution(
                    term=term,
                    kind="keyword",
                    status="resolved",
                    value=record.keyword_id,
                    match_type="alias",
                    canonical_name=record.name,
                )
        if self._keyword_searcher is None:
            return TermResolution(
                term=term,
                kind="keyword",
                status="unavailable",
                reason="keyword provider is not configured",
            )
        if lookup_count >= self._max_keyword_lookups:
            return TermResolution(
                term=term,
                kind="keyword",
                status="unavailable",
                reason="keyword lookup limit reached",
            )
        query = alias if isinstance(alias, str) else term
        try:
            records = TmdbKeywordAdapter(self._keyword_searcher).search(str(query))
        except (TmdbKeywordProviderError, ValueError) as error:
            return TermResolution(
                term=term,
                kind="keyword",
                status="unavailable",
                reason=str(error),
            )
        query_name = normalize_term(query)
        matches: List[TmdbKeywordRecord] = []
        seen_ids = set()
        for record in records:
            names = {normalize_term(record.name)} | {
                normalize_term(alias_name) for alias_name in record.aliases
            }
            if query_name in names and record.keyword_id not in seen_ids:
                seen_ids.add(record.keyword_id)
                matches.append(record)
        if len(matches) == 1:
            return TermResolution(
                term=term,
                kind="keyword",
                status="resolved",
                value=matches[0].keyword_id,
                match_type="alias" if isinstance(alias, str) else "exact",
                canonical_name=matches[0].name,
            )
        if len(matches) > 1:
            return TermResolution(
                term=term,
                kind="keyword",
                status="ambiguous",
                reason="more than one exact keyword ID matched",
            )
        return TermResolution(
            term=term,
            kind="keyword",
            status="not_found",
            reason="no exact keyword name matched",
        )

    def resolve(self, plan: RetrievalPlan) -> RetrievalPlanResolution:
        """解析固定别名与关键词，并将不确定语义留在 ranking_tags。"""
        if not isinstance(plan, RetrievalPlan):
            raise ValueError("retrieval plan is required")
        filters = plan.filters
        genre_ids = list(filters.genre_ids)
        languages = list(filters.original_languages)
        keyword_ids = list(filters.keyword_ids)
        ranking_tags: List[str] = []
        outcomes: List[TermResolution] = []
        keyword_lookup_count = 0
        for term in plan.ranking_tags:
            normalized = normalize_term(term)
            genre = GENRE_ALIASES.get(normalized)
            if genre is not None:
                identifier, canonical = genre
                if self._append_unique(genre_ids, identifier, 20):
                    outcomes.append(
                        TermResolution(
                            term=term,
                            kind="genre",
                            status="resolved",
                            value=identifier,
                            match_type="exact" if normalized == canonical else "alias",
                            canonical_name=canonical,
                        )
                    )
                    continue
            language = LANGUAGE_ALIASES.get(normalized)
            if language is not None:
                identifier, canonical = language
                if self._append_unique(languages, identifier, 10):
                    outcomes.append(
                        TermResolution(
                            term=term,
                            kind="language",
                            status="resolved",
                            value=identifier,
                            match_type="exact" if normalized == canonical else "alias",
                            canonical_name=canonical,
                        )
                    )
                    continue
            keyword_alias = self._keyword_aliases.get(normalized)
            requires_lookup = (
                self._keyword_searcher is not None
                and (keyword_alias is None or isinstance(keyword_alias, str))
                and keyword_lookup_count < self._max_keyword_lookups
            )
            outcome = self._resolve_keyword(term, keyword_lookup_count)
            if requires_lookup:
                keyword_lookup_count += 1
            if outcome.status == "resolved":
                if self._append_unique(keyword_ids, outcome.value, 20):
                    outcomes.append(outcome)
                    continue
                outcome = TermResolution(
                    term=term,
                    kind="keyword",
                    status="unavailable",
                    reason="keyword ID limit reached",
                )
            ranking_tags.append(term)
            outcomes.append(outcome)
        resolved_filters = RetrievalFilters(
            media_types=filters.media_types,
            genre_ids=tuple(genre_ids),
            keyword_ids=tuple(keyword_ids),
            original_languages=tuple(languages),
            year_min=filters.year_min,
            year_max=filters.year_max,
            rating_min=filters.rating_min,
            vote_count_min=filters.vote_count_min,
            sort_by=filters.sort_by,
        )
        return RetrievalPlanResolution(
            plan=RetrievalPlan(
                filters=resolved_filters,
                ranking_tags=tuple(ranking_tags),
            ),
            outcomes=tuple(outcomes),
        )
