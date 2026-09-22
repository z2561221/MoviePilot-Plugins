"""验证身份未决条目的持久化退避和安全恢复，不请求或写入豆瓣。"""

from copy import deepcopy
from types import SimpleNamespace

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


def test_repeated_library_failure_preserves_unexpired_deadline(retry_lab, monkeypatch):
    """媒体库查询失败的早退路径也遵守原有期限，不能被重复播放推迟。"""
    plugin, media, origin, now, _, _, _ = retry_lab
    origin["mediaserver"] = {"server": "lab", "series_id": "series1", "season_id": "season2"}
    monkeypatch.setattr(folio.folio_library, "load_season", lambda *args, **kwargs: None)

    def invoke():
        """只走隔离的媒体库失败分支。"""
        return folio._sync_to_douban(plugin, "还珠格格 第2季", "do", "TV", {}, media, origin=origin)

    assert not invoke()
    first = next(iter(plugin.data["folio_wait"].values()))
    now[0] += 60
    assert not invoke()
    repeated = next(iter(plugin.data["folio_wait"].values()))
    assert repeated["next_retry_at"] == first["next_retry_at"]
    assert repeated["retry_count"] == first["retry_count"] == 1
    now[0] = first["next_retry_at"]
    assert not invoke()
    repeated = next(iter(plugin.data["folio_wait"].values()))
    assert repeated["retry_count"] == 2
    assert repeated["next_retry_at"] == now[0] + 60 * 60


def test_changed_library_or_native_identity_rechecks_immediately(retry_lab):
    """库内季修复或同一库条目的来源身份修正，不受旧等待期限限制。"""
    plugin, media, origin, _, calls, _, _ = retry_lab
    assert not folio._sync_to_douban(plugin, "还珠格格 第2季", "do", "TV", {}, media, origin=origin)
    changed = {**origin, "library_season": {"air_date": "1999-04-21", "episode_numbers": [1, 2]}}
    assert not folio._sync_to_douban(plugin, "还珠格格 第2季", "do", "TV", {}, media, origin=changed)
    assert len(calls) == 2
    reference = {"server": "lab", "series_id": "series1", "season_id": "season2"}
    first = {**changed, "mediaserver": reference}
    repaired = {**first, "media_id": "99999"}
    assert folio_retry.context_key(first, "do") != folio_retry.context_key(repaired, "do")


def test_retry_success_clears_persisted_queue(retry_lab, monkeypatch):
    """到期后核验成功只写一次档案，并清除持久化待处理记录。"""
    plugin, media, origin, now, _, _, result = retry_lab
    writes = []
    monkeypatch.setattr(folio, "_create_douban_api", lambda target: SimpleNamespace(
        set_watching_status=lambda **kwargs: writes.append(kwargs) or True,
    ))
    assert not folio._sync_to_douban(plugin, "还珠格格 第2季", "do", "TV", {}, media, origin=origin)
    now[0] = next(iter(plugin.data["folio_wait"].values()))["next_retry_at"]
    result.update(resolved=True, subject_id="1786740", subject_name="还珠格格第二部",
                  poster_path="https://example.test/season.jpg", identity_scope="season")
    processed = {}
    assert folio._sync_to_douban(
        plugin, "还珠格格 第2季", "do", "TV", processed, media, origin=origin,
    )
    assert len(writes) == 1
    assert plugin.data["folio_wait"] == {}
    assert next(iter(plugin.data["folio_data"].values()))["identity_status"] == "verified"
