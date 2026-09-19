"""验证身份未决条目的持久化退避和安全恢复，不请求或写入豆瓣。"""

from copy import deepcopy

import pytest
from app.plugins.doubancenter.service import folio, folio_retry

from tests.v3.doubancenter.folio_fakes import FolioPlugin, huanzhu_media


@pytest.fixture
def retry_lab(monkeypatch):
    """固定时钟，并记录实际进入分季验证器的次数及警告。"""
    now, calls, warnings = [1_800_000_000.0], [], []
    result = {"resolved": False, "reason": "未找到通过季首播日校验的豆瓣条目"}

    def verify(*args):
        calls.append(args)
        return dict(result)

    monkeypatch.setattr(folio_retry.time, "time", lambda: now[0])
    monkeypatch.setattr(folio, "_validated_playback_subject", verify)
    monkeypatch.setattr(folio, "_create_douban_api", lambda plugin: object())
    monkeypatch.setattr(folio.logger, "warning", lambda text, **kw: warnings.append(text))
    media = huanzhu_media()
    origin = folio._playback_origin(media, "TV", 2)
    return FolioPlugin(), media, origin, now, calls, warnings, result


def test_repeated_failure_waits_across_reload_and_warns_only_on_change(retry_lab):
    """重复播放和插件重载均不能绕过等待；到期复查不重复警告。"""
    plugin, media, origin, now, calls, warnings, _ = retry_lab

    def invoke(target):
        """以相同播放身份调用同步入口。"""
        return folio._sync_to_douban(target, "还珠格格 第2季", "do", "TV", {}, media, origin=origin)

    assert invoke(plugin) is False
    record = next(iter(plugin.data["folio_wait"].values()))
    assert record["next_retry_at"] == now[0] + 30 * 60
    assert invoke(plugin) is False

    restored = FolioPlugin()
    restored.data = deepcopy(plugin.data)
    restored._wait_process = deepcopy(restored.data["folio_wait"])
    assert invoke(restored) is False
    assert len(calls) == len(warnings) == 1

    now[0] += 30 * 60
    assert invoke(restored) is False
    record = next(iter(restored.data["folio_wait"].values()))
    assert record["next_retry_at"] == now[0] + 60 * 60
    assert len(calls) == 2
    assert len(warnings) == 1


def test_watch_status_change_rechecks_without_downgrading_collected_state(retry_lab):
    """新的看过事件可立即复核，后续在看事件不能覆盖看过状态。"""
    plugin, media, origin, _, calls, warnings, _ = retry_lab
    assert not folio._sync_to_douban(plugin, "还珠格格 第2季", "do", "TV", {}, media, origin=origin)
    assert not folio._sync_to_douban(plugin, "还珠格格 第2季", "collect", "TV", {}, media, origin=origin)
    assert len(calls) == len(warnings) == 2
    assert not folio._sync_to_douban(plugin, "还珠格格 第2季", "do", "TV", {}, media, origin=origin)
    assert len(calls) == 2
    assert next(iter(plugin.data["folio_wait"].values()))["status"] == "collect"


def test_changed_library_facts_and_legacy_queue_remain_immediately_eligible(retry_lab):
    """新的库内季信息绕过旧等待，旧版本队列缺少重试字段时正常接续。"""
    plugin, media, origin, _, _, _, _ = retry_lab
    assert not folio._sync_to_douban(plugin, "还珠格格 第2季", "do", "TV", {}, media, origin=origin)
    record = next(iter(plugin.data["folio_wait"].values()))
    updated = {**origin, "library_season": {"episode_numbers": [1, 2], "air_date": "1999-04-21"}}
    assert folio_retry.is_due(record, updated, "do")
    assert folio_retry.is_due({"identity_status": "unresolved", "origin": origin}, origin, "do")
    assert folio_retry.is_due({**record, "identity_status": "verified"}, origin, "do")


def test_retry_delay_is_bounded_and_new_reason_is_reported(retry_lab):
    """长期缺失有最长六小时间隔，失败原因变化仍会重新警告。"""
    plugin, media, origin, now, calls, warnings, result = retry_lab
    for _ in range(7):
        assert not folio._sync_to_douban(plugin, "还珠格格 第2季", "do", "TV", {}, media, origin=origin)
        record = next(iter(plugin.data["folio_wait"].values()))
        assert record["next_retry_at"] - now[0] <= 6 * 60 * 60
        now[0] = record["next_retry_at"]
    assert len(calls) == 7
    assert len(warnings) == 1
    result["reason"] = "分季豆瓣候选不唯一"
    assert not folio._sync_to_douban(plugin, "还珠格格 第2季", "do", "TV", {}, media, origin=origin)
    assert len(warnings) == 2
    assert next(iter(plugin.data["folio_wait"].values()))["retry_count"] == 1
