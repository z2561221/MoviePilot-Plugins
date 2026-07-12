"""MoviePilot 内置与扩展发现源适配器。"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping
from urllib.parse import urlencode


@dataclass
class RawDiscoveredItem:
    """表示带受信来源标签的原始发现条目。"""

    source: str
    payload: Any
    mediaid_prefix: str = ""


@dataclass
class DiscoveryFetchResult:
    """表示多来源读取结果及独立失败证据。"""

    items: List[RawDiscoveredItem] = field(default_factory=list)
    source_errors: Dict[str, str] = field(default_factory=dict)
    rejected_sources: List[str] = field(default_factory=list)


class DiscoveryAdapter:
    """封装当前 MoviePilot chain 与 DiscoverSource 扩展契约。"""

    def __init__(
        self,
        source_fetchers: Dict[str, Callable[[int], List[Any]]] = None,
        extension_sources_provider: Callable[[], List[Any]] = None,
        extension_fetcher: Callable[[Mapping[str, Any], int], List[Any]] = None,
    ):
        """允许测试注入来源；运行时使用当前 core 的实现。"""
        self._source_fetchers = (
            dict(source_fetchers)
            if source_fetchers is not None
            else self._default_source_fetchers()
        )
        self._extension_sources_provider = (
            extension_sources_provider or self._default_extension_sources
        )
        self._extension_fetcher = extension_fetcher or self._default_extension_fetch

    @staticmethod
    def _default_source_fetchers() -> Dict[str, Callable[[int], List[Any]]]:
        """返回五类配置中的四个内置发现读取函数。"""
        return {
            "douban": DiscoveryAdapter._fetch_douban,
            "tmdb_movies": DiscoveryAdapter._fetch_tmdb_movies,
            "tmdb_tv": DiscoveryAdapter._fetch_tmdb_tv,
            "bangumi": DiscoveryAdapter._fetch_bangumi,
        }

    @staticmethod
    def _fetch_douban(count: int) -> List[Any]:
        """通过 DoubanChain 读取热门电影、剧集和动画。"""
        from app.chain.douban import DoubanChain

        chain = DoubanChain()
        each_count = max(1, int(count) // 3)
        return list(chain.movie_hot(count=each_count) or []) + list(
            chain.tv_hot(count=each_count) or []
        ) + list(chain.tv_animation(count=each_count) or [])

    @staticmethod
    def _fetch_tmdb_movies(count: int) -> List[Any]:
        """通过 TmdbChain 读取高热度电影。"""
        from app.chain.tmdb import TmdbChain
        from app.schemas.types import MediaType

        return list(
            TmdbChain().tmdb_discover(
                mtype=MediaType.MOVIE,
                sort_by="popularity.desc",
                with_genres="",
                with_original_language="",
                with_keywords="",
                with_watch_providers="",
                vote_average=0.0,
                vote_count=0,
                release_date="",
                page=1,
            )
            or []
        )[: max(1, int(count))]

    @staticmethod
    def _fetch_tmdb_tv(count: int) -> List[Any]:
        """通过 TmdbChain 读取高热度剧集。"""
        from app.chain.tmdb import TmdbChain
        from app.schemas.types import MediaType

        return list(
            TmdbChain().tmdb_discover(
                mtype=MediaType.TV,
                sort_by="popularity.desc",
                with_genres="",
                with_original_language="",
                with_keywords="",
                with_watch_providers="",
                vote_average=0.0,
                vote_count=0,
                release_date="",
                page=1,
            )
            or []
        )[: max(1, int(count))]

    @staticmethod
    def _fetch_bangumi(count: int) -> List[Any]:
        """通过 BangumiChain 读取高排名动画。"""
        from app.chain.bangumi import BangumiChain

        return list(
            BangumiChain().discover(
                type=2,
                cat=None,
                sort="rank",
                year=None,
                limit=max(1, int(count)),
                offset=0,
            )
            or []
        )

    @staticmethod
    def _object_mapping(value: Any) -> Dict[str, Any]:
        """将 Pydantic、字典或普通描述对象转换为独立字典。"""
        if isinstance(value, Mapping):
            return dict(value)
        if hasattr(value, "model_dump"):
            return dict(value.model_dump())
        return {
            name: getattr(value, name)
            for name in ("name", "mediaid_prefix", "api_path")
            if hasattr(value, name)
        }

    @staticmethod
    def _default_extension_sources() -> List[Any]:
        """广播 DiscoverSource 事件并返回扩展源描述。"""
        from app.core.event import eventmanager
        from app.schemas import DiscoverSourceEventData
        from app.schemas.types import ChainEventType

        event_data = DiscoverSourceEventData()
        event = eventmanager.send_event(ChainEventType.DiscoverSource, event_data)
        if event and event.event_data:
            event_data = event.event_data
        return list(getattr(event_data, "extra_sources", None) or [])

    @staticmethod
    def _safe_api_path(value: Any) -> bool:
        """仅允许 MoviePilot 内部相对 API 路径。"""
        path = str(value or "").strip()
        lowered = path.lower()
        return bool(path) and not (
            "://" in lowered
            or path.startswith(("//", "\\", "/../"))
            or ".." in path.replace("\\", "/").split("/")
        )

    @staticmethod
    def _default_extension_fetch(source: Mapping[str, Any], count: int) -> List[Any]:
        """通过宿主本地鉴权 API 读取一个已验证的扩展发现源。"""
        from app.core.config import settings
        from app.utils.http import RequestUtils

        api_path = str(source.get("api_path") or "").lstrip("/")
        if not api_path.startswith("api/v1/"):
            api_path = f"api/v1/{api_path}"
        query = urlencode({"token": settings.API_TOKEN, "count": max(1, int(count))})
        response = RequestUtils(timeout=15).get_res(
            f"http://127.0.0.1:{settings.PORT}/{api_path}?{query}"
        )
        if not response:
            return []
        payload = response.json()
        return list(payload) if isinstance(payload, list) else []

    def fetch(self, enabled_sources: Mapping[str, Any], count: int) -> DiscoveryFetchResult:
        """逐来源读取，隔离失败并给每条数据附加受信来源。"""
        result = DiscoveryFetchResult()
        per_source_count = max(1, int(count))
        for source_name, fetcher in self._source_fetchers.items():
            if not enabled_sources.get(source_name, False):
                continue
            try:
                rows = fetcher(per_source_count) or []
            except Exception as error:
                result.source_errors[source_name] = str(error)
                continue
            result.items.extend(
                RawDiscoveredItem(source=source_name, payload=row) for row in rows
            )
        if enabled_sources.get("extensions", False):
            try:
                descriptors = self._extension_sources_provider() or []
            except Exception as error:
                result.source_errors["extensions"] = str(error)
                descriptors = []
            for raw_source in descriptors:
                source = self._object_mapping(raw_source)
                name = str(source.get("name") or "unnamed extension")
                prefix = str(source.get("mediaid_prefix") or "").strip()
                if not prefix or not self._safe_api_path(source.get("api_path")):
                    result.rejected_sources.append(name)
                    continue
                try:
                    rows = self._extension_fetcher(source, per_source_count) or []
                except Exception as error:
                    result.source_errors[f"extension:{prefix}"] = str(error)
                    continue
                result.items.extend(
                    RawDiscoveredItem(
                        source=f"extension:{prefix}",
                        payload=row,
                        mediaid_prefix=prefix,
                    )
                    for row in rows
                )
        return result
