"""审查发现的查询及并发事件回归，所有外部副作用均隔离。"""

from types import SimpleNamespace

import pytest
from app.plugins.doubancenter.adapter import subscription_query as query
from app.plugins.doubancenter.service import subscription

PARAMS = {"media_source": "themoviedb", "media_id": "123", "season": 2, "episode_group": "group"}


def test_missing_history_method_is_unknown():
    """旧的显式注入对象缺少历史方法，不能把未查历史当成空。"""
    oper = SimpleNamespace(exists=lambda **kw: False)
    assert query.exists(PARAMS, subscribe_oper_cls=lambda: oper) is None


def test_sdk_exact_history_match_prevents_subscription(monkeypatch):
    """完成历史按身份和季精确查找，命中就不创建新的订阅。"""
    calls = []

    def history(**kwargs):
        """返回位于大量历史中的精确命中，服务端负责筛选。"""
        calls.append(kwargs)
        return SimpleNamespace(items=[SimpleNamespace(id=42)], total=1)

    monkeypatch.setattr(query, "_sdk_queries", lambda: SimpleNamespace(
        list_subscriptions=lambda **kw: SimpleNamespace(items=[], total=0),
        list_subscription_history=history,
    ))
    assert query.exists(PARAMS) is True
    assert calls == [{"filters": PARAMS, "page": {"page": 1, "count": 1}}]
    assert subscription.is_existing_identity("themoviedb", "123", season=2, episode_group="group") is True


@pytest.mark.parametrize("active,history,expected", [
    (False, False, False), (None, False, None), (False, None, None),
    (None, True, True), (True, None, True),
])
def test_sdk_query_failure_and_hit_precedence(monkeypatch, active, history, expected):
    """SDK 失败保留未知，已确认命中不能被另一查询失败抹掉。"""
    def response(value):
        """模拟宿主查询异常与完整结果。"""
        if value is None:
            raise RuntimeError("database unavailable")
        return SimpleNamespace(items=[object()] if value else [], total=int(value))

    monkeypatch.setattr(query, "_sdk_queries", lambda: SimpleNamespace(
        list_subscriptions=lambda **kw: response(active),
        list_subscription_history=lambda **kw: response(history),
    ))
    assert query.exists(PARAMS) is expected


def test_incomplete_sdk_page_is_unknown(monkeypatch):
    """非零总数与空条目的矛盾结果不能证明不存在。"""
    monkeypatch.setattr(query, "_sdk_queries", lambda: SimpleNamespace(
        list_subscriptions=lambda **kw: SimpleNamespace(items=[], total=1),
        list_subscription_history=lambda **kw: SimpleNamespace(items=[], total=0),
    ))
    assert query.exists(PARAMS) is None


def test_old_host_uses_separate_real_history_oper(monkeypatch):
    """旧宿主两个真实 Oper 的方法形状不同，历史必须走独立入口。"""
    from app.db.oper.subscribe import SubscribeOper
    from app.db.oper.subscribehistory import SubscribeHistoryOper

    monkeypatch.setattr(query, "_sdk_queries", lambda: None)
    monkeypatch.setattr(SubscribeOper, "exists", lambda self, **kw: False)
    monkeypatch.setattr(SubscribeHistoryOper, "exists", lambda self, **kw: True)
    assert query.exists(PARAMS) is True
