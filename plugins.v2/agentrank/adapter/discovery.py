"""MoviePilot 推荐与探索 Provider 适配器。"""

import inspect
import re
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

from ..model.retrieval import (
    ISO_639_1_CODES,
    SORT_OPTIONS,
    TMDB_GENRE_IDS,
    RetrievalPlan,
)


DEFAULT_RAW_FETCH_LIMIT = 150
PROVIDER_METHOD_CONTRACTS = {
    "douban_public": {
        "provider": "douban",
        "mode": "discover",
        "params": frozenset({"page"}),
    },
    "tmdb_discover": {
        "provider": "tmdb",
        "mode": "discover",
        "params": frozenset(
            {
                "sort_by",
                "with_genres",
                "with_original_language",
                "with_keywords",
                "with_watch_providers",
                "vote_average",
                "vote_count",
                "release_date",
                "page",
            }
        ),
    },
    "bangumi_discover": {
        "provider": "bangumi",
        "mode": "discover",
        "params": frozenset({"type", "cat", "sort", "year", "offset"}),
    },
    "tmdb_recommend": {
        "provider": "tmdb",
        "mode": "recommend",
        "params": frozenset({"tmdbid"}),
    },
}


def _positive_integer(value: Any, label: str) -> int:
    """读取正整数参数并拒绝布尔值和字符串注入。"""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _id_expression(value: Any, allowed: Optional[set] = None) -> str:
    """校验由竖线连接的正整数 ID 表达式。"""
    text = str(value or "")
    if not text:
        return ""
    if not re.fullmatch(r"[1-9]\d*(?:\|[1-9]\d*)*", text):
        raise ValueError("provider ID expression is invalid")
    identifiers = [int(item) for item in text.split("|")]
    if len(identifiers) > 20:
        raise ValueError("provider ID expression exceeds 20 IDs")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("provider ID expression contains duplicates")
    if allowed is not None and any(item not in allowed for item in identifiers):
        raise ValueError("provider ID expression contains an unknown ID")
    return text


@dataclass(frozen=True)
class ProviderRequest:
    """表示一个仅含白名单参数的 MoviePilot Provider 请求。"""

    request_id: str
    source: str
    provider: str
    mode: str
    method: str
    media_type: str
    limit: int
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """校验方法契约、媒体类型、配额和参数键值。"""
        request_id = str(self.request_id or "").strip()
        source = str(self.source or "").strip()
        if not re.fullmatch(r"[a-z0-9:_-]{1,96}", request_id):
            raise ValueError("provider request_id is invalid")
        if not re.fullmatch(r"[a-z0-9:_-]{1,64}", source):
            raise ValueError("provider source is invalid")
        contract = PROVIDER_METHOD_CONTRACTS.get(self.method)
        if contract is None:
            raise ValueError("provider method is not allowed")
        if self.provider != contract["provider"] or self.mode != contract["mode"]:
            raise ValueError("provider method contract mismatch")
        if self.media_type not in {"movie", "tv", "anime", "mixed"}:
            raise ValueError("provider media_type is invalid")
        if isinstance(self.limit, bool) or not isinstance(self.limit, int):
            raise ValueError("provider limit must be an integer")
        if not 1 <= self.limit <= DEFAULT_RAW_FETCH_LIMIT:
            raise ValueError("provider limit must be between 1 and 150")
        if not isinstance(self.params, Mapping):
            raise ValueError("provider params must be a mapping")
        params = dict(self.params)
        if set(params) != set(contract["params"]):
            raise ValueError("provider params do not match the method whitelist")
        self._validate_params(params)
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "params", MappingProxyType(params))

    def _validate_params(self, params: Dict[str, Any]) -> None:
        """按 MoviePilot chain 签名校验白名单参数值。"""
        if self.method == "douban_public":
            if self.media_type != "mixed" or params["page"] != 1:
                raise ValueError("douban public page must be 1")
            return
        if self.method == "bangumi_discover":
            if (
                self.media_type != "anime"
                or params["type"] != 2
                or params["cat"] is not None
                or params["sort"] != "rank"
                or params["offset"] != 0
            ):
                raise ValueError("bangumi discovery params are invalid")
            year = params["year"]
            if year is not None and (
                isinstance(year, bool)
                or not isinstance(year, int)
                or not 1870 <= year <= 2100
            ):
                raise ValueError("bangumi year is invalid")
            return
        if self.method == "tmdb_recommend":
            _positive_integer(params["tmdbid"], "tmdbid")
            if self.media_type not in {"movie", "tv"}:
                raise ValueError("tmdb recommendation media_type is invalid")
            return
        if self.media_type not in {"movie", "tv"}:
            raise ValueError("tmdb discovery media_type is invalid")
        if params["sort_by"] not in SORT_OPTIONS:
            raise ValueError("tmdb sort_by is invalid")
        _id_expression(params["with_genres"], set(TMDB_GENRE_IDS))
        _id_expression(params["with_keywords"])
        language = str(params["with_original_language"] or "")
        if language and language not in ISO_639_1_CODES:
            raise ValueError("tmdb original language is invalid")
        if params["with_watch_providers"] != "":
            raise ValueError("tmdb watch provider filter is not allowed")
        rating = params["vote_average"]
        if isinstance(rating, bool) or not isinstance(rating, (int, float)):
            raise ValueError("tmdb vote_average is invalid")
        if not 0 <= float(rating) <= 10:
            raise ValueError("tmdb vote_average is out of range")
        votes = params["vote_count"]
        if (
            isinstance(votes, bool)
            or not isinstance(votes, int)
            or not 0 <= votes <= 2_000_000_000
        ):
            raise ValueError("tmdb vote_count is invalid")
        release_date = str(params["release_date"] or "")
        if release_date:
            if not re.fullmatch(r"\d{4}-01-01", release_date):
                raise ValueError("tmdb release_date is invalid")
            if not 1870 <= int(release_date[:4]) <= 2100:
                raise ValueError("tmdb release_date is out of range")
        if params["page"] != 1:
            raise ValueError("tmdb discovery page must be 1")

    def recipe(self) -> Dict[str, Any]:
        """返回不含秘密、可写入运行历史的请求配方。"""
        return {
            "request_id": self.request_id,
            "source": self.source,
            "provider": self.provider,
            "mode": self.mode,
            "method": self.method,
            "media_type": self.media_type,
            "limit": self.limit,
            "params": dict(self.params),
        }


@dataclass
class RawDiscoveredItem:
    """表示带受信来源标签的原始发现条目。"""

    source: str
    payload: Any
    mediaid_prefix: str = ""


@dataclass
class DiscoveryFetchResult:
    """表示多来源读取结果、请求配方与独立失败证据。"""

    items: List[RawDiscoveredItem] = field(default_factory=list)
    source_errors: Dict[str, str] = field(default_factory=dict)
    rejected_sources: List[str] = field(default_factory=list)
    source_counts: Dict[str, int] = field(default_factory=dict)
    request_recipes: List[Dict[str, Any]] = field(default_factory=list)
    raw_limit: int = DEFAULT_RAW_FETCH_LIMIT


class MoviePilotProvider:
    """执行类型化请求并复用 MoviePilot 推荐与探索 chain。"""

    def __init__(
        self, handlers: Optional[Mapping[str, Callable[[ProviderRequest], Iterable[Any]]]] = None
    ):
        """允许测试注入方法 handler；运行时使用宿主 chain。"""
        self._handlers = dict(handlers or {})

    @staticmethod
    def _douban_public(request: ProviderRequest) -> List[Any]:
        """通过 DoubanChain 读取公共热门电影、剧集与动画。"""
        from app.chain.douban import DoubanChain

        chain = DoubanChain()
        each_count = max(1, (request.limit + 2) // 3)
        rows = list(chain.movie_hot(page=1, count=each_count) or [])
        rows.extend(chain.tv_hot(page=1, count=each_count) or [])
        rows.extend(chain.tv_animation(page=1, count=each_count) or [])
        return rows[: request.limit]

    @staticmethod
    def _tmdb_discover(request: ProviderRequest) -> List[Any]:
        """通过 TmdbChain 按白名单配方读取电影或剧集。"""
        from app.chain.tmdb import TmdbChain
        from app.schemas.types import MediaType

        media_type = MediaType.MOVIE if request.media_type == "movie" else MediaType.TV
        rows = TmdbChain().tmdb_discover(mtype=media_type, **dict(request.params))
        return list(rows or [])[: request.limit]

    @staticmethod
    def _bangumi_discover(request: ProviderRequest) -> List[Any]:
        """通过 BangumiChain 读取高排名番剧。"""
        from app.chain.bangumi import BangumiChain

        rows = BangumiChain().discover(limit=request.limit, **dict(request.params))
        return list(rows or [])[: request.limit]

    @staticmethod
    def _tmdb_recommend(request: ProviderRequest) -> List[Any]:
        """通过 TmdbChain 按播放种子读取相关推荐。"""
        from app.chain.tmdb import TmdbChain

        chain = TmdbChain()
        tmdbid = int(request.params["tmdbid"])
        rows = (
            chain.movie_recommend(tmdbid)
            if request.media_type == "movie"
            else chain.tv_recommend(tmdbid)
        )
        return list(rows or [])[: request.limit]

    def execute(self, request: ProviderRequest) -> List[Any]:
        """执行一个已校验请求并强制应用请求上限。"""
        if not isinstance(request, ProviderRequest):
            raise ValueError("provider request is required")
        handler = self._handlers.get(request.method)
        if handler is None:
            handler = {
                "douban_public": self._douban_public,
                "tmdb_discover": self._tmdb_discover,
                "bangumi_discover": self._bangumi_discover,
                "tmdb_recommend": self._tmdb_recommend,
            }[request.method]
        return list(handler(request) or [])[: request.limit]


class DiscoveryAdapter:
    """编排 MoviePilot Provider 请求并隔离来源级故障。"""

    DEFAULT_SOURCE_ORDER = ("douban", "tmdb_movies", "tmdb_tv", "bangumi")

    def __init__(
        self,
        source_fetchers: Optional[Dict[str, Callable[[int], List[Any]]]] = None,
        provider: Optional[MoviePilotProvider] = None,
        raw_fetch_limit: int = DEFAULT_RAW_FETCH_LIMIT,
    ):
        """绑定测试兼容 fetcher 或真实 Provider，并限制全局原始抓取数。"""
        self._source_fetchers = (
            dict(source_fetchers) if source_fetchers is not None else None
        )
        self._provider = provider or MoviePilotProvider()
        self._raw_fetch_limit = max(
            1, min(int(raw_fetch_limit), DEFAULT_RAW_FETCH_LIMIT)
        )

    @staticmethod
    def _quotas(names: Sequence[str], limit: int) -> Dict[str, int]:
        """把全局原始上限无损分配给有序来源。"""
        if not names:
            return {}
        base, remainder = divmod(max(1, int(limit)), len(names))
        return {
            name: base + (1 if index < remainder else 0)
            for index, name in enumerate(names)
            if base + (1 if index < remainder else 0) > 0
        }

    @staticmethod
    def _tmdb_params(plan: Optional[RetrievalPlan]) -> Dict[str, Any]:
        """只从已校验检索计划生成 TmdbChain 支持的参数。"""
        filters = plan.filters if isinstance(plan, RetrievalPlan) else None
        genre_ids = filters.genre_ids if filters else ()
        keyword_ids = filters.keyword_ids if filters else ()
        languages = filters.original_languages if filters else ()
        year_min = filters.year_min if filters else None
        return {
            "sort_by": filters.sort_by if filters else "popularity.desc",
            "with_genres": "|".join(str(item) for item in genre_ids),
            "with_original_language": languages[0] if languages else "",
            "with_keywords": "|".join(str(item) for item in keyword_ids),
            "with_watch_providers": "",
            "vote_average": float(filters.rating_min or 0.0) if filters else 0.0,
            "vote_count": int(filters.vote_count_min or 0) if filters else 0,
            "release_date": f"{year_min:04d}-01-01" if year_min else "",
            "page": 1,
        }

    def _default_requests(
        self,
        enabled_sources: Mapping[str, Any],
        plan: Optional[RetrievalPlan],
        raw_limit: int,
    ) -> List[ProviderRequest]:
        """构造公共探索请求；推荐请求由独立入口接收播放种子。"""
        filters = plan.filters if isinstance(plan, RetrievalPlan) else None
        media_types = set(filters.media_types if filters else ())
        enabled_names = [
            name
            for name in self.DEFAULT_SOURCE_ORDER
            if enabled_sources.get(name, False)
            and not (
                (name == "tmdb_movies" and media_types and "movie" not in media_types)
                or (
                    name == "tmdb_tv"
                    and media_types
                    and not media_types.intersection({"tv", "anime"})
                )
                or (
                    name == "bangumi"
                    and media_types
                    and not media_types.intersection({"tv", "anime"})
                )
            )
        ]
        quotas = self._quotas(enabled_names, raw_limit)
        tmdb_params = self._tmdb_params(plan)
        requests: List[ProviderRequest] = []
        for name, limit in quotas.items():
            if name == "douban":
                requests.append(
                    ProviderRequest(
                        request_id=name,
                        source=name,
                        provider="douban",
                        mode="discover",
                        method="douban_public",
                        media_type="mixed",
                        limit=limit,
                        params={"page": 1},
                    )
                )
            elif name in {"tmdb_movies", "tmdb_tv"}:
                requests.append(
                    ProviderRequest(
                        request_id=name,
                        source=name,
                        provider="tmdb",
                        mode="discover",
                        method="tmdb_discover",
                        media_type="movie" if name == "tmdb_movies" else "tv",
                        limit=limit,
                        params=tmdb_params,
                    )
                )
            else:
                requests.append(
                    ProviderRequest(
                        request_id=name,
                        source=name,
                        provider="bangumi",
                        mode="discover",
                        method="bangumi_discover",
                        media_type="anime",
                        limit=limit,
                        params={
                            "type": 2,
                            "cat": None,
                            "sort": "rank",
                            "year": filters.year_min if filters else None,
                            "offset": 0,
                        },
                    )
                )
        return requests

    @staticmethod
    def _invoke_legacy(fetcher: Callable[..., Any], limit: int) -> List[Any]:
        """调用历史测试 fetcher，同时避免吞掉 fetcher 内部 TypeError。"""
        signature = inspect.signature(fetcher)
        positional = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind
            in {parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD}
        ]
        if not positional and not any(
            item.kind == item.VAR_POSITIONAL
            for item in signature.parameters.values()
        ):
            return list(fetcher() or [])[:limit]
        return list(fetcher(limit) or [])[:limit]

    def _fetch_legacy(
        self, enabled_sources: Mapping[str, Any], raw_limit: int
    ) -> DiscoveryFetchResult:
        """为已有单参数测试 fetcher 提供同等来源隔离与 recipe 证据。"""
        result = DiscoveryFetchResult(raw_limit=raw_limit)
        enabled_names = [
            name
            for name in self._source_fetchers or {}
            if enabled_sources.get(name, False)
        ]
        for source, limit in self._quotas(enabled_names, raw_limit).items():
            recipe = {
                "request_id": source,
                "source": source,
                "provider": "injected",
                "mode": "discover",
                "method": "test_fetcher",
                "media_type": "mixed",
                "limit": limit,
                "params": {},
            }
            result.request_recipes.append(recipe)
            try:
                rows = self._invoke_legacy(self._source_fetchers[source], limit)
            except Exception as error:
                result.source_errors[source] = str(error)
                continue
            result.source_counts[source] = len(rows)
            result.items.extend(
                RawDiscoveredItem(source=source, payload=row) for row in rows
            )
        return result

    def fetch_requests(
        self,
        requests: Sequence[ProviderRequest],
        raw_limit: Optional[int] = None,
    ) -> DiscoveryFetchResult:
        """执行类型化请求，强制全局原始上限并隔离每个请求失败。"""
        limit = max(
            1,
            min(
                int(raw_limit or self._raw_fetch_limit),
                DEFAULT_RAW_FETCH_LIMIT,
            ),
        )
        result = DiscoveryFetchResult(raw_limit=limit)
        remaining = limit
        for request in requests:
            if not isinstance(request, ProviderRequest):
                raise ValueError("fetch_requests only accepts ProviderRequest")
            if remaining <= 0:
                break
            effective = request
            if request.limit > remaining:
                effective = replace(request, limit=remaining)
            result.request_recipes.append(effective.recipe())
            remaining -= effective.limit
            try:
                rows = self._provider.execute(effective)
            except Exception as error:
                result.source_errors[effective.request_id] = str(error)
                continue
            result.source_counts[effective.source] = (
                result.source_counts.get(effective.source, 0) + len(rows)
            )
            result.items.extend(
                RawDiscoveredItem(source=effective.source, payload=row) for row in rows
            )
        return result

    def fetch(
        self,
        enabled_sources: Mapping[str, Any],
        count: int,
        retrieval_plan: Optional[RetrievalPlan] = None,
        raw_limit: Optional[int] = None,
    ) -> DiscoveryFetchResult:
        """按默认 150 条原始上限执行公共探索 Provider。"""
        if not isinstance(enabled_sources, Mapping):
            return DiscoveryFetchResult(raw_limit=self._raw_fetch_limit)
        limit = max(
            1,
            min(
                int(raw_limit or self._raw_fetch_limit),
                DEFAULT_RAW_FETCH_LIMIT,
            ),
        )
        if self._source_fetchers is not None:
            return self._fetch_legacy(enabled_sources, limit)
        requests = self._default_requests(enabled_sources, retrieval_plan, limit)
        return self.fetch_requests(requests, raw_limit=limit)

    def fetch_recommendations(
        self,
        playback_samples: Iterable[Mapping[str, Any]],
        raw_limit: Optional[int] = None,
    ) -> DiscoveryFetchResult:
        """按类型化 TMDB 播放种子执行公共推荐 Provider。"""
        limit = max(
            1,
            min(
                int(raw_limit or self._raw_fetch_limit),
                DEFAULT_RAW_FETCH_LIMIT,
            ),
        )
        seeds: List[tuple[str, int]] = []
        for sample in playback_samples or ():
            if not isinstance(sample, Mapping):
                continue
            media_type = str(sample.get("media_type") or "").strip()
            raw_id = sample.get("tmdb_id")
            if media_type not in {"movie", "tv"} or isinstance(raw_id, bool):
                continue
            if isinstance(raw_id, int):
                tmdbid = raw_id
            elif isinstance(raw_id, str) and re.fullmatch(r"[1-9]\d*", raw_id.strip()):
                tmdbid = int(raw_id.strip())
            else:
                continue
            seed = (media_type, tmdbid)
            if tmdbid > 0 and seed not in seeds:
                seeds.append(seed)
        quotas = self._quotas(
            [f"{media_type}:{tmdbid}" for media_type, tmdbid in seeds], limit
        )
        requests = [
            ProviderRequest(
                request_id=f"tmdb_recommend:{media_type}:{tmdbid}",
                source="tmdb_recommend",
                provider="tmdb",
                mode="recommend",
                method="tmdb_recommend",
                media_type=media_type,
                limit=quotas[f"{media_type}:{tmdbid}"],
                params={"tmdbid": tmdbid},
            )
            for media_type, tmdbid in seeds
            if f"{media_type}:{tmdbid}" in quotas
        ]
        return self.fetch_requests(requests, raw_limit=limit)
