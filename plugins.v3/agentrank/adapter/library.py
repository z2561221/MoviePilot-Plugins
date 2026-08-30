"""MoviePilot 媒体库存在性适配器。"""

from typing import Any, Dict, Iterable, Optional, Set, Tuple

from app.schemas.types import MediaSource

from ..model.candidate import Candidate


class LibraryAdapter:
    """按 V3 统一身份查询 MoviePilot 媒体服务器索引。"""

    def __init__(self, oper: Any = None):
        """允许测试注入 MediaServerOper。"""
        if oper is None:
            from app.db.oper.mediaserver import MediaServerOper

            oper = MediaServerOper()
        self._oper = oper

    def exists(self, candidate: Candidate) -> bool:
        """候选主身份已存在于任一媒体服务器时返回真。"""
        lookup = self._lookup(candidate)
        if lookup is None:
            return False
        media_source, media_id, media_type = lookup
        try:
            return bool(
                self._oper.exists(
                    media_source=media_source,
                    media_id=media_id,
                    mtype=media_type,
                )
            )
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _lookup(
        candidate: Candidate,
    ) -> Optional[Tuple[MediaSource, str, str]]:
        """把候选转换为公开 MediaServerOper 使用的规范查询参数。"""
        try:
            media_source = MediaSource(candidate.media_source)
        except ValueError:
            return None
        if not candidate.media_id:
            return None
        media_type = str(candidate.metadata.get("mp_media_type") or "").strip()
        if media_type not in {"电影", "电视剧"}:
            media_type = "电影" if candidate.media_type == "movie" else "电视剧"
        return media_source, str(candidate.media_id), media_type

    def candidate_ids(self, candidates: Iterable[Candidate]) -> Set[str]:
        """按去重后的规范身份读取媒体库状态，不直接访问宿主 ORM。"""
        items = list(candidates or ())
        candidate_map: Dict[Tuple[MediaSource, str, str], Set[str]] = {}
        for candidate in items:
            lookup = self._lookup(candidate)
            if lookup is None:
                continue
            candidate_map.setdefault(lookup, set()).add(candidate.candidate_id)
        if not candidate_map:
            return set()
        result: Set[str] = set()
        for (
            media_source,
            media_id,
            media_type,
        ), candidate_ids in candidate_map.items():
            try:
                matched = self._oper.exists(
                    media_source=media_source,
                    media_id=media_id,
                    mtype=media_type,
                )
            except Exception:
                matched = None
            if matched:
                result.update(candidate_ids)
        return result
