"""MoviePilot 媒体识别与 TMDB 标准化适配器。"""

import inspect
import re
from typing import Any, Callable, Iterable, List, Mapping, Optional, Tuple

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
    _MEDIA_SOURCE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
    _MEDIA_SOURCE_ALIASES = {
        "tmdb": "tmdb",
        "themoviedb": "tmdb",
        "douban": "douban",
        "bangumi": "bangumi",
        "bgm": "bangumi",
        "anilist": "anilist",
        "tvdb": "tvdb",
        "imdb": "imdb",
    }
    _MAX_TITLE_RECOGNITION_ATTEMPTS = 2

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

    @classmethod
    def _source_name(cls, value: Any) -> str:
        """规范宿主媒体来源名并拒绝不可控前缀。"""
        text = str(value or "").strip().casefold()
        if not text:
            return ""
        normalized = cls._MEDIA_SOURCE_ALIASES.get(text, text)
        return normalized if cls._MEDIA_SOURCE_PATTERN.fullmatch(normalized) else ""

    @staticmethod
    def _source_id(value: Any) -> str:
        """读取非空且非零的来源媒体 ID。"""
        text = str(value or "").strip()
        return text if text and text != "0" else ""

    @classmethod
    def _source_identity(cls, candidate: Candidate) -> Tuple[str, str]:
        """选择候选最可靠的来源身份，优先 TMDB 与宿主内置来源。"""
        for source in ("tmdb", "douban", "bangumi", "anilist"):
            media_id = cls._source_id(candidate.source_ids.get(source))
            if media_id:
                return source, media_id
        for raw_source, raw_media_id in candidate.source_ids.items():
            source = cls._source_name(raw_source)
            media_id = cls._source_id(raw_media_id)
            if source and media_id:
                return source, media_id
        return "", ""

    @staticmethod
    def _positive_tmdb_id(value: Any) -> Optional[int]:
        """从宿主映射结果中读取正整数 TMDB ID。"""
        try:
            tmdb_id = int(value)
        except (TypeError, ValueError):
            return None
        return tmdb_id if tmdb_id > 0 else None

    @classmethod
    def _mapped_tmdb_id(cls, value: Any) -> Optional[int]:
        """兼容字典或 MediaInfo 形式的来源到 TMDB 映射结果。"""
        if value is None:
            return None
        if isinstance(value, Mapping):
            for name in ("tmdb_id", "tmdbid", "id"):
                tmdb_id = cls._positive_tmdb_id(value.get(name))
                if tmdb_id:
                    return tmdb_id
            nested = value.get("tmdb_info")
            return cls._mapped_tmdb_id(nested) if nested else None
        for name in ("tmdb_id", "tmdbid"):
            tmdb_id = cls._positive_tmdb_id(getattr(value, name, None))
            if tmdb_id:
                return tmdb_id
        nested = getattr(value, "tmdb_info", None)
        return cls._mapped_tmdb_id(nested) if nested else None

    @staticmethod
    def _recognition_meta(
        candidate: Candidate,
        title: str,
        meta_factory: Callable[[str], Any],
        media_type: Any,
    ) -> Any:
        """为一次受控识别构造独立 MoviePilot MetaInfo。"""
        meta = meta_factory(title)
        if candidate.year:
            meta.year = str(candidate.year)
        meta.type = media_type
        return meta

    @staticmethod
    def _call_recognize(chain: Any, meta: Any, media_type: Any, **kwargs: Any) -> Any:
        """调用宿主识别接口，并在旧版签名不兼容时安全返回空。"""
        try:
            return chain.recognize_media(meta=meta, mtype=media_type, **kwargs)
        except Exception:
            return None

    @classmethod
    def _map_source_to_tmdb(
        cls, chain: Any, source: str, media_id: str, media_type: Any
    ) -> Optional[int]:
        """能力探测宿主来源映射方法，并提取可复用的 TMDB ID。"""
        if not source or source == "tmdb":
            return cls._positive_tmdb_id(media_id) if source == "tmdb" else None
        method = getattr(chain, f"get_tmdbinfo_by_{source}id", None)
        if not callable(method):
            return None
        value: Any = int(media_id) if media_id.isdigit() and source != "douban" else media_id
        try:
            parameters = inspect.signature(method).parameters
        except (TypeError, ValueError):
            parameters = {}
        try:
            mapping = method(value, mtype=media_type) if "mtype" in parameters else method(value)
        except Exception:
            return None
        return cls._mapped_tmdb_id(mapping)

    @classmethod
    def _recognize_source(
        cls,
        chain: Any,
        meta: Any,
        media_type: Any,
        source: str,
        media_id: str,
    ) -> Any:
        """按来源 ID 调用新旧 MoviePilot 兼容识别入口。"""
        if source == "tmdb":
            return cls._call_recognize(
                chain, meta, media_type, tmdbid=cls._positive_tmdb_id(media_id)
            )
        compatibility_kwargs = {
            "douban": {"doubanid": media_id},
            "bangumi": {"bangumiid": media_id},
            "anilist": {"anilistid": media_id},
        }
        mediainfo = cls._call_recognize(
            chain,
            meta,
            media_type,
            source="themoviedb" if source == "tmdb" else source,
            mediaid=media_id,
        )
        if mediainfo or source not in compatibility_kwargs:
            return mediainfo
        return cls._call_recognize(
            chain, meta, media_type, **compatibility_kwargs[source]
        )

    @classmethod
    def _title_candidates(cls, candidate: Candidate, mediainfo: Any = None) -> List[str]:
        """生成有限且去重的 TMDB 标题兜底列表。"""
        names: List[str] = []
        for value in (
            candidate.title,
            candidate.original_title,
            getattr(mediainfo, "title", "") if mediainfo else "",
            getattr(mediainfo, "original_title", "") if mediainfo else "",
            getattr(mediainfo, "en_title", "") if mediainfo else "",
        ):
            name = str(value or "").strip()
            if name and name not in names:
                names.append(name)
            if len(names) >= cls._MAX_TITLE_RECOGNITION_ATTEMPTS:
                break
        return names

    @classmethod
    def _recognize_tmdb_titles(
        cls,
        chain: Any,
        candidate: Candidate,
        mediainfo: Any,
        meta_factory: Callable[[str], Any],
        media_type: Any,
    ) -> Any:
        """最多按两个标题尝试 TMDB 识别，避免候选采集串行放大。"""
        for title in cls._title_candidates(candidate, mediainfo):
            meta = cls._recognition_meta(candidate, title, meta_factory, media_type)
            result = cls._call_recognize(
                chain, meta, media_type, source="themoviedb"
            )
            if result is None:
                result = cls._call_recognize(chain, meta, media_type)
            if cls._mapped_tmdb_id(result):
                return result
        return None

    def recognize(self, candidate: Candidate) -> Optional[Candidate]:
        """识别候选并仅在获得 TMDB 身份时返回标准条目。"""
        self._normalize_source_ids(candidate)
        chain_factory, meta_factory, media_type_cls = self._dependencies()
        media_type = self._media_type(candidate, media_type_cls)
        chain = chain_factory()
        source, media_id = self._source_identity(candidate)
        meta = self._recognition_meta(candidate, candidate.title, meta_factory, media_type)
        mapped_tmdb_id = self._map_source_to_tmdb(
            chain, source, media_id, media_type
        )
        mediainfo = None
        if mapped_tmdb_id:
            mediainfo = self._call_recognize(
                chain, meta, media_type, tmdbid=mapped_tmdb_id
            )
        if mediainfo is None and source and media_id:
            mediainfo = self._recognize_source(
                chain, meta, media_type, source, media_id
            )
        if not self._mapped_tmdb_id(mediainfo):
            mediainfo = self._recognize_tmdb_titles(
                chain, candidate, mediainfo, meta_factory, media_type
            )
        resolved_tmdb_id = self._mapped_tmdb_id(mediainfo)
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
