"""MoviePilot 媒体库存在性适配器。"""

from typing import Any, Iterable, Set

from ..model.candidate import Candidate, typed_tmdb_candidate_id


class LibraryAdapter:
    """按 TMDB 身份查询 MoviePilot 媒体服务器索引。"""

    def __init__(self, oper: Any = None):
        """允许测试注入 MediaServerOper。"""
        if oper is None:
            from app.db.mediaserver_oper import MediaServerOper

            oper = MediaServerOper()
        self._oper = oper

    def exists(self, candidate: Candidate) -> bool:
        """候选 TMDB ID 已存在于任一媒体服务器时返回真。"""
        tmdb_id = candidate.source_ids.get("tmdb")
        if not tmdb_id:
            return False
        media_type = str(candidate.metadata.get("mp_media_type") or "").strip()
        if media_type not in {"电影", "电视剧"}:
            media_type = "电影" if candidate.media_type == "movie" else "电视剧"
        try:
            return bool(self._oper.exists(tmdbid=int(tmdb_id), mtype=media_type))
        except (TypeError, ValueError):
            return False

    def candidate_ids(self, candidates: Iterable[Candidate]) -> Set[str]:
        """用一次媒体库索引查询返回已存在候选的类型化身份。"""
        items = list(candidates or ())
        tmdb_ids = {
            int(value)
            for candidate in items
            if (value := str(candidate.source_ids.get("tmdb") or "")).isdigit()
            and int(value) > 0
        }
        if not tmdb_ids:
            return set()
        try:
            from app.db import ScopedSession
            from app.db.models.mediaserver import MediaServerItem

            owned_session = getattr(self._oper, "_db", None) is None
            session = getattr(self._oper, "_db", None) or ScopedSession()
            try:
                rows = list(
                    session.query(MediaServerItem.tmdbid, MediaServerItem.item_type)
                    .filter(MediaServerItem.tmdbid.in_(tmdb_ids))
                    .all()
                )
            finally:
                if owned_session:
                    session.close()
        except Exception:
            return {
                candidate.candidate_id
                for candidate in items
                if self.exists(candidate)
            }
        result: Set[str] = set()
        for tmdb_id, item_type in rows:
            try:
                result.add(
                    typed_tmdb_candidate_id(
                        tmdb_id,
                        "movie" if str(item_type) == "电影" else "tv",
                    )
                )
            except ValueError:
                continue
        return result
