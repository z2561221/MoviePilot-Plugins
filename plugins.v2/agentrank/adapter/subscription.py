"""MoviePilot 用户订阅读取适配器。"""

from typing import Any, List


class SubscriptionAdapter:
    """只通过当前 core 的按用户名接口读取订阅。"""

    def __init__(self, oper: Any = None):
        """允许测试注入 SubscribeOper，运行时则延迟创建宿主实现。"""
        if oper is None:
            from app.db.subscribe_oper import SubscribeOper

            oper = SubscribeOper()
        self._oper = oper

    @staticmethod
    def _username(record: Any) -> str:
        """兼容 ORM 对象与字典读取订阅所属用户。"""
        if isinstance(record, dict):
            return str(record.get("username") or "").strip()
        return str(getattr(record, "username", "") or "").strip()

    def list_by_username(self, username: str) -> List[Any]:
        """读取一个用户的订阅，并拒绝上游意外混入的其他用户记录。"""
        target = str(username or "").strip()
        if not target:
            raise ValueError("username is required")
        records = self._oper.list_by_username(username=target, state=None, mtype=None) or []
        return [
            record
            for record in records
            if not self._username(record) or self._username(record) == target
        ]
