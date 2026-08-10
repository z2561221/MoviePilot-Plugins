"""发现候选领域对象。"""

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional


_TYPED_TMDB_ID = re.compile(r"^tmdb:(movie|tv):([1-9]\d*)$")


def canonical_media_type(media_type: Any, mp_media_type: Any = "") -> Optional[str]:
    """把候选或 MoviePilot 类型收敛为 movie/tv 基础类型。"""
    for value in (mp_media_type, media_type):
        raw = str(getattr(value, "value", value) or "").strip().casefold()
        if raw in {"movie", "电影"} or "movie" in raw:
            return "movie"
        if raw in {"tv", "电视剧", "剧集", "电视"} or raw.startswith("tv"):
            return "tv"
    return None


def typed_tmdb_candidate_id(
    tmdb_id: Any, media_type: Any = "", mp_media_type: Any = ""
) -> str:
    """生成或校验 `tmdb:movie:<id>` / `tmdb:tv:<id>` 身份。"""
    raw_id = str(tmdb_id or "").strip()
    matched = _TYPED_TMDB_ID.fullmatch(raw_id)
    if matched:
        return f"tmdb:{matched.group(1)}:{int(matched.group(2))}"
    if not raw_id.isdigit() or int(raw_id) <= 0:
        raise ValueError("candidate requires a positive TMDB id")
    normalized_type = canonical_media_type(media_type, mp_media_type)
    if normalized_type is None:
        raise ValueError("candidate requires a movie or tv TMDB type")
    return f"tmdb:{normalized_type}:{int(raw_id)}"


@dataclass
class Candidate:
    """表示进入某次推荐运行的规范化候选。"""

    candidate_id: str
    title: str
    media_type: str = "unknown"
    year: Optional[int] = None
    source_ids: Dict[str, str] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)
    original_title: str = ""
    overview: str = ""
    poster_path: str = ""
    backdrop_path: str = ""
    rating: Optional[float] = None
    popularity: Optional[float] = None
    release_date: str = ""
    genres: List[str] = field(default_factory=list)
    regions: List[str] = field(default_factory=list)
    actors: List[str] = field(default_factory=list)
    directors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Candidate":
        """从持久化字典恢复候选并校验稳定标识。"""
        if not isinstance(value, Mapping):
            raise ValueError("candidate must be a mapping")
        candidate_id = str(value.get("candidate_id") or "").strip()
        title = str(value.get("title") or "").strip()
        if not candidate_id or not title:
            raise ValueError("candidate_id and title are required")
        year = value.get("year")
        return cls(
            candidate_id=candidate_id,
            title=title,
            media_type=str(value.get("media_type") or "unknown"),
            year=int(year) if year not in (None, "") else None,
            source_ids=dict(value.get("source_ids") or {}),
            sources=[str(item) for item in value.get("sources") or []],
            original_title=str(value.get("original_title") or ""),
            overview=str(value.get("overview") or ""),
            poster_path=str(value.get("poster_path") or ""),
            backdrop_path=str(value.get("backdrop_path") or ""),
            rating=(
                float(value.get("rating"))
                if value.get("rating") not in (None, "")
                else None
            ),
            popularity=(
                float(value.get("popularity"))
                if value.get("popularity") not in (None, "")
                else None
            ),
            release_date=str(value.get("release_date") or ""),
            genres=[str(item) for item in value.get("genres") or []],
            regions=[str(item) for item in value.get("regions") or []],
            actors=[str(item) for item in value.get("actors") or []],
            directors=[str(item) for item in value.get("directors") or []],
            metadata=dict(value.get("metadata") or {}),
            schema_version=int(value.get("schema_version") or 1),
        )
