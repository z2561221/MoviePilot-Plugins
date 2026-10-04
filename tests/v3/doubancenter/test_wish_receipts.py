"""想看队列依据本次订阅回执决定重试，所有存储与外部查询均隔离。"""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter.service import folio, subscription
from app.schemas.types import MediaSource, MediaType


@pytest.fixture
def wish_lab():
    """提供一条统一媒体身份的想看候选和内存存储。"""
    saved = {"folio_wish_queue": [{"subject_id": "123", "title": "回执测试", "year": "2026"}]}
    plugin = SimpleNamespace(
        get_data=lambda key: deepcopy(saved.get(key)),
        save_data=lambda key, value: saved.__setitem__(key, deepcopy(value)),
    )
    media = SimpleNamespace(
        title="回执测试", year="2026", type=MediaType.TV,
        media_source=MediaSource.TMDB, media_id="777", tmdb_id=777,
        get_poster_image=lambda: "", episode_group=None,
    )
    return plugin, media, saved


def test_unknown_subscription_is_retried_then_existing_clears_failure(wish_lab, monkeypatch):
    """第一次及重复查询失败都不能吞掉候选，恢复后才出队并清除旧错误。"""
    plugin, media, saved = wish_lab
    monkeypatch.setattr(subscription, "is_existing_media", lambda *a, **kw: None)
    for attempt in (1, 2):
        folio.process_wish_queue(plugin, recognize=lambda *_: media)
        assert len(saved["folio_wish_queue"]) == 1
        assert saved["folio_wish_queue"][0]["retry"] == attempt
        assert saved["folio_wish_processed"] == []
        assert saved["folio_wish_failed"][-1]["reason"] == "subscribe_failed"
        assert "未提交" in saved["folio_wish_failed"][-1]["message"]
        assert len(saved["subscribe_records"]) == 1
        assert "tmdbid" not in saved["subscribe_records"][0]
    monkeypatch.setattr(subscription, "is_existing_media", lambda *a, **kw: True)
    monkeypatch.setattr(subscription.observation, "cleanup_observe_logs", lambda *a, **kw: None)
    folio.process_wish_queue(plugin, recognize=lambda *_: media)
    assert saved["folio_wish_queue"] == []
    assert saved["folio_wish_failed"] == []
    assert len(saved["folio_wish_processed"]) == 1


@pytest.mark.parametrize("receipt", [False, None, {}, {"success": False}, {"ok": False},
                                     subscription.SubscriptionResult("failed", "rejected")])
def test_non_success_receipts_keep_candidate(wish_lab, receipt):
    """无明确成功证据时保留候选，不伪造完成记录。"""
    plugin, media, saved = wish_lab
    folio.process_wish_queue(plugin, recognize=lambda *_: media, subscribe=lambda *a, **kw: receipt)
    assert len(saved["folio_wish_queue"]) == 1
    assert saved["folio_wish_processed"] == []


@pytest.mark.parametrize("receipt", [True, {"success": True}, {"existing": True},
                                     subscription.SubscriptionResult("success")])
def test_confirmed_completion_removes_candidate(wish_lab, receipt):
    """兼容显式注入的旧回调成功值以及新的结构化回执。"""
    plugin, media, saved = wish_lab
    folio.process_wish_queue(plugin, recognize=lambda *_: media, subscribe=lambda *a, **kw: receipt)
    assert saved["folio_wish_queue"] == []
    assert len(saved["folio_wish_processed"]) == 1
