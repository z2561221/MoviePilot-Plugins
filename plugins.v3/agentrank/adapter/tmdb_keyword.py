"""TMDB 关键词查询适配器。"""

from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Mapping, Optional, Tuple


class TmdbKeywordProviderError(RuntimeError):
    """表示宿主 TMDB 关键词服务不可用。"""


@dataclass(frozen=True)
class TmdbKeywordRecord:
    """表示一个经过字段筛选的 TMDB 关键词结果。"""

    keyword_id: int
    name: str
    aliases: Tuple[str, ...] = ()

    @classmethod
    def from_payload(cls, payload: Any) -> Optional["TmdbKeywordRecord"]:
        """从宿主或测试载荷提取正整数 ID 与关键词名称。"""
        if isinstance(payload, Mapping):
            raw_id = payload.get("id", payload.get("keyword_id"))
            raw_name = payload.get("name", payload.get("keyword"))
            raw_aliases = payload.get("aliases") or ()
        else:
            raw_id = getattr(payload, "id", getattr(payload, "keyword_id", None))
            raw_name = getattr(payload, "name", getattr(payload, "keyword", None))
            raw_aliases = getattr(payload, "aliases", ()) or ()
        if isinstance(raw_id, bool):
            return None
        try:
            keyword_id = int(raw_id)
        except (TypeError, ValueError):
            return None
        name = str(raw_name or "").strip()
        if keyword_id <= 0 or not name:
            return None
        aliases: List[str] = []
        values = (
            raw_aliases
            if isinstance(raw_aliases, (list, tuple, set))
            else [raw_aliases]
        )
        for value in values:
            text = str(value or "").strip()
            if text and text not in aliases and text != name:
                aliases.append(text)
        return cls(keyword_id=keyword_id, name=name, aliases=tuple(aliases))


class TmdbKeywordAdapter:
    """通过 MoviePilot TheMovieDb 模块查询关键词，测试时可注入 searcher。"""

    def __init__(
        self, searcher: Optional[Callable[[str], Iterable[Any]]] = None
    ):
        """绑定可替换的关键词查询函数；未注入时延迟使用宿主模块。"""
        self._searcher = searcher

    @staticmethod
    def _runtime_search(term: str) -> Iterable[Any]:
        """调用宿主 TmdbApi.search.keywords，避免插件直接拼接 HTTP。"""
        try:
            from app.modules.themoviedb.tmdbapi import TmdbApi

            api = TmdbApi()
        except Exception as error:
            raise TmdbKeywordProviderError(str(error)) from error
        try:
            search = getattr(api, "search", None)
            keywords = getattr(search, "keywords", None)
            if not callable(keywords):
                raise TmdbKeywordProviderError(
                    "MoviePilot TMDB keyword search is unavailable"
                )
            return keywords(term=term, page=1) or ()
        except TmdbKeywordProviderError:
            raise
        except Exception as error:
            raise TmdbKeywordProviderError(str(error)) from error
        finally:
            close = getattr(api, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    def search(self, term: str) -> List[TmdbKeywordRecord]:
        """查询并去重关键词结果，只暴露安全字段。"""
        text = str(term or "").strip()
        if not text:
            return []
        if len(text) > 80:
            raise ValueError("TMDB keyword term exceeds 80 characters")
        searcher = self._searcher or self._runtime_search
        try:
            payload = searcher(text)
        except TmdbKeywordProviderError:
            raise
        except Exception as error:
            raise TmdbKeywordProviderError(str(error)) from error
        if isinstance(payload, Mapping):
            payload = (
                payload.get("results") or ()
                if "results" in payload
                else [payload]
            )
        if payload is None:
            return []
        if not isinstance(payload, (list, tuple, set)):
            payload = [payload]
        records: List[TmdbKeywordRecord] = []
        seen_ids = set()
        for item in payload:
            record = TmdbKeywordRecord.from_payload(item)
            if record is None or record.keyword_id in seen_ids:
                continue
            seen_ids.add(record.keyword_id)
            records.append(record)
        return records
