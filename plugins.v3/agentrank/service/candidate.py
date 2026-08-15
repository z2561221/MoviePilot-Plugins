"""多来源候选规范化、去重与快照服务。"""

from collections import deque
from dataclasses import dataclass, field
import math
import re
import time
from typing import Any, Deque, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from ..adapter.discovery import DiscoveryAdapter, DiscoveryFetchResult, RawDiscoveredItem
from ..model.candidate import Candidate, typed_tmdb_candidate_id
from ..model.candidate_snapshot import CandidateSnapshot
from ..model.retrieval import RetrievalPlan
from ..storage.repository import AgentRankRepository


DEFAULT_FROZEN_CANDIDATE_TARGET = 15
DEFAULT_MINIMUM_FROZEN_CANDIDATES = 10
DEFAULT_CANDIDATE_SURVIVAL_RATE = 0.5
MIN_INITIAL_RECALL = 20
MAX_INITIAL_RECALL = 30
MIN_SUPPLEMENT_RECALL = 5
MAX_SUPPLEMENT_RECALL = 10
MAX_RAW_RECALL = 150
MAX_RECALL_ROUNDS = 25
MAX_STALLED_RECALL_ROUNDS = 3
RECOGNITION_BATCH_SIZE = 6
_MEDIAID_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
_MEDIAID_PREFIX_ALIASES = {
    "tmdb": "tmdb",
    "themoviedb": "tmdb",
    "douban": "douban",
    "bangumi": "bangumi",
    "bgm": "bangumi",
    "anilist": "anilist",
    "tvdb": "tvdb",
    "imdb": "imdb",
}


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
    timings_ms: Dict[str, int] = field(default_factory=dict)
    processing_counts: Dict[str, int] = field(default_factory=dict)
    survival_rate_used: float = DEFAULT_CANDIDATE_SURVIVAL_RATE
    candidate_survival_rate: float = 0.0


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

    @staticmethod
    def _mediaid_prefix(value: Any) -> str:
        """校验并规范 MoviePilot 通用媒体来源前缀。"""
        text = str(value or "").strip().casefold()
        if not text:
            return ""
        normalized = _MEDIAID_PREFIX_ALIASES.get(text, text)
        if not _MEDIAID_PREFIX_PATTERN.fullmatch(normalized):
            raise ValueError("extension mediaid_prefix is invalid")
        return normalized

    @classmethod
    def _source_ids(
        cls, data: Mapping[str, Any], trusted_prefix: str
    ) -> Dict[str, str]:
        """只提取受支持的媒体标识，并校验扩展源前缀。"""
        aliases = {
            "tmdb": ("tmdb_id", "tmdbid", "themoviedb", "themoviedb_id"),
            "douban": ("douban_id", "doubanid"),
            "bangumi": ("bangumi_id", "bangumiid", "bgm", "bgm_id"),
            "anilist": ("anilist_id", "anilistid"),
            "tvdb": ("tvdb_id", "tvdbid"),
            "imdb": ("imdb_id", "imdbid"),
        }
        ids = {
            target: str(value)
            for target, names in aliases.items()
            if (value := cls._first(data, *names)) not in (None, "")
        }
        media_id = cls._first(data, "media_id", "mediaid")
        payload_prefix_value = cls._first(data, "mediaid_prefix", "media_source")
        if payload_prefix_value in (None, "") and media_id not in (None, ""):
            payload_prefix_value = data.get("source")
        payload_prefix = cls._mediaid_prefix(payload_prefix_value)
        expected_prefix = cls._mediaid_prefix(trusted_prefix)
        if expected_prefix and payload_prefix and payload_prefix != expected_prefix:
            raise ValueError("extension mediaid_prefix mismatch")
        resolved_prefix = payload_prefix or expected_prefix
        if media_id not in (None, "") and resolved_prefix:
            ids[resolved_prefix] = str(media_id)
        return ids

    @staticmethod
    def _candidate_id(ids: Mapping[str, str], media_type: str) -> str:
        """优先生成类型化 TMDB 身份，否则保留待识别来源身份。"""
        if ids.get("tmdb"):
            try:
                return typed_tmdb_candidate_id(ids["tmdb"], media_type)
            except ValueError:
                pass
        for name in ("douban", "bangumi", "anilist", "tvdb", "imdb"):
            if ids.get(name):
                return f"{name}:{ids[name]}"
        for name, media_id in ids.items():
            if name != "tmdb" and media_id:
                return f"{name}:{media_id}"
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
        if source == "anilist":
            return "anime"
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
        requested_media_type = str(
            getattr(raw, "requested_media_type", "") or ""
        ).strip().casefold()
        if requested_media_type in {"movie", "tv", "anime"}:
            safe_metadata["requested_media_type"] = requested_media_type
        genre_ids = cls._strings(cls._first(data, "genre_ids", "genreIds"))
        if genre_ids:
            safe_metadata["genre_ids"] = genre_ids
        category = cls._first(data, "category")
        if category:
            safe_metadata["category"] = str(category)
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
    def _metadata_values(candidate: Candidate, name: str) -> List[str]:
        """读取候选 metadata 中可作为过滤线索的字符串列表。"""
        value = candidate.metadata.get(name, "")
        if isinstance(value, (list, tuple, set)):
            items = value
        else:
            items = [value]
        return [str(item).strip() for item in items if str(item or "").strip()]

    @classmethod
    def _has_animation_hint(
        cls, candidate: Candidate, include_requested_type: bool = False
    ) -> bool:
        """判断识别前候选是否带有动画事实线索。"""
        genre_ids = {
            item.casefold()
            for item in cls._metadata_values(candidate, "genre_ids")
        }
        if "16" in genre_ids:
            return True
        texts = [
            *candidate.genres,
            candidate.metadata.get("category", ""),
        ]
        if include_requested_type:
            texts.append(candidate.metadata.get("requested_media_type", ""))
        haystack = " ".join(str(item or "") for item in texts).casefold()
        return any(
            token in haystack
            for token in ("animation", "anime", "动画", "动漫", "番剧")
        )

    @classmethod
    def _media_type_matches_filter(
        cls,
        candidate: Candidate,
        allowed: Set[str],
        allow_animation_hints: bool = False,
    ) -> bool:
        """按过滤条件判断候选媒体类型是否可进入下一阶段。"""
        candidate_type = str(candidate.media_type or "").strip().casefold()
        if candidate_type in allowed:
            return True
        if allow_animation_hints and "anime" in allowed:
            return cls._has_animation_hint(candidate, include_requested_type=True)
        return False

    @staticmethod
    def _typed_identity(candidate: Candidate) -> str:
        """从 V3 TMDB 主身份与基础媒体类型生成候选最终身份。"""
        if candidate.media_source != "themoviedb":
            raise ValueError("candidate primary identity is not TMDB")
        return typed_tmdb_candidate_id(
            candidate.media_id,
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

    def _library_candidate_ids(self, candidates: Iterable[Candidate]) -> Set[str]:
        """批量读取媒体库身份；旧适配器回退为兼容逐条检查。"""
        items = list(candidates or ())
        if self._library_adapter is None or not items:
            return set()
        candidate_ids = getattr(self._library_adapter, "candidate_ids", None)
        if callable(candidate_ids):
            return set(candidate_ids(items) or set())
        return {
            candidate.candidate_id
            for candidate in items
            if self._library_adapter.exists(candidate)
        }

    def _recent_survival_rate(self, profile_id: str) -> float:
        """读取最近成功运行的候选存活率，没有历史时使用保守默认值。"""
        try:
            history = self._repository.load_run_history(profile_id)
        except Exception:
            return DEFAULT_CANDIDATE_SURVIVAL_RATE
        for run in history:
            if str(getattr(run, "status", "")) not in {
                "success",
                "recommendation_degraded",
                "recommendation_incomplete",
            }:
                continue
            metrics = dict(getattr(run, "metrics", {}) or {})
            try:
                rate = float(metrics.get("candidate_survival_rate") or 0.0)
            except (TypeError, ValueError):
                continue
            if rate > 0:
                return max(0.1, min(rate, 1.0))
        return DEFAULT_CANDIDATE_SURVIVAL_RATE

    @staticmethod
    def _initial_recall_budget(target: int, survival_rate: float) -> int:
        """按最近存活率计算 20-30 条首批原始召回预算。"""
        estimated = math.ceil(max(1, int(target)) / max(0.1, survival_rate))
        return max(MIN_INITIAL_RECALL, min(estimated, MAX_INITIAL_RECALL))

    @staticmethod
    def _supplement_recall_budget(remaining: int, survival_rate: float) -> int:
        """按剩余缺口计算 5-10 条补充召回预算。"""
        estimated = math.ceil(max(1, int(remaining)) / max(0.1, survival_rate))
        return max(MIN_SUPPLEMENT_RECALL, min(estimated, MAX_SUPPLEMENT_RECALL))

    @staticmethod
    def _merge_fetch_result(
        target: DiscoveryFetchResult,
        incoming: DiscoveryFetchResult,
        recall_round: int,
    ) -> None:
        """汇总多轮召回证据并保留每轮编号。"""
        target.items.extend(incoming.items)
        target.source_errors.update(incoming.source_errors)
        target.rejected_sources.extend(
            source
            for source in incoming.rejected_sources
            if source not in target.rejected_sources
        )
        for source, count in incoming.source_counts.items():
            target.source_counts[source] = target.source_counts.get(source, 0) + count
        for layer, count in incoming.layer_counts.items():
            target.layer_counts[layer] = target.layer_counts.get(layer, 0) + count
        for recipe in incoming.request_recipes:
            marked = dict(recipe)
            marked["recall_round"] = recall_round
            target.request_recipes.append(marked)

    @classmethod
    def _cheap_filter_reason(
        cls,
        candidate: Candidate,
        retrieval_plan: Optional[RetrievalPlan],
        negative_keywords: Iterable[str],
    ) -> str:
        """在媒体识别前执行只依赖来源字段的廉价硬过滤。"""
        filters = retrieval_plan.filters if retrieval_plan is not None else None
        if filters and filters.media_types:
            allowed = set(filters.media_types)
            if not cls._media_type_matches_filter(
                candidate, allowed, allow_animation_hints=True
            ):
                return "media_type"
        if filters and candidate.year is not None:
            if filters.year_min is not None and candidate.year < filters.year_min:
                return "year"
            if filters.year_max is not None and candidate.year > filters.year_max:
                return "year"
        if cls._negative_match(candidate, negative_keywords):
            return "negative_keyword"
        return ""

    @classmethod
    def _recognition_priority(
        cls, candidate: Candidate, retrieval_plan: Optional[RetrievalPlan]
    ) -> Tuple[float, ...]:
        """按来源现有事实生成媒体识别优先级，不表达最终用户契合度。"""
        filters = retrieval_plan.filters if retrieval_plan is not None else None
        type_match = 1.0
        if filters and filters.media_types:
            type_match = float(
                cls._media_type_matches_filter(
                    candidate,
                    set(filters.media_types),
                    allow_animation_hints=True,
                )
            )
        rating = float(candidate.rating or 0.0)
        popularity = float(candidate.popularity or 0.0)
        freshness = float(candidate.year or 0)
        completeness = float(
            sum(
                bool(value)
                for value in (
                    candidate.year,
                    candidate.original_title,
                    candidate.overview,
                    candidate.rating,
                    candidate.popularity,
                    candidate.release_date,
                )
            )
        )
        return type_match, completeness, rating, popularity, freshness

    def _recognize_batch(
        self, candidates: Iterable[Candidate]
    ) -> List[Optional[Candidate]]:
        """通过批量适配器识别一批候选并隔离单条预期失败。"""
        items = list(candidates or ())
        if self._media_adapter is None:
            return list(items)
        recognize_many = getattr(self._media_adapter, "recognize_many", None)
        if callable(recognize_many):
            return list(recognize_many(items))
        result: List[Optional[Candidate]] = []
        for candidate in items:
            try:
                result.append(self._media_adapter.recognize(candidate))
            except (TypeError, ValueError, KeyError):
                result.append(None)
        return result

    @classmethod
    def _playback_candidate_statuses(cls, samples: Iterable[Any]) -> Dict[str, str]:
        """把非完成播放事实压缩为候选可展示的观看状态。"""
        result: Dict[str, str] = {}
        for sample in samples or ():
            stable_id = cls._field(sample, "stable_id")
            candidate_id = ""
            try:
                candidate_id = typed_tmdb_candidate_id(stable_id)
            except ValueError:
                try:
                    candidate_id = typed_tmdb_candidate_id(
                        cls._field(sample, "tmdb_id"),
                        cls._field(sample, "media_type"),
                    )
                except ValueError:
                    continue
            if bool(cls._field(sample, "completed")):
                result[candidate_id] = "completed"
                continue
            watched_events = max(
                int(cls._field(sample, "play_count") or 0),
                int(cls._field(sample, "watched_episode_count") or 0),
                int(cls._field(sample, "completed_episode_count") or 0),
                int(cls._field(sample, "watch_minutes") or 0),
            )
            if watched_events > 0:
                result[candidate_id] = "partial"
            else:
                result.setdefault(candidate_id, "unknown")
        return result

    def enrich_recommendation_sources(self, recommendations: Iterable[Any]) -> None:
        """仅为最终榜单条目按需补齐跨来源按钮所需的媒体 ID。"""
        enrich = getattr(self._media_adapter, "enrich_cross_source_ids", None)
        if not callable(enrich):
            return
        for recommendation in recommendations or ():
            try:
                enrich(recommendation)
            except Exception:
                # 跨来源补全失败不应撤销已经通过校验的推荐。
                continue

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
        disliked_candidate_ids: Optional[Iterable[str]] = None,
        previous_board_candidate_ids: Optional[Iterable[str]] = None,
        exclude_library_candidates: bool = True,
    ) -> CandidateCollectionResult:
        """动态召回并冻结 10-15 条候选；上一榜重复由最终时近权重处理。"""
        playback_samples = list(playback_samples or ())
        target = max(
            DEFAULT_MINIMUM_FROZEN_CANDIDATES,
            min(int(candidate_limit or DEFAULT_FROZEN_CANDIDATE_TARGET), DEFAULT_FROZEN_CANDIDATE_TARGET),
        )
        maximum_raw = min(MAX_RAW_RECALL, max(1, int(raw_limit or MAX_RAW_RECALL)))
        survival_rate = self._recent_survival_rate(profile_id)
        initial_budget = min(
            maximum_raw, self._initial_recall_budget(target, survival_rate)
        )
        timings_ms: Dict[str, int] = {
            "recall": 0,
            "normalize": 0,
            "recognition": 0,
            "filter": 0,
        }
        processing_counts: Dict[str, int] = {
            "raw": 0,
            "normalized": 0,
            "pre_recognition_deduplicated": 0,
            "recognition_input": 0,
            "recognized": 0,
            "post_recognition_deduplicated": 0,
            "candidate_recognition_cache_hit_count": 0,
            "candidate_recognition_cache_miss_count": 0,
            "initial_recall_budget": initial_budget,
            "supplement_recall_count": 0,
            "recognition_batch_count": 0,
            "previous_board_exclusion_count": 0,
        }
        exclusion_counts = {
            "invalid_or_unrecognized": 0,
            "cheap_media_type": 0,
            "cheap_year": 0,
            "watched_completed": 0,
            "library": 0,
            "subscribed": 0,
            "disliked": 0,
            "archived": 0,
            "previous_board": 0,
            "negative_keyword": 0,
        }
        filter_errors: Dict[str, str] = {}
        status_errors: Dict[str, str] = {}
        watched_ids = self._completed_candidate_ids(playback_samples)
        playback_statuses = self._playback_candidate_statuses(playback_samples)
        archived_ids = {
            str(candidate_id or "").strip()
            for candidate_id in archived_candidate_ids or ()
            if str(candidate_id or "").strip()
        }
        disliked_ids = {
            str(candidate_id or "").strip()
            for candidate_id in disliked_candidate_ids or ()
            if str(candidate_id or "").strip()
        }
        previous_board_ids = {
            str(candidate_id or "").strip()
            for candidate_id in previous_board_candidate_ids or ()
            if str(candidate_id or "").strip()
        }
        try:
            subscribed_ids = self._subscribed_candidate_ids()
        except Exception as error:
            status_errors["subscriptions"] = str(error)
            subscribed_ids = set()

        fetched = DiscoveryFetchResult(raw_limit=maximum_raw)
        pre_recognition_by_id: Dict[str, Candidate] = {}
        recognized_by_id: Dict[str, Candidate] = {}
        candidates: List[Candidate] = []
        rejected_count = 0
        recall_round = 0
        no_new_identity_rounds = 0
        no_new_candidate_rounds = 0
        next_budget = initial_budget
        while (
            not filter_errors
            and len(candidates) < target
            and processing_counts["raw"] < maximum_raw
            and recall_round < MAX_RECALL_ROUNDS
        ):
            recall_round += 1
            accepted_before_round = len(candidates)
            budget = min(next_budget, maximum_raw - processing_counts["raw"])
            stage_clock = time.monotonic()
            if hasattr(self._adapter, "fetch_layered") and (
                retrieval_plan is not None or playback_samples
            ):
                incoming = self._adapter.fetch_layered(
                    enabled_sources,
                    budget,
                    retrieval_plan=retrieval_plan,
                    playback_samples=playback_samples,
                    raw_limit=budget,
                    page=recall_round,
                )
            else:
                incoming = self._adapter.fetch(
                    enabled_sources,
                    budget,
                    retrieval_plan=retrieval_plan,
                    raw_limit=budget,
                )
            timings_ms["recall"] += max(
                0, int((time.monotonic() - stage_clock) * 1000)
            )
            rows = list(incoming.items)[:budget]
            incoming.items = rows
            self._merge_fetch_result(fetched, incoming, recall_round)
            processing_counts["raw"] += len(rows)
            if recall_round > 1:
                processing_counts["supplement_recall_count"] += len(rows)
            if not rows:
                break

            stage_clock = time.monotonic()
            pending: List[Candidate] = []
            new_identity_count = 0
            for raw in self._round_robin(rows):
                try:
                    candidate = self._normalize(raw)
                except (TypeError, ValueError, KeyError):
                    rejected_count += 1
                    exclusion_counts["invalid_or_unrecognized"] += 1
                    continue
                existing = pre_recognition_by_id.get(candidate.candidate_id)
                if existing:
                    self._merge(existing, candidate)
                    processing_counts["pre_recognition_deduplicated"] += 1
                    continue
                pre_recognition_by_id[candidate.candidate_id] = candidate
                new_identity_count += 1
                reason = self._cheap_filter_reason(
                    candidate, retrieval_plan, negative_keywords or ()
                )
                if reason:
                    exclusion_counts[
                        "negative_keyword" if reason == "negative_keyword" else f"cheap_{reason}"
                    ] += 1
                    continue
                pending.append(candidate)
            processing_counts["normalized"] = len(pre_recognition_by_id)
            pending.sort(
                key=lambda item: self._recognition_priority(item, retrieval_plan),
                reverse=True,
            )
            timings_ms["normalize"] += max(
                0, int((time.monotonic() - stage_clock) * 1000)
            )

            while pending and len(candidates) < target and not filter_errors:
                batch = pending[:RECOGNITION_BATCH_SIZE]
                del pending[:RECOGNITION_BATCH_SIZE]
                processing_counts["recognition_batch_count"] += 1
                processing_counts["recognition_input"] += len(batch)
                stage_clock = time.monotonic()
                recognized_items = self._recognize_batch(batch)
                timings_ms["recognition"] += max(
                    0, int((time.monotonic() - stage_clock) * 1000)
                )
                valid_batch: List[Candidate] = []
                for index, source in enumerate(batch):
                    recognized = (
                        recognized_items[index]
                        if index < len(recognized_items)
                        else None
                    )
                    cache_hit = False
                    for value in (source, recognized):
                        metadata = getattr(value, "metadata", None)
                        if isinstance(metadata, dict):
                            cache_hit = (
                                metadata.pop("_recognize_cache_hit", None) is True
                                or cache_hit
                            )
                    count_key = (
                        "candidate_recognition_cache_hit_count"
                        if cache_hit
                        else "candidate_recognition_cache_miss_count"
                    )
                    processing_counts[count_key] += 1
                    try:
                        if recognized is None:
                            raise ValueError("candidate could not be recognized")
                        recognized.candidate_id = self._typed_identity(recognized)
                    except (TypeError, ValueError, KeyError):
                        rejected_count += 1
                        exclusion_counts["invalid_or_unrecognized"] += 1
                        continue
                    existing = recognized_by_id.get(recognized.candidate_id)
                    if existing:
                        self._merge(existing, recognized)
                        processing_counts["post_recognition_deduplicated"] += 1
                        continue
                    recognized_by_id[recognized.candidate_id] = recognized
                    valid_batch.append(recognized)
                processing_counts["recognized"] = len(recognized_by_id)

                stage_clock = time.monotonic()
                try:
                    try:
                        library_ids = self._library_candidate_ids(valid_batch)
                    except Exception as error:
                        # 状态标记失败不能阻断候选召回；硬观看过滤仍可独立执行。
                        status_errors["library"] = str(error)
                        library_ids = set()
                except Exception as error:
                    filter_errors["library"] = str(error)
                    candidates = []
                    break
                filters = (
                    retrieval_plan.filters
                    if retrieval_plan is not None
                    else None
                )
                for candidate in valid_batch:
                    candidate_id = candidate.candidate_id
                    candidate.metadata.pop("requested_media_type", None)
                    candidate.metadata["in_library"] = candidate_id in library_ids
                    candidate.metadata["subscribed"] = candidate_id in subscribed_ids
                    candidate.metadata["watch_status"] = playback_statuses.get(
                        candidate_id, "unwatched"
                    )
                    if (
                        filters
                        and filters.media_types
                        and not self._media_type_matches_filter(
                            candidate,
                            set(filters.media_types),
                            allow_animation_hints=False,
                        )
                    ):
                        exclusion_counts["cheap_media_type"] += 1
                    elif candidate_id in watched_ids:
                        exclusion_counts["watched_completed"] += 1
                    elif exclude_library_candidates and candidate_id in library_ids:
                        exclusion_counts["library"] += 1
                    elif candidate_id in disliked_ids:
                        exclusion_counts["disliked"] += 1
                    elif candidate_id in archived_ids:
                        exclusion_counts["archived"] += 1
                    elif self._negative_match(candidate, negative_keywords or ()):
                        exclusion_counts["negative_keyword"] += 1
                    else:
                        candidates.append(candidate)
                        if len(candidates) >= target:
                            break
                timings_ms["filter"] += max(
                    0, int((time.monotonic() - stage_clock) * 1000)
                )

            if len(candidates) >= target or processing_counts["raw"] >= maximum_raw:
                break
            legacy_exhausted = (
                getattr(self._adapter, "_source_fetchers", None) is not None
                and len(rows) < budget
            )
            if legacy_exhausted:
                break
            no_new_identity_rounds = (
                no_new_identity_rounds + 1 if new_identity_count == 0 else 0
            )
            no_new_candidate_rounds = (
                no_new_candidate_rounds + 1
                if len(candidates) == accepted_before_round
                else 0
            )
            if (
                no_new_identity_rounds >= MAX_STALLED_RECALL_ROUNDS
                or no_new_candidate_rounds >= MAX_STALLED_RECALL_ROUNDS
            ):
                break
            next_budget = self._supplement_recall_budget(
                target - len(candidates), survival_rate
            )

        for candidate in candidates:
            candidate.metadata.pop("requested_media_type", None)
        processing_counts["recall_round_count"] = recall_round
        processing_counts["no_new_identity_rounds"] = no_new_identity_rounds
        processing_counts["no_new_candidate_rounds"] = no_new_candidate_rounds
        processing_counts["accepted"] = len(candidates)
        processing_counts["previous_board_exclusion_count"] = exclusion_counts[
            "previous_board"
        ]
        processing_counts["early_stop"] = int(len(candidates) >= target)
        current_survival_rate = (
            len(candidates) / processing_counts["raw"]
            if processing_counts["raw"]
            else 0.0
        )

        if status_errors:
            fetched.source_errors.update(status_errors)
        if filter_errors:
            status = "candidate_filter_failed"
        else:
            status = (
                "ready"
                if len(candidates) >= DEFAULT_MINIMUM_FROZEN_CANDIDATES
                else "candidate_insufficient"
            )
        snapshot = None
        snapshot_error = ""
        stage_clock = time.monotonic()
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
        timings_ms["snapshot"] = max(
            0, int((time.monotonic() - stage_clock) * 1000)
        )
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
            minimum_frozen_candidates=min(DEFAULT_MINIMUM_FROZEN_CANDIDATES, target),
            timings_ms=timings_ms,
            processing_counts=processing_counts,
            survival_rate_used=survival_rate,
            candidate_survival_rate=current_survival_rate,
        )
