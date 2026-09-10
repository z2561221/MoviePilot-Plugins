"""MoviePilot V3 全局订阅读取适配器。"""

from typing import Any, Callable, List, Mapping, Set

from app.schemas.types import MediaSource, MediaType

from ..model.candidate import typed_tmdb_candidate_id


class SubscriptionAdapter:
    """跨全部用户名读取订阅，并统一转换为 AgentRank 的 TMDB 候选身份。"""

    def __init__(
        self,
        oper: Any = None,
        chain_factory: Callable[[], Any] = None,
        query_api: Any = None,
    ):
        """允许测试注入旧读取器、查询门面与媒体身份转换链。"""
        self._oper = oper
        self._chain_factory = chain_factory
        self._query_api = query_api

    @staticmethod
    def _field(record: Any, name: str) -> Any:
        """兼容 ORM 对象与字典读取订阅字段。"""
        if isinstance(record, dict):
            return record.get(name)
        return getattr(record, name, None)

    def _chain(self) -> Any:
        """延迟创建 V3 媒体链，避免只读 TMDB 订阅时加载额外能力。"""
        if self._chain_factory is not None:
            return self._chain_factory()
        from app.chain.media import MediaChain

        return MediaChain()

    def list_all(self) -> List[Any]:
        """读取 MoviePilot 当前全部订阅，不按用户名划分范围。"""
        if self._oper is not None:
            return list(self._oper.list() or [])
        from app.sdk import queries

        query_api = self._query_api if self._query_api is not None else queries
        page_number = 1
        records: list[Any] = []
        while True:
            page = query_api.list_subscriptions(
                filters={"media_types": (MediaType.MOVIE, MediaType.TV)},
                page=queries.QueryPageRequest(
                    page=page_number,
                    count=queries.MAX_QUERY_PAGE_SIZE,
                    sort=queries.QuerySort(
                        field=queries.QuerySortField.ID,
                        direction=queries.QuerySortDirection.ASC,
                    ),
                ),
            )
            records.extend(page.items)
            if not page.has_next or not page.items:
                return records
            page_number += 1

    @staticmethod
    def _is_music_media_type(value: Any) -> bool:
        """判断音乐订阅；音乐不参与影视榜单的 TMDB 去重。"""
        if value == getattr(MediaType, "MUSIC", object()):
            return True
        raw = str(getattr(value, "value", value) or "").strip().casefold()
        return raw in {"music", "音乐"}

    @staticmethod
    def _normalize_media_type(value: Any) -> MediaType:
        """把订阅中的字符串媒体类型转换为 MoviePilot MediaType。"""
        if isinstance(value, MediaType):
            return value
        raw = str(getattr(value, "value", value) or "").strip().casefold()
        if raw in {"movie", "电影"}:
            return MediaType.MOVIE
        if raw in {"tv", "电视剧", "剧集", "电视"} or raw.startswith("tv"):
            return MediaType.TV
        raise ValueError("subscription media type is unsupported")

    @staticmethod
    def _mapping_tmdb_id(value: Any) -> str:
        """从统一身份转换结果提取 TMDB 原生 ID。"""
        if not isinstance(value, Mapping):
            return ""
        source = str(value.get("media_source") or "").strip()
        if source in {str(MediaSource.TMDB), "tmdb"}:
            media_id = str(value.get("media_id") or "").strip()
            if media_id.isdigit() and int(media_id) > 0:
                return str(int(media_id))
        for name in ("tmdb_id", "tmdbid", "id"):
            media_id = str(value.get(name) or "").strip()
            if media_id.isdigit() and int(media_id) > 0:
                return str(int(media_id))
        return ""

    def _tmdb_id(self, record: Any, media_type: Any) -> str:
        """把一条 V3 订阅的主身份转换为 TMDB ID。"""
        source_text = str(self._field(record, "media_source") or "").strip()
        media_id = str(self._field(record, "media_id") or "").strip()
        if not source_text or not media_id or media_id == "0":
            return ""
        try:
            source = MediaSource(source_text)
        except ValueError as error:
            raise RuntimeError("subscription media source is unsupported") from error
        if source == MediaSource.TMDB:
            return str(int(media_id)) if media_id.isdigit() and int(media_id) > 0 else ""
        normalized_media_type = self._normalize_media_type(media_type)
        try:
            mapping = self._chain().convert_media_identity(
                target_source=MediaSource.TMDB,
                media_source=source,
                media_id=media_id,
                mtype=normalized_media_type,
            )
        except Exception as error:
            raise RuntimeError("subscription identity conversion unavailable") from error
        tmdb_id = self._mapping_tmdb_id(mapping)
        if not tmdb_id:
            raise RuntimeError("subscription identity conversion unavailable")
        return tmdb_id

    def candidate_ids(self) -> Set[str]:
        """返回全部订阅对应的类型化 TMDB 候选身份。"""
        result: Set[str] = set()
        for record in self.list_all():
            media_type = self._field(record, "type") or self._field(
                record, "media_type"
            )
            if self._is_music_media_type(media_type):
                continue
            tmdb_id = self._tmdb_id(record, media_type)
            if not tmdb_id:
                continue
            result.add(typed_tmdb_candidate_id(tmdb_id, media_type))
        return result
