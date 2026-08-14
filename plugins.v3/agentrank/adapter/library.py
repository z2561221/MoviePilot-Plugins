"""MoviePilot 媒体库存在性适配器。"""

from typing import Any, Dict, Iterable, Set, Tuple

from app.schemas.types import MediaSource

from ..model.candidate import Candidate


class LibraryAdapter:
    """按 V3 统一身份查询 MoviePilot 媒体服务器索引。"""

    def __init__(self, oper: Any = None):
        """允许测试注入 MediaServerOper。"""
        if oper is None:
            from app.db.mediaserver_oper import MediaServerOper

            oper = MediaServerOper()
        self._oper = oper

    def exists(self, candidate: Candidate) -> bool:
        """候选主身份已存在于任一媒体服务器时返回真。"""
        try:
            media_source = MediaSource(candidate.media_source)
        except ValueError:
            return False
        if not candidate.media_id:
            return False
        media_type = str(candidate.metadata.get("mp_media_type") or "").strip()
        if media_type not in {"电影", "电视剧"}:
            media_type = "电影" if candidate.media_type == "movie" else "电视剧"
        try:
            return bool(
                self._oper.exists(
                    media_source=media_source,
                    media_id=str(candidate.media_id),
                    mtype=media_type,
                )
            )
        except (TypeError, ValueError):
            return False

    def candidate_ids(self, candidates: Iterable[Candidate]) -> Set[str]:
        """用一次媒体库索引查询返回已存在候选的类型化身份。"""
        items = list(candidates or ())
        candidate_map: Dict[Tuple[str, str, str], Set[str]] = {}
        for candidate in items:
            source = str(candidate.media_source or "").strip()
            media_id = str(candidate.media_id or "").strip()
            if not source or not media_id:
                continue
            media_type = str(candidate.metadata.get("mp_media_type") or "").strip()
            if media_type not in {"电影", "电视剧"}:
                media_type = "电影" if candidate.media_type == "movie" else "电视剧"
            candidate_map.setdefault((source, media_id, media_type), set()).add(
                candidate.candidate_id
            )
        if not candidate_map:
            return set()
        try:
            from app.db import ScopedSession
            from app.db.models.mediaserver import MediaServerItem
            from sqlalchemy import tuple_

            owned_session = getattr(self._oper, "_db", None) is None
            session = getattr(self._oper, "_db", None) or ScopedSession()
            try:
                rows = list(
                    session.query(
                        MediaServerItem.media_source,
                        MediaServerItem.media_id,
                        MediaServerItem.item_type,
                    )
                    .filter(
                        tuple_(
                            MediaServerItem.media_source,
                            MediaServerItem.media_id,
                            MediaServerItem.item_type,
                        ).in_(list(candidate_map))
                    )
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
        for media_source, media_id, item_type in rows:
            result.update(
                candidate_map.get(
                    (str(media_source), str(media_id), str(item_type)), set()
                )
            )
        return result
