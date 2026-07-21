"""多来源候选规范化、去重与快照服务。"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from ..adapter.discovery import DiscoveryAdapter, RawDiscoveredItem
from ..model.candidate import Candidate, typed_tmdb_candidate_id
from ..model.candidate_snapshot import CandidateSnapshot
from ..model.retrieval import RetrievalPlan
from ..storage.repository import AgentRankRepository


DEFAULT_MINIMUM_FROZEN_CANDIDATES = 20


@dataclass
class CandidateCollectionResult:
    """表示候选采集结果及来源级错误。"""

    profile_id: str
    run_id: str
    status: str
    candidates: List[Candidate] = field(default_factory=list)
    source_errors: Dict[str, str] = field(default_factory=dict)
    rejected_sources: List[str] = field(default_factory=list)
    rejected_count: int = 0
    fetched_source_counts: Dict[str, int] = field(default_factory=dict)
    accepted_source_counts: Dict[str, int] = field(default_factory=dict)
    request_recipes: List[Dict[str, Any]] = field(default_factory=list)
    layer_counts: Dict[str, int] = field(default_factory=dict)
    exclusion_counts: Dict[str, int] = field(default_factory=dict)
    filter_errors: Dict[str, str] = field(default_factory=dict)
    snapshot: Optional[CandidateSnapshot] = None
    snapshot_error: str = ""
    minimum_frozen_candidates: int = DEFAULT_MINIMUM_FROZEN_CANDIDATES


class CandidateCollectionService:
    """选择可信字段、合并跨来源身份并先冻结候选池。"""

    def __init__(
        self,
        adapter: DiscoveryAdapter,
        repository: AgentRankRepository,
        media_adapter: Any = None,
        library_adapter: Any = None,
        subscription_adapter: Any = None,
    ):
        """绑定发现读取边界和持久化仓库。"""
        self._adapter = adapter
        self._repository = repository
        self._media_adapter = media_adapter
        self._library_adapter = library_adapter
        self._subscription_adapter = subscription_adapter

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
    def _candidate_id(ids: Mapping[str, str], media_type: str) -> str:
        """优先生成类型化 TMDB 身份，否则保留待识别来源身份。"""
        if ids.get("tmdb"):
            try:
                return typed_tmdb_candidate_id(ids["tmdb"], media_type)
            except ValueError:
                pass
        for name in ("douban", "bangumi", "tvdb", "imdb"):
            if ids.get(name):
                return f"{name}:{ids[name]}"
        raise ValueError("candidate requires a traceable media id")

    @classmethod
    def _media_type(cls, data: Mapping[str, Any], source: str) -> str:
        """仅按来源载荷规范化候选媒体类型，不把来源名称当作类型。"""
        raw = str(cls._first(data, "media_type", "type", "category") or "").lower()
        if any(token in raw for token in ("anime", "动漫", "动画")):
            return "anime"
        if any(token in raw for token in ("movie", "电影")):
            return "movie"
        if any(token in raw for token in ("tv", "电视剧", "剧集")):
            return "tv"
        if source == "tmdb_movies":
            return "movie"
        if source in {"tmdb_tv", "bangumi"}:
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
        media_type = cls._media_type(data, raw.source)
        return Candidate(
            candidate_id=cls._candidate_id(ids, media_type),
            title=title,
            media_type=media_type,
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
            actors=cls._strings(cls._first(data, "actors", "actor", "casts")),
            directors=cls._strings(cls._first(data, "directors", "director")),
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
        for name in ("genres", "regions", "actors", "directors"):
            values = getattr(target, name)
            for item in getattr(incoming, name):
                if item not in values:
                    values.append(item)
        target.metadata.update(incoming.metadata)

    @staticmethod
    def _round_robin(items: Iterable[RawDiscoveredItem]) -> Iterable[RawDiscoveredItem]:
        """按来源轮询原始候选，避免固定来源顺序抢占全局上限。"""
        queues: Dict[str, Deque[RawDiscoveredItem]] = {}
        for item in items:
            queues.setdefault(item.source, deque()).append(item)
        active_sources = list(queues)
        while active_sources:
            next_sources: List[str] = []
            for source in active_sources:
                queue = queues[source]
                if queue:
                    yield queue.popleft()
                if queue:
                    next_sources.append(source)
            active_sources = next_sources

    @staticmethod
    def _source_counts(candidates: Iterable[Candidate]) -> Dict[str, int]:
        """统计最终候选中每个受信来源的覆盖数量。"""
        counts: Dict[str, int] = {}
        for candidate in candidates:
            for source in candidate.sources:
                counts[source] = counts.get(source, 0) + 1
        return counts

    @staticmethod
    def _field(value: Any, name: str) -> Any:
        """兼容映射与领域对象读取安全字段。"""
        if isinstance(value, Mapping):
            return value.get(name)
        return getattr(value, name, None)

    @classmethod
    def _completed_candidate_ids(cls, samples: Iterable[Any]) -> Set[str]:
        """从 Playback Reporting 样本提取已看完的类型化身份。"""
        result: Set[str] = set()
        for sample in samples:
            if not bool(cls._field(sample, "completed")):
                continue
            stable_id = cls._field(sample, "stable_id")
            try:
                result.add(typed_tmdb_candidate_id(stable_id))
                continue
            except ValueError:
                pass
            try:
                result.add(
                    typed_tmdb_candidate_id(
                        cls._field(sample, "tmdb_id"),
                        cls._field(sample, "media_type"),
                    )
                )
            except ValueError:
                continue
        return result

    @staticmethod
    def _negative_match(candidate: Candidate, keywords: Iterable[Any]) -> bool:
        """对可信候选文本执行大小写与空白无关的负向关键词匹配。"""
        values = [
            candidate.title,
            candidate.original_title,
            candidate.overview,
            *candidate.genres,
            *candidate.regions,
            *candidate.actors,
            *candidate.directors,
            candidate.metadata.get("category", ""),
        ]
        searchable = [
            "".join(str(value or "").casefold().split())
            for value in values
            if str(value or "").strip()
        ]
        for keyword in keywords:
            needle = "".join(str(keyword or "").casefold().split())
            if needle and any(needle in value for value in searchable):
                return True
        return False

    @staticmethod
    def _typed_identity(candidate: Candidate) -> str:
        """从 TMDB ID 与基础媒体类型生成候选最终身份。"""
        return typed_tmdb_candidate_id(
            candidate.source_ids.get("tmdb"),
            candidate.media_type,
            candidate.metadata.get("mp_media_type", ""),
        )

    def _subscribed_candidate_ids(self) -> Set[str]:
        """通过全局订阅适配器读取所有用户名下的类型化身份。"""
        if self._subscription_adapter is None:
            return set()
        candidate_ids = getattr(self._subscription_adapter, "candidate_ids", None)
        if not callable(candidate_ids):
            raise RuntimeError("subscription adapter does not expose candidate_ids")
        return set(candidate_ids() or set())

    def collect_and_freeze(
        self,
        profile_id: str,
        run_id: str,
        enabled_sources: Mapping[str, Any],
        candidate_limit: int,
        retrieval_plan: Optional[RetrievalPlan] = None,
        raw_limit: Optional[int] = None,
        playback_samples: Optional[Iterable[Any]] = None,
        archived_candidate_ids: Optional[Iterable[str]] = None,
        negative_keywords: Optional[Iterable[str]] = None,
        profile_version: Optional[Mapping[str, Any]] = None,
    ) -> CandidateCollectionResult:
        """采集、类型化去重、硬过滤并在返回前冻结候选快照。"""
        playback_samples = list(playback_samples or ())
        if hasattr(self._adapter, "fetch_layered") and (
            retrieval_plan is not None or playback_samples
        ):
            fetched = self._adapter.fetch_layered(
                enabled_sources,
                max(1, int(candidate_limit)),
                retrieval_plan=retrieval_plan,
                playback_samples=playback_samples,
                raw_limit=raw_limit,
            )
        else:
            fetched = self._adapter.fetch(
                enabled_sources,
                max(1, int(candidate_limit)),
                retrieval_plan=retrieval_plan,
                raw_limit=raw_limit,
            )
        normalized_candidates: List[Candidate] = []
        by_id: Dict[str, Candidate] = {}
        rejected_count = 0
        limit = max(1, int(candidate_limit))
        for raw in self._round_robin(fetched.items):
            try:
                candidate = self._normalize(raw)
                if self._media_adapter is not None:
                    candidate = self._media_adapter.recognize(candidate)
                    if candidate is None:
                        raise ValueError("candidate could not be recognized as TMDB media")
                candidate.candidate_id = self._typed_identity(candidate)
            except (TypeError, ValueError, KeyError):
                rejected_count += 1
                continue
            existing = by_id.get(candidate.candidate_id)
            if existing:
                self._merge(existing, candidate)
                continue
            by_id[candidate.candidate_id] = candidate
            normalized_candidates.append(candidate)

        exclusion_counts = {
            "invalid_or_unrecognized": rejected_count,
            "watched_completed": 0,
            "library": 0,
            "subscribed": 0,
            "archived": 0,
            "negative_keyword": 0,
        }
        filter_errors: Dict[str, str] = {}
        watched_ids = self._completed_candidate_ids(playback_samples)
        archived_ids = {
            str(candidate_id or "").strip()
            for candidate_id in archived_candidate_ids or ()
            if str(candidate_id or "").strip()
        }
        try:
            subscribed_ids = self._subscribed_candidate_ids()
        except Exception as error:
            filter_errors["subscriptions"] = str(error)
            subscribed_ids = set()

        candidates: List[Candidate] = []
        if not filter_errors:
            for candidate in normalized_candidates:
                candidate_id = candidate.candidate_id
                if candidate_id in watched_ids:
                    exclusion_counts["watched_completed"] += 1
                    continue
                try:
                    in_library = bool(
                        self._library_adapter is not None
                        and self._library_adapter.exists(candidate)
                    )
                except Exception as error:
                    filter_errors["library"] = str(error)
                    candidates = []
                    break
                if in_library:
                    exclusion_counts["library"] += 1
                    continue
                if candidate_id in subscribed_ids:
                    exclusion_counts["subscribed"] += 1
                    continue
                if candidate_id in archived_ids:
                    exclusion_counts["archived"] += 1
                    continue
                if self._negative_match(candidate, negative_keywords or ()):
                    exclusion_counts["negative_keyword"] += 1
                    continue
                candidates.append(candidate)
                if len(candidates) >= limit:
                    break

        if filter_errors:
            status = "candidate_filter_failed"
        else:
            status = "ready" if candidates else "candidate_insufficient"
        snapshot = None
        snapshot_error = ""
        if not filter_errors:
            source_stats = {
                "fetched_source_counts": dict(fetched.source_counts),
                "accepted_source_counts": self._source_counts(candidates),
                "layer_counts": dict(getattr(fetched, "layer_counts", {}) or {}),
                "source_error_count": len(fetched.source_errors),
            }
            try:
                pending_snapshot = CandidateSnapshot.create(
                    profile_id=profile_id,
                    run_id=run_id,
                    profile_version=(
                        profile_version
                        or {"run_id": run_id, "schema_version": 1}
                    ),
                    retrieval_plan=(
                        retrieval_plan.to_dict() if retrieval_plan is not None else {}
                    ),
                    candidates=candidates,
                    source_stats=source_stats,
                    exclusion_counts=exclusion_counts,
                )
                self._repository.save_candidate_snapshot(pending_snapshot)
                snapshot = self._repository.load_candidate_snapshot_record(
                    run_id, profile_id
                )
                if snapshot is None:
                    raise ValueError("candidate snapshot readback failed")
                candidates = list(snapshot.candidates)
            except Exception as error:
                snapshot_error = str(error)
                status = "candidate_snapshot_failed"
                candidates = []
        return CandidateCollectionResult(
            profile_id=profile_id,
            run_id=run_id,
            status=status,
            candidates=candidates,
            source_errors=fetched.source_errors,
            rejected_sources=fetched.rejected_sources,
            rejected_count=rejected_count,
            fetched_source_counts=dict(fetched.source_counts),
            accepted_source_counts=self._source_counts(candidates),
            request_recipes=list(getattr(fetched, "request_recipes", []) or []),
            layer_counts=dict(getattr(fetched, "layer_counts", {}) or {}),
            exclusion_counts=exclusion_counts,
            filter_errors=filter_errors,
            snapshot=snapshot,
            snapshot_error=snapshot_error,
            minimum_frozen_candidates=min(DEFAULT_MINIMUM_FROZEN_CANDIDATES, limit),
        )
