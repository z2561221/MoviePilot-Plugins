"""AgentRank 受控检索计划领域模型。"""

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple


MEDIA_TYPES = frozenset({"movie", "tv", "anime"})
SORT_OPTIONS = frozenset(
    {
        "popularity.desc",
        "vote_average.desc",
        "vote_count.desc",
        "release_date.desc",
    }
)
TMDB_GENRE_IDS = frozenset(
    {
        12,
        14,
        16,
        18,
        27,
        28,
        35,
        36,
        37,
        53,
        80,
        99,
        878,
        9648,
        10402,
        10749,
        10751,
        10752,
        10759,
        10762,
        10763,
        10764,
        10765,
        10766,
        10767,
        10768,
        10770,
    }
)
ISO_639_1_CODES = frozenset(
    """
    aa ab ae af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce
    ch co cr cs cu cv cy da de dv dz ee el en eo es et eu fa ff fi fj fo fr
    fy ga gd gl gn gu gv ha he hi ho hr ht hu hy hz ia id ie ig ii ik io is
    it iu ja jv ka kg ki kj kk kl km kn ko kr ks ku kv kw ky la lb lg li ln
    lo lt lu lv mg mh mi mk ml mn mr ms mt my na nb nd ne ng nl nn no nr nv
    ny oc oj om or os pa pi pl ps pt qu rm rn ro ru rw sa sc sd se sg si sk
    sl sm sn so sq sr ss st su sv sw ta te tg th ti tk tl tn to tr ts tt tw
    ty ug uk ur uz ve vi vo wa wo xh yi yo za zh zu
    """.split()
)


@dataclass(frozen=True)
class RetrievalFilters:
    """表示经过校验、可映射到发现查询的结构化过滤条件。"""

    media_types: Tuple[str, ...] = ()
    genre_ids: Tuple[int, ...] = ()
    keyword_ids: Tuple[int, ...] = ()
    original_languages: Tuple[str, ...] = ()
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    rating_min: Optional[float] = None
    vote_count_min: Optional[int] = None
    sort_by: str = "popularity.desc"

    def to_dict(self) -> Dict[str, Any]:
        """返回供持久化和受信上下文使用的规范字典。"""
        return {
            "media_types": list(self.media_types),
            "genre_ids": list(self.genre_ids),
            "keyword_ids": list(self.keyword_ids),
            "original_languages": list(self.original_languages),
            "year_min": self.year_min,
            "year_max": self.year_max,
            "rating_min": self.rating_min,
            "vote_count_min": self.vote_count_min,
            "sort_by": self.sort_by,
        }


@dataclass(frozen=True)
class RetrievalPlan:
    """表示画像 Agent 生成并通过安全门的完整检索计划。"""

    filters: RetrievalFilters = field(default_factory=RetrievalFilters)
    ranking_tags: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        """返回只包含结构化过滤条件和自由排序标签的字典。"""
        return {
            "filters": self.filters.to_dict(),
            "ranking_tags": list(self.ranking_tags),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RetrievalPlan":
        """从已通过安全门的持久化字典恢复检索计划。"""
        if not isinstance(value, Mapping):
            raise ValueError("retrieval plan must be a mapping")
        if set(value) != {"filters", "ranking_tags"}:
            raise ValueError("retrieval plan keys are invalid")
        filters = value.get("filters")
        ranking_tags = value.get("ranking_tags")
        if not isinstance(filters, Mapping) or not isinstance(
            ranking_tags, (list, tuple)
        ):
            raise ValueError("retrieval plan values are invalid")
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
        if set(filters) != expected:
            raise ValueError("retrieval filters keys are invalid")
        return cls(
            filters=RetrievalFilters(
                media_types=tuple(filters["media_types"] or ()),
                genre_ids=tuple(filters["genre_ids"] or ()),
                keyword_ids=tuple(filters["keyword_ids"] or ()),
                original_languages=tuple(filters["original_languages"] or ()),
                year_min=filters["year_min"],
                year_max=filters["year_max"],
                rating_min=filters["rating_min"],
                vote_count_min=filters["vote_count_min"],
                sort_by=str(filters["sort_by"]),
            ),
            ranking_tags=tuple(str(item) for item in ranking_tags),
        )
