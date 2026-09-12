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
        """查询单项已确认库状态；失败抛出异常供调用方保留待核验状态。"""
        state = self.candidate_states([candidate]).get(candidate.candidate_id)
        if state is None:
            raise RuntimeError("媒体库状态查询失败")
        return state

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

    def candidate_states(self, candidates: Iterable[Candidate]) -> Dict[str, Optional[bool]]:
        """按身份去重查询，分别保留存在、不存在和失败三种状态。"""
        items = list(candidates or ())
        states: Dict[str, Optional[bool]] = {
            candidate.candidate_id: None for candidate in items
        }
        candidate_map: Dict[Tuple[MediaSource, str, str], Set[str]] = {}
        for candidate in items:
            lookup = self._lookup(candidate)
            if lookup is not None:
                candidate_map.setdefault(lookup, set()).add(candidate.candidate_id)
        for (media_source, media_id, media_type), candidate_ids in candidate_map.items():
            try:
                state = bool(self._oper.exists(
                    media_source=media_source, media_id=media_id, mtype=media_type,
                ))
            except Exception:
                state = None
            for candidate_id in candidate_ids:
                states[candidate_id] = state
        return states

    def candidate_ids(self, candidates: Iterable[Candidate]) -> Set[str]:
        """兼容完整集合查询；部分失败时不得返回伪装成完整的空集合。"""
        states = self.candidate_states(candidates)
        if any(state is None for state in states.values()):
            raise RuntimeError("部分候选媒体库状态未知")
        return {candidate_id for candidate_id, state in states.items() if state is True}
