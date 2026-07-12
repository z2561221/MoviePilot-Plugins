"""MoviePilot 媒体识别与 TMDB 标准化适配器。"""

from typing import Any, Callable, Optional

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
        candidate.metadata["recognized_by"] = "moviepilot"
        return candidate
