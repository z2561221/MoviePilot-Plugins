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
RECALL_LAYER_ORDER = ("exact", "relaxed", "adjacent", "public_recommend")
DEFAULT_RECALL_LAYER_QUOTAS = {
    "exact": 25,
    "relaxed": 10,
    "adjacent": 5,
    "public_recommend": 10,
}
RECALL_LAYER_NAMES = frozenset(RECALL_LAYER_ORDER)
ADJACENT_GENRE_IDS = {
    12: (14, 28, 878),
    14: (12, 16, 27),
    16: (12, 35, 10751),
    18: (36, 80, 10749),
    27: (53, 9648, 18),
    28: (12, 53, 878),
    35: (16, 10749, 10751),
    36: (18, 37, 99),
    37: (36, 18, 28),
    53: (27, 9648, 80),
    80: (18, 53, 9648),
    99: (18, 36, 10770),
    878: (12, 14, 28, 9648),
    9648: (27, 53, 80, 878),
    10402: (18, 35, 10749),
    10749: (18, 35, 10751),
    10751: (16, 35, 10749),
    10752: (28, 36, 18),
    10759: (18, 28, 10765),
    10762: (16, 10751, 35),
    10763: (99, 10764, 10766),
    10764: (99, 10763, 10766),
    10765: (14, 878, 9648),
    10766: (18, 10759, 10765),
    10767: (10759, 10765, 16),
    10768: (36, 10752, 18),
    10770: (35, 18, 10751),
}
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
    "anilist_public": {
        "provider": "anilist",
        "mode": "recommend",
        "params": frozenset({"page"}),
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
    layer: str = "exact"

    def __post_init__(self) -> None:
        """校验方法契约、媒体类型、配额和参数键值。"""
        request_id = str(self.request_id or "").strip()
        source = str(self.source or "").strip()
        if not re.fullmatch(r"[a-z0-9:_-]{1,96}", request_id):
            raise ValueError("provider request_id is invalid")
        if not re.fullmatch(r"[a-z0-9:_-]{1,64}", source):
            raise ValueError("provider source is invalid")
        layer = str(self.layer or "").strip()
        if layer not in RECALL_LAYER_NAMES:
            raise ValueError("provider recall layer is invalid")
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
        object.__setattr__(self, "layer", layer)
        object.__setattr__(self, "params", MappingProxyType(params))

    def _validate_params(self, params: Dict[str, Any]) -> None:
        """按 MoviePilot chain 签名校验白名单参数值。"""
        if self.method == "douban_public":
            page = params["page"]
            if (
                self.media_type != "mixed"
                or isinstance(page, bool)
                or not isinstance(page, int)
                or not 1 <= page <= 10
            ):
                raise ValueError("douban public page is invalid")
            return
        if self.method == "bangumi_discover":
            if (
                self.media_type != "anime"
                or params["type"] != 2
                or params["cat"] is not None
                or params["sort"] != "rank"
            ):
                raise ValueError("bangumi discovery params are invalid")
            offset = params["offset"]
            if (
                isinstance(offset, bool)
                or not isinstance(offset, int)
                or not 0 <= offset <= 1500
            ):
                raise ValueError("bangumi discovery offset is invalid")
            year = params["year"]
            if year is not None and (
                isinstance(year, bool)
                or not isinstance(year, int)
                or not 1870 <= year <= 2100
            ):
                raise ValueError("bangumi year is invalid")
            return
        if self.method == "anilist_public":
            page = params["page"]
            if (
                self.media_type != "anime"
                or isinstance(page, bool)
                or not isinstance(page, int)
                or not 1 <= page <= 10
            ):
                raise ValueError("anilist public page is invalid")
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
        page = params["page"]
        if (
            isinstance(page, bool)
            or not isinstance(page, int)
            or not 1 <= page <= 10
        ):
            raise ValueError("tmdb discovery page is invalid")

    def recipe(self) -> Dict[str, Any]:
        """返回不含秘密、可写入运行历史的请求配方。"""
        return {
            "request_id": self.request_id,
            "source": self.source,
            "provider": self.provider,
            "mode": self.mode,
            "method": self.method,
            "media_type": self.media_type,
            "layer": self.layer,
            "limit": self.limit,
            "params": dict(self.params),
        }


@dataclass
class RawDiscoveredItem:
    """表示带受信来源标签的原始发现条目。"""

    source: str
    payload: Any
    mediaid_prefix: str = ""
    layer: str = "exact"


@dataclass
class DiscoveryFetchResult:
    """表示多来源读取结果、请求配方与独立失败证据。"""

    items: List[RawDiscoveredItem] = field(default_factory=list)
    source_errors: Dict[str, str] = field(default_factory=dict)
    rejected_sources: List[str] = field(default_factory=list)
    source_counts: Dict[str, int] = field(default_factory=dict)
    request_recipes: List[Dict[str, Any]] = field(default_factory=list)
    raw_limit: int = DEFAULT_RAW_FETCH_LIMIT
    layer_counts: Dict[str, int] = field(default_factory=dict)


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
        page = int(request.params["page"])
        rows = list(chain.movie_hot(page=page, count=each_count) or [])
        rows.extend(chain.tv_hot(page=page, count=each_count) or [])
        rows.extend(chain.tv_animation(page=page, count=each_count) or [])
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
    def _anilist_public(request: ProviderRequest) -> List[Any]:
        """读取 MoviePilot 内置 AniList 趋势榜与本季热门榜。"""
        from app.chain.anilist import AniListChain

        chain = AniListChain()
        each_count = max(1, (request.limit + 1) // 2)
        page = int(request.params["page"])
        rows = list(chain.trending(page=page, count=each_count) or [])
        rows.extend(
            chain.popular_this_season(page=page, count=each_count) or []
        )
        return rows[: request.limit]

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
                "anilist_public": self._anilist_public,
                "tmdb_recommend": self._tmdb_recommend,
            }[request.method]
        return list(handler(request) or [])[: request.limit]


class DiscoveryAdapter:
    """编排 MoviePilot Provider 请求并隔离来源级故障。"""

    DEFAULT_SOURCE_ORDER = (
        "douban",
        "tmdb_movies",
        "tmdb_tv",
        "bangumi",
        "anilist",
    )

    @staticmethod
    def source_options() -> List[Dict[str, Any]]:
        """返回当前插件支持且由宿主能力探测确认的发现来源。"""
        options = [
            {
                "key": "douban",
                "title": "豆瓣发现",
                "subtitle": "热门电影、剧集与动画",
                "icon": "mdi-alpha-d-circle-outline",
                "available": True,
            },
            {
                "key": "tmdb_movies",
                "title": "TMDB电影",
                "subtitle": "高热度电影候选",
                "icon": "mdi-movie-open-star-outline",
                "available": True,
            },
            {
                "key": "tmdb_tv",
                "title": "TMDB剧集",
                "subtitle": "高热度剧集候选",
                "icon": "mdi-television-classic",
                "available": True,
            },
            {
                "key": "bangumi",
                "title": "Bangumi",
                "subtitle": "动画与番剧候选",
                "icon": "mdi-animation-outline",
                "available": True,
            },
        ]
        try:
            from app.chain.anilist import AniListChain

            available = all(
                callable(getattr(AniListChain, name, None))
                for name in ("trending", "popular_this_season")
            )
        except (ImportError, AttributeError):
            available = False
        options.append(
            {
                "key": "anilist",
                "title": "AniList",
                "subtitle": "趋势动画与本季热门",
                "icon": "mdi-alpha-a-circle-outline",
                "available": available,
            }
        )
        return options

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

    @staticmethod
    def _relaxed_tmdb_params(params: Mapping[str, Any]) -> Dict[str, Any]:
        """构造放宽探索参数，移除高约束条件但保留媒体类型与语言。"""
        relaxed = dict(params)
        relaxed.update(
            {
                "with_genres": "",
                "with_keywords": "",
                "vote_average": 0.0,
                "vote_count": 0,
                "release_date": "",
            }
        )
        return relaxed

    @staticmethod
    def _adjacent_genres(genre_ids: Iterable[int]) -> List[int]:
        """按固定白名单将画像题材映射为相邻题材。"""
        selected = {int(item) for item in genre_ids or ()}
        result: List[int] = []
        for genre_id in sorted(selected):
            for adjacent in ADJACENT_GENRE_IDS.get(genre_id, ()):
                if adjacent not in selected and adjacent not in result:
                    result.append(adjacent)
        return result[:20]

    def _layer_tmdb_params(
        self, plan: Optional[RetrievalPlan], layer: str
    ) -> Optional[Dict[str, Any]]:
        """按召回层生成受控 TMDB 参数；无相邻题材时跳过该层。"""
        params = self._tmdb_params(plan)
        if layer == "exact":
            return params
        if layer == "relaxed":
            return self._relaxed_tmdb_params(params)
        if layer == "adjacent":
            filters = plan.filters if isinstance(plan, RetrievalPlan) else None
            adjacent = self._adjacent_genres(filters.genre_ids if filters else ())
            if not adjacent:
                return None
            params = self._relaxed_tmdb_params(params)
            params["with_genres"] = "|".join(str(item) for item in adjacent)
            return params
        raise ValueError("unsupported discovery layer")

    def _default_requests(
        self,
        enabled_sources: Mapping[str, Any],
        plan: Optional[RetrievalPlan],
        raw_limit: int,
        layer: str = "exact",
        request_suffix: str = "",
        page: int = 1,
    ) -> List[ProviderRequest]:
        """构造指定召回层的公共探索请求。"""
        filters = plan.filters if isinstance(plan, RetrievalPlan) else None
        media_types = set(filters.media_types if filters else ())
        tmdb_params = self._layer_tmdb_params(plan, layer)
        if layer != "exact" and tmdb_params is None:
            return []
        source_order = self.DEFAULT_SOURCE_ORDER
        if layer in {"relaxed", "adjacent"}:
            source_order = ("tmdb_movies", "tmdb_tv")
        enabled_names = [
            name
            for name in source_order
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
                or (
                    name == "anilist"
                    and media_types
                    and not media_types.intersection({"tv", "anime"})
                )
            )
        ]
        quotas = self._quotas(enabled_names, raw_limit)
        requests: List[ProviderRequest] = []
        for name, limit in quotas.items():
            request_id = (
                name
                if layer == "exact" and not request_suffix
                else f"{layer}:{name}{request_suffix}"
            )
            if name == "douban":
                requests.append(
                    ProviderRequest(
                        request_id=request_id,
                        source=name,
                        provider="douban",
                        mode="discover",
                        method="douban_public",
                        media_type="mixed",
                        limit=limit,
                        params={"page": page},
                        layer=layer,
                    )
                )
            elif name in {"tmdb_movies", "tmdb_tv"}:
                requests.append(
                    ProviderRequest(
                        request_id=request_id,
                        source=name,
                        provider="tmdb",
                        mode="discover",
                        method="tmdb_discover",
                        media_type="movie" if name == "tmdb_movies" else "tv",
                        limit=limit,
                        params={**tmdb_params, "page": page},
                        layer=layer,
                    )
                )
            elif name == "bangumi":
                requests.append(
                    ProviderRequest(
                        request_id=request_id,
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
                            "offset": 0 if page == 1 else (page - 1) * limit,
                        },
                        layer=layer,
                    )
                )
            else:
                requests.append(
                    ProviderRequest(
                        request_id=request_id,
                        source=name,
                        provider="anilist",
                        mode="recommend",
                        method="anilist_public",
                        media_type="anime",
                        limit=limit,
                        params={"page": page},
                        layer=layer,
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
        self,
        enabled_sources: Mapping[str, Any],
        raw_limit: int,
        layer: str = "exact",
        source_names: Optional[Sequence[str]] = None,
        request_suffix: str = "",
    ) -> DiscoveryFetchResult:
        """为已有单参数 fetcher 提供分层来源隔离与 recipe 证据。"""
        result = DiscoveryFetchResult(raw_limit=raw_limit)
        allowed = set(source_names) if source_names is not None else None
        enabled_names = [
            name
            for name in self._source_fetchers or {}
            if enabled_sources.get(name, False)
            and (allowed is None or name in allowed)
        ]
        for source, limit in self._quotas(enabled_names, raw_limit).items():
            request_id = (
                source
                if layer == "exact" and not request_suffix
                else f"{layer}:{source}{request_suffix}"
            )
            recipe = {
                "request_id": request_id,
                "source": source,
                "provider": "injected",
                "mode": "discover",
                "method": "test_fetcher",
                "media_type": "mixed",
                "layer": layer,
                "limit": limit,
                "params": {},
            }
            result.request_recipes.append(recipe)
            try:
                rows = self._invoke_legacy(self._source_fetchers[source], limit)
            except Exception as error:
                result.source_errors[request_id] = str(error)
                continue
            result.source_counts[source] = len(rows)
            result.items.extend(
                RawDiscoveredItem(source=source, payload=row, layer=layer)
                for row in rows
            )
            result.layer_counts[layer] = result.layer_counts.get(layer, 0) + len(rows)
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
                RawDiscoveredItem(
                    source=effective.source, payload=row, layer=effective.layer
                )
                for row in rows
            )
            result.layer_counts[effective.layer] = (
                result.layer_counts.get(effective.layer, 0) + len(rows)
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
            return self._fetch_legacy(enabled_sources, limit, layer="exact")
        requests = self._default_requests(
            enabled_sources, retrieval_plan, limit, layer="exact"
        )
        return self.fetch_requests(requests, raw_limit=limit)

    def fetch_recommendations(
        self,
        playback_samples: Iterable[Mapping[str, Any]],
        raw_limit: Optional[int] = None,
        layer: str = "public_recommend",
        request_suffix: str = "",
    ) -> DiscoveryFetchResult:
        """按类型化 TMDB 播放种子执行指定层的公共推荐 Provider。"""
        limit = max(
            1,
            min(
                int(raw_limit or self._raw_fetch_limit),
                DEFAULT_RAW_FETCH_LIMIT,
            ),
        )
        seeds: List[tuple[str, int]] = []
        for sample in playback_samples or ():
            if not isinstance(sample, Mapping) and hasattr(sample, "to_dict"):
                sample = sample.to_dict()
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
                request_id=f"tmdb_recommend:{media_type}:{tmdbid}{request_suffix}",
                source="tmdb_recommend",
                provider="tmdb",
                mode="recommend",
                method="tmdb_recommend",
                media_type=media_type,
                limit=quotas[f"{media_type}:{tmdbid}"],
                params={"tmdbid": tmdbid},
                layer=layer,
            )
            for media_type, tmdbid in seeds
            if f"{media_type}:{tmdbid}" in quotas
        ]
        return self.fetch_requests(requests, raw_limit=limit)

    @staticmethod
    def _scaled_layer_quotas(target: int) -> Dict[str, int]:
        """将默认 25/10/5/10 配额按目标池大小做最大余数缩放。"""
        target = max(0, int(target))
        total = sum(DEFAULT_RECALL_LAYER_QUOTAS.values())
        if not target or not total:
            return {name: 0 for name in RECALL_LAYER_ORDER}
        base = {
            name: target * quota // total
            for name, quota in DEFAULT_RECALL_LAYER_QUOTAS.items()
        }
        remainder = target - sum(base.values())
        ranked = sorted(
            RECALL_LAYER_ORDER,
            key=lambda name: (
                -(target * DEFAULT_RECALL_LAYER_QUOTAS[name] % total),
                RECALL_LAYER_ORDER.index(name),
            ),
        )
        for name in ranked[:remainder]:
            base[name] += 1
        return base

    @staticmethod
    def _merge_fetch_result(
        target: DiscoveryFetchResult,
        incoming: DiscoveryFetchResult,
        recall_pass: str,
    ) -> None:
        """合并一次召回结果并标注初始或补足轮次。"""
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
            marked["recall_pass"] = recall_pass
            target.request_recipes.append(marked)

    def _run_recall_layer(
        self,
        layer: str,
        enabled_sources: Mapping[str, Any],
        plan: Optional[RetrievalPlan],
        playback_samples: Iterable[Mapping[str, Any]],
        limit: int,
        fallback: bool,
    ) -> DiscoveryFetchResult:
        """执行一层召回并保持同一来源与参数边界。"""
        suffix = ":fallback" if fallback else ""
        if layer == "public_recommend":
            allowed_samples = []
            for sample in playback_samples or ():
                value = sample.to_dict() if hasattr(sample, "to_dict") else sample
                if not isinstance(value, Mapping):
                    continue
                media_type = str(value.get("media_type") or "")
                if (
                    (media_type == "movie" and enabled_sources.get("tmdb_movies", False))
                    or (media_type == "tv" and enabled_sources.get("tmdb_tv", False))
                ):
                    allowed_samples.append(value)
            return self.fetch_recommendations(
                allowed_samples,
                raw_limit=limit,
                layer=layer,
                request_suffix=suffix,
            )
        source_names = None
        if layer in {"relaxed", "adjacent"}:
            source_names = ("tmdb_movies", "tmdb_tv")
        if self._source_fetchers is not None:
            return self._fetch_legacy(
                enabled_sources,
                limit,
                layer=layer,
                source_names=source_names,
                request_suffix=suffix,
            )
        requests = self._default_requests(
            enabled_sources,
            plan,
            limit,
            layer=layer,
            request_suffix=suffix,
            page=2 if fallback else 1,
        )
        return self.fetch_requests(requests, raw_limit=limit)

    def fetch_layered(
        self,
        enabled_sources: Mapping[str, Any],
        candidate_limit: int,
        retrieval_plan: Optional[RetrievalPlan] = None,
        playback_samples: Iterable[Mapping[str, Any]] = (),
        raw_limit: Optional[int] = None,
    ) -> DiscoveryFetchResult:
        """按四层配额召回候选，并在短缺时从有效层补足。"""
        if not isinstance(enabled_sources, Mapping):
            return DiscoveryFetchResult(raw_limit=self._raw_fetch_limit)
        playback_samples = list(playback_samples or ())
        limit = max(
            1,
            min(int(raw_limit or self._raw_fetch_limit), DEFAULT_RAW_FETCH_LIMIT),
        )
        target = min(max(1, int(candidate_limit)), limit)
        quotas = self._scaled_layer_quotas(target)
        result = DiscoveryFetchResult(raw_limit=limit)
        valid_layers: List[str] = []
        initial_budgets: Dict[str, int] = {}
        consumed = 0
        for layer in RECALL_LAYER_ORDER:
            budget = min(quotas.get(layer, 0), max(0, limit - consumed))
            if budget <= 0:
                continue
            incoming = self._run_recall_layer(
                layer,
                enabled_sources,
                retrieval_plan,
                playback_samples,
                budget,
                fallback=False,
            )
            if not incoming.request_recipes:
                continue
            valid_layers.append(layer)
            initial_budgets[layer] = budget
            self._merge_fetch_result(result, incoming, "initial")
            consumed += sum(int(item.get("limit") or 0) for item in incoming.request_recipes)
        shortfall = max(0, target - len(result.items))
        if shortfall and valid_layers and consumed < limit:
            full_layers = [
                layer
                for layer in valid_layers
                if result.layer_counts.get(layer, 0) >= initial_budgets[layer]
            ]
            eligible = full_layers or valid_layers
            extra = min(shortfall, limit - consumed)
            for layer, budget in self._quotas(eligible, extra).items():
                incoming = self._run_recall_layer(
                    layer,
                    enabled_sources,
                    retrieval_plan,
                    playback_samples,
                    budget,
                    fallback=True,
                )
                self._merge_fetch_result(result, incoming, "fallback")
                consumed += sum(
                    int(item.get("limit") or 0) for item in incoming.request_recipes
                )
        return result
