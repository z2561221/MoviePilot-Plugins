"""MoviePilot 媒体库存在性适配器。"""

from typing import Any

from ..model.candidate import Candidate


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
        try:
            return bool(self._oper.exists(tmdbid=int(tmdb_id)))
        except (TypeError, ValueError):
            return False
