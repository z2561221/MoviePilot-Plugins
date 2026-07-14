"""MoviePilot 内置发现源适配器。"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping


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
    """封装当前 MoviePilot 内置发现链。"""

    def __init__(
        self,
        source_fetchers: Dict[str, Callable[[int], List[Any]]] = None,
    ):
        """允许测试注入来源；运行时使用当前 core 的实现。"""
        self._source_fetchers = (
            dict(source_fetchers)
            if source_fetchers is not None
            else self._default_source_fetchers()
        )

    @staticmethod
    def _default_source_fetchers() -> Dict[str, Callable[[int], List[Any]]]:
        """返回四个内置发现读取函数。"""
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
        return result
