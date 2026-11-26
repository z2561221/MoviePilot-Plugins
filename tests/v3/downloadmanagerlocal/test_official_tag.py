"""官种判定按目标站隔离，不在测试中访问真实站点或下载器。"""

import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.plugins.downloadmanagerlocal.service import iyuu, recheck, site_tag, transfer
from app.plugins.downloadmanagerlocal.service.config import DEFAULT_TRACKER_MAPPINGS
from app.plugins.downloadmanagerlocal.utils.config import PLUGIN_CONFIG_DEFAULTS
from app.plugins.downloadmanagerlocal.utils.official_tag import (
    DEFAULT_OFFICIAL_MAPPINGS,
    apply_official,
    match_official,
    parse_official_mappings,
    transfer_release_name,
)
from app.plugins.downloadmanagerlocal.utils.tracker import parse_tracker_mappings
from bencode import bencode


def configured():
    """构造打开官种但关闭站名标签的下载中心。"""
    return SimpleNamespace(_tag_official_enabled=True, _tag_enabled=False, _tag_official_prefix="🏅",
                           _official_groups=parse_official_mappings(DEFAULT_OFFICIAL_MAPPINGS), _tracker_mappings={})


@pytest.mark.parametrize(("site", "title", "match"), [
    ("观众", "AnimeS@ADWeb [集数]", True), ("观众", "[电影] - Test-73ACG.mkv", False),
    ("Sunny", "Show.WEB-DL-Nimbus@Sunny", True), ("朋友", "Show.WEB-DL-Nimbus@Sunny", False),
    ("青蛙", "Test-FROGWeb", True), ("青蛙", "Test-catedu", True), ("青蛙", "Test-FROGE", True),
    ("青蛙", "Test-ADWeb", False), ("观众", "Test-FROG", False), ("", "A-ADE", False),
    ("青蛙", "FROG 出品", False), ("青蛙", "Test-FROGExtended", False),
    ("观众", "Test-Other [字幕组-ADWeb]", False), ("观众", "Test-ADE@Other", False),
])
def test_site_and_complete_release_group(site, title, match):
    """真实后缀、重命名前缀、方括号备注及跨站反例。"""
    assert bool(match_official(configured(), site, title)) is match


def test_config_can_clear_or_extend_defaults():
    """默认关闭；清空前缀或映射不会重新套默认值。"""
    plugin = configured()
    assert PLUGIN_CONFIG_DEFAULTS["tag_official_enabled"] is False
    assert len(plugin._official_groups) == 10
    assert len(plugin._official_groups["青蛙"]) == 4 and len(plugin._official_groups["观众"]) == 6
    plugin._tag_official_prefix = ""
    plugin._official_groups = parse_official_mappings("新站： A+ | 9Team\n新站:B")
    assert match_official(plugin, "新站", "Name-9TEAM") == "官种"
    assert apply_official(["🌀IYUU辅种", "我的辅种计划", "已整理", "转种"], "官种") == ["我的辅种计划", "已整理", "官种"]
    plugin._official_groups = parse_official_mappings("")
    assert not match_official(plugin, "观众", "Name-ADWeb")


def test_transfer_can_use_release_title_with_plain_torrent_root():
    """根目录未带组名可使用下载器发布名，两个发布组冲突不采信改名。"""
    assert transfer_release_name("Season 1", "Show-ADWeb") == "Show-ADWeb"
    assert transfer_release_name("Show-Other.mkv", "Show-ADWeb") == "Show-Other.mkv"
    assert not match_official(configured(), "观众", "-ADWeb")


@pytest.mark.parametrize("group", ["Breeze@Sunny", "Rain@Sunny", "Nimbus@Sunny"])
def test_sunny_alias_restores_old_tasks_without_trusting_existing_label(monkeypatch, group):
    """Sunny 的真实 tracker 不在站点同一父域，且下载器站名标签不能替代来源核验。"""
    plugin = configured()
    plugin._tracker_mappings = parse_tracker_mappings(DEFAULT_TRACKER_MAPPINGS)
    monkeypatch.setattr(site_tag, "load_tracker_directory", lambda: {"sunnypt.top": "Sunny", "example.test": "其他站"})
    row = {"hash": "old", "name": f"[ 中文名 ] - Title.WEB-DL-{group}", "tags": "🏠Sunny,⏩转种"}
    def expected(domains):
        """重放补齐扫描与写入共用的期望标签计算。"""
        return site_tag._expected_completion_tags(plugin, "QB", row, "qbittorrent", source_service=None,
            site_cache={}, transfer_cache={}, iyuu_cache={}, data_snapshot={}, tracker_urls=domains)["official"]
    assert expected(["https://sunnytk.top/announce"]) == {"🏅官种"}
    assert not expected(["https://sunnytk.top.evil.test/announce"])
    assert not expected(["sunnytk.top", "example.test"])
    assert not expected(["example.test"])


@pytest.mark.parametrize("kind", ["transmission", "qbittorrent"])
@pytest.mark.parametrize(("operation", "site", "enabled", "expected"), [
    ("transfer", "观众", True, "🏅官种"), ("transfer", "青蛙", True, "⏩转种"),
    ("transfer", "观众", False, "⏩转种"), ("reseed", "观众", True, "🏅官种"),
    ("reseed", "青蛙", True, "辅种"), ("reseed", "观众", False, "辅种"),
])
def test_labels_in_add_request(monkeypatch, kind, operation, site, enabled, expected):
    """验证两类下载器实际 add 参数，而非只测字符串分类函数。"""
    plugin = configured()
    plugin._tag_official_enabled = enabled
    plugin._torrent_tags = ["⏩转种", "已整理"]
    plugin._iyuu_labelsafterseed = "已整理,辅种"
    plugin._remainoldtag, plugin._remainoldcat, plugin._seed_skipverify = True, False, False
    plugin._fromdownloader = "source"
    plugin.service_info = lambda _name: SimpleNamespace(type="qbittorrent")
    plugin.get_label = lambda *_: ["保种"]
    dl = Mock()
    dl.get_torrents.return_value = ([{"hash": "h1"}], None)
    dl.get_torrent_id_by_tag.return_value = "h1"
    dl.add_torrent.return_value = SimpleNamespace(hashString="h1")
    service = SimpleNamespace(type=kind, name="dest", instance=dl)
    content = bencode({"announce": "https://tracker.test/a", "info": {"name": "Target@ADWeb"}})
    monkeypatch.setattr(site_tag, "load_tracker_directory", lambda: {"tracker.test": site})
    if operation == "transfer":
        assert transfer.download_torrent(plugin, service, content, "/data", {"name": "other-FROG"}) == "h1"
    else:
        assert iyuu.iyuu_download(plugin, service, content, "/data", "", site, expected_hash="h1") == "h1"
    labels = set(dl.add_torrent.call_args.kwargs["tag" if kind == "qbittorrent" else "labels"])
    assert labels & {"⏩转种", "辅种", "🏅官种"} == {expected}
    assert "已整理" in labels
    assert ("保种" in labels) is (operation == "transfer")


def test_old_original_and_tracker_conflict(tmp_path, monkeypatch):
    """无下载历史或当前名称已改，仍可从核过 hash 的原种恢复。"""
    plugin = configured()
    plugin._fromtorrentpath = str(tmp_path)
    info = {"name": "Source-FROG"}
    identity = hashlib.sha1(bencode(info)).hexdigest()
    path = tmp_path / f"{identity}.torrent"
    path.write_bytes(bencode({"info": info}))
    monkeypatch.setattr(site_tag, "load_tracker_directory", lambda: {"a.test": "青蛙", "b.test": "观众"})
    row = {"hash": identity, "name": "手改的名字"}
    def expected(trackers):
        """按目标下载器当前证据计算期望官种标签。"""
        return site_tag._expected_completion_tags(plugin, "QB", row, "qbittorrent", source_service=None,
            site_cache={}, transfer_cache={}, iyuu_cache={}, data_snapshot={}, tracker_urls=trackers)["official"]
    assert expected(["a.test"]) == {"🏅官种"}
    assert not expected(["a.test", "b.test"]) and not expected(["a.test", "unknown.test"])
    path.write_bytes(bencode({"info": {"name": "Fake-FROG"}}))
    assert not expected(["a.test"])


def test_official_old_seed_is_not_authority_to_start():
    """老种被补成官种不等于授权自动启动，仍须该下载器的完成历史。"""
    plugin = configured()
    plugin._fromdownloader = "source"
    plugin.service_info = lambda name: SimpleNamespace(name=name)
    state = {"source-proven": {"transfer_state": "completed", "to_download": "QB", "to_download_id": "proven"}}
    plugin.get_data = lambda: state
    rows = [{"state": "pausedUP", "hash": name, "tags": "🏅官种,已整理"} for name in ("manual", "proven")]
    assert recheck._collect_ready_seed_hashes(plugin, rows, "qbittorrent", only_tagged_sources=True, downloader_name="QB")[0] == ["proven"]
