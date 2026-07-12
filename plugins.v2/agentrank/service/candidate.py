"""多来源候选规范化、去重与快照服务。"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ..adapter.discovery import DiscoveryAdapter, RawDiscoveredItem
from ..model.candidate import Candidate
from ..storage.repository import AgentRankRepository


@dataclass
class CandidateCollectionResult:
    """表示候选采集结果及来源级错误。"""

    username: str
    run_id: str
    status: str
    candidates: List[Candidate] = field(default_factory=list)
    source_errors: Dict[str, str] = field(default_factory=dict)
    rejected_sources: List[str] = field(default_factory=list)
    rejected_count: int = 0


class CandidateCollectionService:
    """选择可信字段、合并跨来源身份并先冻结候选池。"""

    def __init__(self, adapter: DiscoveryAdapter, repository: AgentRankRepository):
        """绑定发现读取边界和持久化仓库。"""
        self._adapter = adapter
        self._repository = repository

    @staticmethod
    def _mapping(payload: Any) -> Dict[str, Any]:
        """将字典或 MediaInfo 转为独立字典；其他类型拒绝。"""
        if isinstance(payload, Mapping):
            return dict(payload)
        if hasattr(payload, "to_dict"):
            value = payload.to_dict()
            if isinstance(value, Mapping):
                return dict(value)
        if hasattr(payload, "model_dump"):
            value = payload.model_dump()
            if isinstance(value, Mapping):
                return dict(value)
        raise ValueError("candidate payload must be a mapping")

    @staticmethod
    def _first(data: Mapping[str, Any], *names: str) -> Any:
        """返回别名列表中的第一个非空字段。"""
        for name in names:
            if data.get(name) not in (None, ""):
                return data.get(name)
        return None

    @classmethod
    def _source_ids(
        cls, data: Mapping[str, Any], trusted_prefix: str
    ) -> Dict[str, str]:
        """只提取受支持的媒体标识，并校验扩展源前缀。"""
        aliases = {
            "tmdb": ("tmdb_id", "tmdbid"),
            "douban": ("douban_id", "doubanid"),
            "bangumi": ("bangumi_id", "bangumiid"),
            "tvdb": ("tvdb_id", "tvdbid"),
            "imdb": ("imdb_id", "imdbid"),
        }
        ids = {
            target: str(value)
            for target, names in aliases.items()
            if (value := cls._first(data, *names)) not in (None, "")
        }
        media_id = cls._first(data, "media_id", "mediaid")
        payload_prefix = str(data.get("mediaid_prefix") or trusted_prefix or "").strip()
        if trusted_prefix and payload_prefix != trusted_prefix:
            raise ValueError("extension mediaid_prefix mismatch")
        if media_id not in (None, "") and payload_prefix:
            ids[payload_prefix] = str(media_id)
        return ids

    @staticmethod
    def _candidate_id(ids: Mapping[str, str]) -> str:
        """按稳定平台优先级生成唯一候选标识。"""
        for name in ("tmdb", "douban", "bangumi", "tvdb", "imdb"):
            if ids.get(name):
                return f"{name}:{ids[name]}"
        for name in sorted(ids):
            if ids[name]:
                return f"{name}:{ids[name]}"
        raise ValueError("candidate requires a traceable media id")

    @classmethod
    def _media_type(cls, data: Mapping[str, Any], source: str) -> str:
        """规范化候选媒体类型。"""
        raw = str(cls._first(data, "media_type", "type", "category") or "").lower()
        if "bangumi" in source or any(token in raw for token in ("anime", "动漫", "动画")):
            return "anime"
        if any(token in raw for token in ("movie", "电影")):
            return "movie"
        if any(token in raw for token in ("tv", "电视剧", "剧集")):
            return "tv"
        return "unknown"

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        """把可用数值转为浮点，无效时返回空。"""
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _strings(value: Any) -> List[str]:
        """把来源字段规范化为唯一字符串列表。"""
        if value is None:
            return []
        items = value if isinstance(value, (list, tuple, set)) else [value]
        result: List[str] = []
        for item in items:
            if isinstance(item, Mapping):
                item = item.get("name") or item.get("title")
            text = str(item or "").strip()
            if text and text not in result:
                result.append(text)
        return result

    @classmethod
    def _normalize(cls, raw: RawDiscoveredItem) -> Candidate:
        """从不可信 payload 中仅选择候选 schema 允许的字段。"""
        data = cls._mapping(raw.payload)
        title = str(cls._first(data, "title", "name") or "").strip()
        if not title:
            raise ValueError("candidate title is required")
        ids = cls._source_ids(data, raw.mediaid_prefix)
        release_date = str(
            cls._first(data, "release_date", "first_air_date", "air_date") or ""
        )
        raw_year = cls._first(data, "year") or release_date[:4]
        try:
            year = int(raw_year) if raw_year else None
        except (TypeError, ValueError):
            year = None
        safe_metadata: Dict[str, Any] = {}
        original_language = cls._first(data, "original_language", "language")
        if original_language:
            safe_metadata["original_language"] = str(original_language)
        return Candidate(
            candidate_id=cls._candidate_id(ids),
            title=title,
            media_type=cls._media_type(data, raw.source),
            year=year,
            source_ids=ids,
            sources=[raw.source],
            original_title=str(cls._first(data, "original_title", "original_name") or ""),
            overview=str(cls._first(data, "overview", "description") or ""),
            poster_path=str(cls._first(data, "poster_path", "poster") or ""),
            backdrop_path=str(cls._first(data, "backdrop_path", "backdrop") or ""),
            rating=cls._number(cls._first(data, "vote_average", "vote", "rating", "score")),
            popularity=cls._number(cls._first(data, "popularity", "heat")),
            release_date=release_date,
            genres=cls._strings(cls._first(data, "genres", "genre")),
            regions=cls._strings(cls._first(data, "regions", "region", "countries")),
            metadata=safe_metadata,
        )

    @staticmethod
    def _merge(target: Candidate, incoming: Candidate) -> None:
        """合并重复候选的来源、标识和缺失展示字段。"""
        for source in incoming.sources:
            if source not in target.sources:
                target.sources.append(source)
        target.source_ids.update(incoming.source_ids)
        for name in (
            "original_title",
            "overview",
            "poster_path",
            "backdrop_path",
            "release_date",
        ):
            if not getattr(target, name) and getattr(incoming, name):
                setattr(target, name, getattr(incoming, name))
        if target.year is None:
            target.year = incoming.year
        if target.rating is None:
            target.rating = incoming.rating
        if target.popularity is None:
            target.popularity = incoming.popularity
        for name in ("genres", "regions"):
            values = getattr(target, name)
            for item in getattr(incoming, name):
                if item not in values:
                    values.append(item)
        target.metadata.update(incoming.metadata)

    def collect_and_freeze(
        self,
        username: str,
        run_id: str,
        enabled_sources: Mapping[str, Any],
        candidate_limit: int,
    ) -> CandidateCollectionResult:
        """采集、规范化、去重并在返回前冻结候选快照。"""
        fetched = self._adapter.fetch(enabled_sources, max(1, int(candidate_limit)))
        candidates: List[Candidate] = []
        by_id: Dict[str, Candidate] = {}
        rejected_count = 0
        for raw in fetched.items:
            try:
                candidate = self._normalize(raw)
            except (TypeError, ValueError, KeyError):
                rejected_count += 1
                continue
            existing = by_id.get(candidate.candidate_id)
            if existing:
                self._merge(existing, candidate)
                continue
            if len(candidates) >= max(1, int(candidate_limit)):
                continue
            by_id[candidate.candidate_id] = candidate
            candidates.append(candidate)
        self._repository.save_candidate_snapshot(run_id, username, candidates)
        return CandidateCollectionResult(
            username=username,
            run_id=run_id,
            status="ready" if candidates else "candidate_insufficient",
            candidates=candidates,
            source_errors=fetched.source_errors,
            rejected_sources=fetched.rejected_sources,
            rejected_count=rejected_count,
        )
