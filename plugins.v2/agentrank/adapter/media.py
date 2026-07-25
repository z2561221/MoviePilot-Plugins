"""MoviePilot 媒体识别与 TMDB 标准化适配器。"""

from typing import Any, Callable, Iterable, List, Mapping, Optional

from ..model.candidate import Candidate, typed_tmdb_candidate_id


class MediaRecognitionAdapter:
    """通过 MoviePilot MediaChain 将来源候选转换为 TMDB 标准条目。"""

    _DIRECTOR_JOBS = frozenset(
        {
            "director",
            "series director",
            "episode director",
            "co-director",
            "导演",
            "总导演",
        }
    )

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

    @classmethod
    def _director_strings(cls, value: Any) -> List[str]:
        """仅保留 MoviePilot 主创列表中真正承担导演职责的人物。"""
        if value is None:
            return []
        items: Iterable[Any] = value if isinstance(value, (list, tuple, set)) else [value]
        filtered: List[Any] = []
        for item in items:
            if isinstance(item, Mapping):
                job = str(item.get("job") or "").strip().casefold()
                department = str(item.get("department") or "").strip().casefold()
            elif isinstance(item, str):
                job = ""
                department = ""
            else:
                job = str(getattr(item, "job", "") or "").strip().casefold()
                department = str(
                    getattr(item, "department", "") or ""
                ).strip().casefold()
            if job and job not in cls._DIRECTOR_JOBS:
                continue
            if not job and department and department != "directing":
                continue
            filtered.append(item)
        return cls._strings(filtered)

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

    @staticmethod
    def _normalize_source_ids(candidate: Any) -> None:
        """把宿主或旧榜单中的来源 ID 别名收敛为插件内部键。"""
        source_ids = getattr(candidate, "source_ids", None)
        if not isinstance(source_ids, dict):
            return
        aliases = {
            "tmdb": ("tmdb_id", "tmdbid", "themoviedb", "themoviedb_id"),
            "douban": ("douban_id", "doubanid"),
            "bangumi": ("bangumi_id", "bangumiid", "bgm", "bgm_id"),
            "anilist": ("anilist_id", "anilistid"),
        }
        for canonical, names in aliases.items():
            if source_ids.get(canonical) not in (None, ""):
                continue
            for name in names:
                value = source_ids.get(name)
                if value not in (None, ""):
                    source_ids[canonical] = str(value)
                    break

    def recognize(self, candidate: Candidate) -> Optional[Candidate]:
        """识别候选并仅在获得 TMDB 身份时返回标准条目。"""
        self._normalize_source_ids(candidate)
        chain_factory, meta_factory, media_type_cls = self._dependencies()
        media_type = self._media_type(candidate, media_type_cls)
        meta = meta_factory(candidate.title)
        if candidate.year:
            meta.year = str(candidate.year)
        meta.type = media_type
        chain = chain_factory()
        mediainfo = None
        tmdb_id = candidate.source_ids.get("tmdb")
        explicit_kwargs = {}
        if tmdb_id:
            explicit_kwargs = {"tmdbid": tmdb_id}
        elif candidate.source_ids.get("douban"):
            explicit_kwargs = {"doubanid": candidate.source_ids["douban"]}
        elif candidate.source_ids.get("bangumi"):
            explicit_kwargs = {"bangumiid": candidate.source_ids["bangumi"]}
        elif candidate.source_ids.get("anilist"):
            explicit_kwargs = {"anilistid": candidate.source_ids["anilist"]}
        if explicit_kwargs:
            try:
                mediainfo = chain.recognize_media(
                    meta=meta, mtype=media_type, **explicit_kwargs
                )
            except TypeError:
                mediainfo = None
        if not mediainfo:
            mediainfo = chain.recognize_media(meta=meta, mtype=media_type)
        if not mediainfo and candidate.source_ids.get("bangumi") and "bangumiid" not in explicit_kwargs:
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
        self._copy_media_ids(candidate, mediainfo)
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
            candidate.directors,
            self._director_strings(getattr(mediainfo, "directors", None)),
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
        candidate.candidate_id = typed_tmdb_candidate_id(
            resolved_tmdb_id,
            candidate.media_type,
            moviepilot_type,
        )
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

    @staticmethod
    def _copy_media_ids(candidate: Candidate, mediainfo: Any) -> None:
        """从 MoviePilot 识别结果补齐可直达的跨来源媒体 ID。"""
        aliases = {
            "douban": ("douban_id", "doubanid"),
            "bangumi": ("bangumi_id", "bangumiid", "bgm_id", "bgmid"),
            "anilist": ("anilist_id", "anilistid"),
            "imdb": ("imdb_id", "imdbid"),
            "tvdb": ("tvdb_id", "tvdbid"),
        }
        for target, names in aliases.items():
            if candidate.source_ids.get(target):
                continue
            for name in names:
                value = getattr(mediainfo, name, None)
                if value not in (None, ""):
                    candidate.source_ids[target] = str(value)
                    break

    def enrich_cross_source_ids(self, candidate: Any) -> Any:
        """为已入榜条目按需补齐 MoviePilot 可解析的豆瓣等跨来源 ID。"""
        if not candidate or not hasattr(candidate, "source_ids"):
            return candidate
        self._normalize_source_ids(candidate)
        if candidate.source_ids.get("douban") or not candidate.source_ids.get("tmdb"):
            return candidate
        chain_factory, _, media_type_cls = self._dependencies()
        chain = chain_factory()
        media_type = self._media_type(candidate, media_type_cls)
        try:
            douban_info = chain.get_doubaninfo_by_tmdbid(
                int(candidate.source_ids["tmdb"]),
                mtype=media_type,
            )
        except Exception:
            douban_info = None
        if isinstance(douban_info, Mapping):
            douban_id = douban_info.get("id") or douban_info.get("douban_id")
            if douban_id not in (None, ""):
                candidate.source_ids["douban"] = str(douban_id)
                return candidate
        relaxed_match = getattr(chain, "match_doubaninfo", None)
        if not callable(relaxed_match):
            return candidate
        names: List[str] = []
        for raw_name in (
            getattr(candidate, "title", ""),
            getattr(candidate, "original_title", ""),
        ):
            name = str(raw_name or "").strip()
            if name and name not in names:
                names.append(name)
        for name in names:
            try:
                douban_info = relaxed_match(
                    name=name,
                    mtype=media_type,
                    year=None,
                )
            except Exception:
                continue
            if not isinstance(douban_info, Mapping):
                continue
            douban_id = douban_info.get("id") or douban_info.get("douban_id")
            if douban_id not in (None, ""):
                candidate.source_ids["douban"] = str(douban_id)
                break
        return candidate
