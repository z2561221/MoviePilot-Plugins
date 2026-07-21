"""MoviePilot 全局订阅读取适配器。"""

from typing import Any, List, Set

from ..model.candidate import typed_tmdb_candidate_id


class SubscriptionAdapter:
    """跨全部用户名读取订阅并生成类型安全媒体身份。"""

    def __init__(self, oper: Any = None):
        """允许测试注入 SubscribeOper，运行时则延迟创建宿主实现。"""
        if oper is None:
            from app.db.subscribe_oper import SubscribeOper

            oper = SubscribeOper()
        self._oper = oper

    @staticmethod
    def _field(record: Any, name: str) -> Any:
        """兼容 ORM 对象与字典读取订阅字段。"""
        if isinstance(record, dict):
            return record.get(name)
        return getattr(record, name, None)

    def list_all(self) -> List[Any]:
        """读取 MoviePilot 当前全部订阅，不按用户名划分范围。"""
        return list(self._oper.list() or [])

    def candidate_ids(self) -> Set[str]:
        """返回全部订阅对应的类型化 TMDB 候选身份。"""
        result: Set[str] = set()
        for record in self.list_all():
            tmdb_id = self._field(record, "tmdbid") or self._field(
                record, "tmdb_id"
            )
            if tmdb_id in (None, ""):
                continue
            media_type = self._field(record, "type") or self._field(
                record, "media_type"
            )
            result.add(typed_tmdb_candidate_id(tmdb_id, media_type))
        return result
