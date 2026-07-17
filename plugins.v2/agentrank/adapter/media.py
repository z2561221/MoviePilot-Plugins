"""MoviePilot 媒体识别与 TMDB 标准化适配器。"""

from typing import Any, Callable, Iterable, List, Mapping, Optional

from ..model.candidate import Candidate


class MediaRecognitionAdapter:
    """通过 MoviePilot MediaChain 将来源候选转换为 TMDB 标准条目。"""

    def __init__(
        self,
        chain_factory: Callable[[], Any] = None,
        meta_factory: Callable[[str], Any] = None,
        media_type_cls: Any = None,
    ):
        """允许测试注入宿主依赖，运行时按需加载 MoviePilot 实现。"""
        self._chain_factory = chain_factory
        self._meta_factory = meta_factory
        self._media_type_cls = media_type_cls

    def _dependencies(self) -> tuple[Callable[[], Any], Callable[[str], Any], Any]:
        """返回延迟加载后的媒体识别依赖。"""
        if self._chain_factory and self._meta_factory and self._media_type_cls:
            return self._chain_factory, self._meta_factory, self._media_type_cls
        from app.chain.media import MediaChain
        from app.core.metainfo import MetaInfo
        from app.schemas.types import MediaType

        return (
            self._chain_factory or MediaChain,
            self._meta_factory or MetaInfo,
            self._media_type_cls or MediaType,
        )

    @staticmethod
    def _poster_path(mediainfo: Any) -> str:
        """从识别结果中提取可显示海报。"""
        poster = str(getattr(mediainfo, "poster_path", "") or "")
        if not poster and hasattr(mediainfo, "get_poster_image"):
            poster = str(mediainfo.get_poster_image() or "")
        return poster

    @staticmethod
    def _media_type(candidate: Candidate, media_type_cls: Any) -> Any:
        """把候选类型转换为 MoviePilot 媒体类型。"""
        if candidate.media_type == "movie":
            return media_type_cls.MOVIE
        return media_type_cls.TV

    @staticmethod
    def _strings(value: Any) -> List[str]:
        """把 MoviePilot 的字典、对象或字符串列表规范化为名称列表。"""
        if value is None:
            return []
        items: Iterable[Any] = value if isinstance(value, (list, tuple, set)) else [value]
        result: List[str] = []
        for item in items:
            if isinstance(item, Mapping):
                item = item.get("name") or item.get("title")
            elif not isinstance(item, str):
                item = getattr(item, "name", None) or getattr(item, "title", None)
            text = str(item or "").strip()
            if text and text not in result:
                result.append(text)
        return result

    @staticmethod
    def _merge_unique(current: List[str], incoming: Iterable[str]) -> List[str]:
        """合并识别特征并保持稳定顺序。"""
        result = list(current or [])
        for item in incoming:
            if item and item not in result:
                result.append(item)
        return result

    @staticmethod
    def _moviepilot_type(mediainfo: Any, requested_type: Any, media_type_cls: Any) -> str:
        """把识别结果类型收敛为媒体库实际保存的中文基础类型。"""
        resolved = getattr(mediainfo, "type", None) or requested_type
        if resolved == media_type_cls.MOVIE:
            return "电影"
        raw = str(getattr(resolved, "value", resolved) or "").strip().lower()
        if raw in {"电影", "movie"} or "movie" in raw:
            return "电影"
        return "电视剧"

    @classmethod
    def _display_type(
        cls, mediainfo: Any, moviepilot_type: str, genres: List[str]
    ) -> str:
        """按实际基础类型与动画特征生成榜单展示类型。"""
        category = str(getattr(mediainfo, "category", "") or "").strip()
        genre_ids = {
            str(item).strip()
            for item in (getattr(mediainfo, "genre_ids", None) or [])
            if str(item).strip()
        }
        animation_text = " ".join([category, *genres]).lower()
        if "16" in genre_ids or any(
            token in animation_text for token in ("animation", "anime", "动画", "动漫")
        ):
            return "anime"
        return "movie" if moviepilot_type == "电影" else "tv"

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        """读取 MoviePilot 可选数值字段。"""
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    def recognize(self, candidate: Candidate) -> Optional[Candidate]:
        """识别候选并仅在获得 TMDB 身份时返回标准条目。"""
        chain_factory, meta_factory, media_type_cls = self._dependencies()
        media_type = self._media_type(candidate, media_type_cls)
        meta = meta_factory(candidate.title)
        if candidate.year:
            meta.year = str(candidate.year)
        meta.type = media_type
        chain = chain_factory()
        mediainfo = None
        tmdb_id = candidate.source_ids.get("tmdb")
        if tmdb_id:
            try:
                mediainfo = chain.recognize_media(
                    meta=meta, mtype=media_type, tmdbid=tmdb_id
                )
            except TypeError:
                mediainfo = None
        if not mediainfo:
            mediainfo = chain.recognize_media(meta=meta, mtype=media_type)
        if not mediainfo and candidate.source_ids.get("bangumi"):
            try:
                mediainfo = chain.recognize_media(
                    meta=meta,
                    mtype=media_type,
                    bangumiid=candidate.source_ids["bangumi"],
                )
            except TypeError:
                mediainfo = None
        resolved_tmdb_id = getattr(mediainfo, "tmdb_id", None) if mediainfo else None
        if not resolved_tmdb_id:
            return None

        candidate.source_ids["tmdb"] = str(resolved_tmdb_id)
        candidate.candidate_id = f"tmdb:{resolved_tmdb_id}"
        candidate.title = str(getattr(mediainfo, "title", "") or candidate.title)
        resolved_year = getattr(mediainfo, "year", None)
        try:
            candidate.year = int(resolved_year) if resolved_year else candidate.year
        except (TypeError, ValueError):
            pass
        candidate.original_title = str(
            getattr(mediainfo, "original_title", "") or candidate.original_title
        )
        candidate.overview = str(
            getattr(mediainfo, "overview", "") or candidate.overview
        )
        candidate.poster_path = self._poster_path(mediainfo) or candidate.poster_path
        candidate.backdrop_path = str(
            getattr(mediainfo, "backdrop_path", "") or candidate.backdrop_path
        )
        genres = self._strings(getattr(mediainfo, "genres", None))
        candidate.genres = self._merge_unique(candidate.genres, genres)
        regions = self._strings(
            getattr(mediainfo, "regions", None)
            or getattr(mediainfo, "countries", None)
            or getattr(mediainfo, "origin_country", None)
        )
        candidate.regions = self._merge_unique(candidate.regions, regions)
        candidate.actors = self._merge_unique(
            candidate.actors, self._strings(getattr(mediainfo, "actors", None))
        )
        candidate.directors = self._merge_unique(
            candidate.directors, self._strings(getattr(mediainfo, "directors", None))
        )
        rating = self._number(
            getattr(mediainfo, "vote_average", None)
            or getattr(mediainfo, "rating", None)
        )
        popularity = self._number(getattr(mediainfo, "popularity", None))
        if rating is not None:
            candidate.rating = rating
        if popularity is not None:
            candidate.popularity = popularity
        release_date = str(
            getattr(mediainfo, "release_date", "")
            or getattr(mediainfo, "first_air_date", "")
        )
        if release_date:
            candidate.release_date = release_date
        moviepilot_type = self._moviepilot_type(mediainfo, media_type, media_type_cls)
        candidate.metadata["mp_media_type"] = moviepilot_type
        category = str(getattr(mediainfo, "category", "") or "").strip()
        if category:
            candidate.metadata["category"] = category
        genre_ids = list(getattr(mediainfo, "genre_ids", None) or [])
        if genre_ids:
            candidate.metadata["genre_ids"] = genre_ids
        candidate.media_type = self._display_type(
            mediainfo, moviepilot_type, candidate.genres
        )
        candidate.metadata["recognized_by"] = "moviepilot"
        return candidate
