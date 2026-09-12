"""订阅查重失败必须阻止写入，同时保留可信的回退结果。"""

from types import SimpleNamespace

from app.schemas.types import MediaSource, MediaType
from app.plugins.doubancenter.service import dashboard_rank_subscription, subscription


def _media():
    """构造具有完整身份的待订阅媒体。"""
    return SimpleNamespace(
        title="查询边界", year="2026", type=MediaType.MOVIE,
        media_source=MediaSource.TMDB, media_id="123", tmdb_id=123,
        episode_group=None, get_poster_image=lambda: "",
    )


class FailedLookupChain:
    """模拟主查重失败，禁止进入订阅写入。"""

    def exists(self, **kwargs):
        """模拟临时查询故障。"""
        raise RuntimeError("lookup unavailable")

    def add(self, **kwargs):
        """查重未知时不得提交订阅。"""
        raise AssertionError("unknown lookup must not submit")


class FailedLookupOper:
    """模拟活动订阅和完成历史均无法查询。"""

    def exists(self, **kwargs):
        """拒绝活动订阅查询。"""
        raise RuntimeError("active lookup unavailable")

    def exist_history(self, **kwargs):
        """拒绝完成历史查询。"""
        raise RuntimeError("history lookup unavailable")


def test_all_failed_lookups_stop_auto_subscription(monkeypatch):
    """三条查重路径均失败时只记录失败，不创建订阅或清理观察记录。"""
    records = []
    monkeypatch.setattr(subscription, "write_subscribe_record", lambda *a, **kw: records.append(kw))
    monkeypatch.setattr(subscription.observation, "cleanup_observe_logs", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("keep observations")))

    assert subscription.is_existing_media(
        _media(), subscribe_chain_cls=FailedLookupChain, subscribe_oper_cls=FailedLookupOper,
    ) is None
    assert subscription.add_subscription(
        object(), _media(), subscribe_chain_cls=FailedLookupChain,
        subscribe_oper_cls=FailedLookupOper,
    ) is False
    assert records[0]["status"] == "failed"
    assert "未提交订阅" in records[0]["reason"]


def test_positive_history_survives_another_lookup_failure():
    """活动查询失败不能覆盖已确认命中的完成历史。"""
    class HistoryHit(FailedLookupOper):
        """提供可信完成历史。"""

        def exist_history(self, **kwargs):
            """返回已确认存在。"""
            return True

    assert subscription.is_existing_media(
        _media(), subscribe_chain_cls=FailedLookupChain, subscribe_oper_cls=HistoryHit,
    ) is True


def test_complete_fallback_can_confirm_absence():
    """主链失败后，完整成功的回退查询仍能确认不存在。"""
    class EmptyLookup:
        """返回成功的空查询。"""

        def exists(self, **kwargs):
            """确认没有活动订阅。"""
            return False

        def exist_history(self, **kwargs):
            """确认没有完成历史。"""
            return False

    assert subscription.is_existing_media(
        _media(), subscribe_chain_cls=FailedLookupChain, subscribe_oper_cls=EmptyLookup,
    ) is False


def test_manual_subscription_returns_lookup_failure(monkeypatch):
    """手动订阅同样停在未知查重结果之前。"""
    class MediaChain:
        """返回固定识别结果。"""

        def recognize_media(self, **kwargs):
            """返回有效媒体。"""
            return _media()

    monkeypatch.setattr(subscription, "is_existing_media", lambda *a, **kw: None)
    result = dashboard_rank_subscription.subscribe_from_rank(
        object(), 123, "movie", "查询边界", "2026",
        media_chain_cls=MediaChain, subscribe_chain_cls=FailedLookupChain,
    )
    assert result == {"success": False, "message": "订阅状态检查失败，请稍后重试"}


def test_bangumi_fallback_stops_before_fetch(monkeypatch):
    """Bangumi 回退不得在查重未知时继续获取详情或添加订阅。"""
    monkeypatch.setattr(subscription, "is_existing_identity", lambda *a, **kw: None)

    def unexpected_fetch(*args, **kwargs):
        """查询失败后不应继续后续工作。"""
        raise AssertionError("unknown lookup must stop before fetching")

    result = dashboard_rank_subscription.subscribe_from_bangumi_subject(
        object(), FailedLookupChain(), MediaType.TV, "查询边界", "2026", 42,
        bangumi_subject_fetcher=unexpected_fetch,
        bangumi_subject_title=lambda *a, **kw: "查询边界",
        bangumi_subject_year=lambda *a, **kw: "2026",
    )
    assert result == {"success": False, "message": "订阅状态检查失败，请稍后重试"}
