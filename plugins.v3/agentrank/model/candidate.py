"""发现候选领域对象。"""

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional


_TYPED_TMDB_ID = re.compile(r"^tmdb:(movie|tv):([1-9]\d*)$")
_MEDIA_SOURCE = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
_MEDIA_SOURCE_ALIASES = {
    "tmdb": "themoviedb",
    "themoviedb": "themoviedb",
    "douban": "douban",
    "bangumi": "bangumi",
    "bgm": "bangumi",
    "anilist": "anilist",
    "imdb": "imdb",
    "tvdb": "tvdb",
}
MAX_CANDIDATE_NAMES = 12
MAX_CANDIDATE_NAME_LENGTH = 120


def normalize_title_names(
    values: Any, *, excluded: Iterable[Any] = ()
) -> List[str]:
    """规范化聚合来源别名并限制数量，避免不可信载荷放大。"""
    excluded_names = {
        " ".join(str(value or "").split()).strip()
        for value in excluded
        if str(value or "").strip()
    }
    result: List[str] = []

    def visit(value: Any) -> None:
        if len(result) >= MAX_CANDIDATE_NAMES or value in (None, ""):
            return
        if isinstance(value, Mapping):
            visit(value.get("name") or value.get("title"))
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                visit(item)
                if len(result) >= MAX_CANDIDATE_NAMES:
                    break
            return
        if not isinstance(value, str):
            value = getattr(value, "name", None) or getattr(value, "title", None)
        text = " ".join(str(value or "").split()).strip()[:MAX_CANDIDATE_NAME_LENGTH]
        if text and text not in excluded_names and text not in result:
            result.append(text)

    visit(values)
    return result


def normalize_media_identity(media_source: Any, media_id: Any) -> tuple[str, str]:
    """规范化 V3 媒体身份；无效半对返回空身份。"""
    source = str(getattr(media_source, "value", media_source) or "").strip().casefold()
    source = _MEDIA_SOURCE_ALIASES.get(source, source)
    identity = str(media_id or "").strip()
    if not source or not identity or identity == "0" or not _MEDIA_SOURCE.fullmatch(source):
        return "", ""
    return source, identity


def infer_media_identity(value: Mapping[str, Any]) -> tuple[str, str]:
    """从显式身份、旧 candidate_id 或辅助来源 ID 中幂等推断主身份。"""
    source, media_id = normalize_media_identity(
        value.get("media_source"), value.get("media_id")
    )
    if source and media_id:
        return source, media_id
    candidate_id = str(value.get("candidate_id") or "").strip()
    matched = _TYPED_TMDB_ID.fullmatch(candidate_id)
    if matched:
        return "themoviedb", str(int(matched.group(2)))
    source_ids = value.get("source_ids")
    if not isinstance(source_ids, Mapping):
        return "", ""
    for raw_source in ("tmdb", "themoviedb", "douban", "bangumi", "anilist"):
        source, media_id = normalize_media_identity(raw_source, source_ids.get(raw_source))
        if source and media_id:
            return source, media_id
    for raw_source, raw_media_id in source_ids.items():
        source, media_id = normalize_media_identity(raw_source, raw_media_id)
        if source and media_id:
            return source, media_id
    return "", ""


def backfill_media_identity_payload(
    value: Mapping[str, Any],
) -> tuple[Dict[str, Any], bool, bool]:
    """复制旧载荷并补全可证明的主身份，返回变更与未解析状态。"""
    payload = dict(value)
    source, media_id = infer_media_identity(payload)
    if not source or not media_id:
        return payload, False, True
    changed = (
        payload.get("media_source") != source
        or str(payload.get("media_id") or "").strip() != media_id
    )
    payload["media_source"] = source
    payload["media_id"] = media_id
    return payload, changed, False


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
    media_source: str = ""
    media_id: str = ""
    source_ids: Dict[str, str] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)
    original_title: str = ""
    names: List[str] = field(default_factory=list)
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
    schema_version: int = 2

    def __post_init__(self) -> None:
        """规范主身份，并为旧构造调用补齐可证明的来源对。"""
        source, media_id = infer_media_identity(
            {
                "candidate_id": self.candidate_id,
                "media_source": self.media_source,
                "media_id": self.media_id,
                "source_ids": self.source_ids,
            }
        )
        self.media_source = source
        self.media_id = media_id
        self.names = normalize_title_names(
            self.names,
            excluded=(self.title, self.original_title),
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化字典。"""
        value = asdict(self)
        # 空别名不写入载荷，保持已有 V4 快照的内容 hash 稳定。
        if not self.names:
            value.pop("names", None)
        return value

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
            media_source=str(value.get("media_source") or ""),
            media_id=str(value.get("media_id") or ""),
            source_ids=dict(value.get("source_ids") or {}),
            sources=[str(item) for item in value.get("sources") or []],
            original_title=str(value.get("original_title") or ""),
            names=normalize_title_names(
                value.get("names") or (),
                excluded=(title, value.get("original_title") or ""),
            ),
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
