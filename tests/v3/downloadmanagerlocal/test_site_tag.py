"""站点标签追加必须保留目标标签，覆盖 TR 实际替换语义及各后处理入口。"""

from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest
from app.modules.qbittorrent.qbittorrent import Qbittorrent
from app.modules.transmission.transmission import Transmission
from app.plugins.downloadmanagerlocal.service import iyuu, rename, site_tag, transfer
from app.plugins.downloadmanagerlocal.service.config import DEFAULT_TRACKER_MAPPINGS
from app.plugins.downloadmanagerlocal.utils.torrent_adapter import get_label
from app.plugins.downloadmanagerlocal.utils.tracker import parse_tracker_mappings


class MemoryDownloader:
    """使用真实宿主标签方法，仅将底层 RPC 和任务存储替换为内存对象。"""

    def __init__(self, kind, labels):
        """保存标签快照，绑定真实宿主的追加或替换方法。"""
        self.kind = kind
        self.labels = list(labels)
        self.writes = []
        self.trc = self.qbc = self
        self.set_torrent_tag = MethodType(Transmission.set_torrent_tag, self)
        self.set_torrents_tag = MethodType(Qbittorrent.set_torrents_tag, self)

    def change_torrent(self, *, labels, ids):
        """模拟 Transmission RPC 整组替换标签。"""
        self.labels = list(labels)
        self.writes.append((ids, list(labels)))

    def torrents_add_tags(self, *, tags, torrent_hashes):
        """模拟 qBittorrent RPC 追加标签。"""
        self.labels = list(dict.fromkeys(self.labels + tags))
        self.writes.append((torrent_hashes, list(tags)))

    def get_torrents(self, ids):
        """返回和真实下载器字段一致的目标任务快照。"""
        if self.kind == "qbittorrent":
            torrent = {
                "hash": ids[0], "name": "Example.2026", "save_path": "/downloads",
                "tags": ", ".join(self.labels),
                "trackers": [{"url": "https://tracker.example/announce", "tier": 0}],
            }
        else:
            torrent = SimpleNamespace(
                hashString=ids[0], name="Example.2026", download_dir="/downloads",
                labels=list(self.labels),
                trackers=[{"announce": "https://tracker.example/announce", "tier": 0}],
            )
        return [torrent], None

    def add_torrent(self, *, content, download_dir, is_paused, labels):
        """模拟 TR 创建任务时接收转移服务拼好的标签。"""
        self.labels = list(labels)
        return SimpleNamespace(hashString="target-hash")


@pytest.fixture
def tag_case(monkeypatch):
    """配置可识别站点及无后台动作的插件，保留真实标签服务。"""
    monkeypatch.setattr(site_tag, "find_site_by_domain", lambda _domain: "彩虹岛")
    log = Mock()
    monkeypatch.setattr(site_tag, "logger", log)
    plugin = SimpleNamespace(
        _tracker_mappings={}, _tag_siteprefix="", _tag_enabled=True,
        _rename_enabled=False, _seed_skipverify=True, _seed_autostart=False,
        _transfer_stop_generation=0, _register_seed_recheck=Mock(),
    )
    plugin._tag_torrent = lambda *args: site_tag.tag_torrent(plugin, *args)
    return SimpleNamespace(plugin=plugin, log=log)


@pytest.mark.parametrize("kind", ["transmission", "qbittorrent"])
@pytest.mark.parametrize("prefix,existing", [("", []), ("", ["MOVIEPILOT", "转移做种"]),
                                              ("站点/", ["保种"]), ("", ["保种", "彩虹岛"])])
def test_site_tag_preserves_existing_labels_and_is_idempotent(tag_case, kind, prefix, existing):
    """已有标签不丢失，重复执行及已有站名不重复写入。"""
    plugin = tag_case.plugin
    plugin._tag_siteprefix = prefix
    downloader = MemoryDownloader(kind, existing)
    original = list(existing)
    site = prefix + "彩虹岛"

    assert plugin._tag_torrent(downloader, kind, "target-hash", existing,
                               ["https://tracker.example/announce"]) is True
    assert set(downloader.labels) == set(existing) | {site}
    assert existing == original
    assert len(downloader.labels) == len(set(downloader.labels))
    assert len(downloader.writes) == (0 if site in existing else 1)
    write_count = len(downloader.writes)

    assert plugin._tag_torrent(downloader, kind, "target-hash", list(downloader.labels),
                               ["https://tracker.example/announce"]) is True
    assert len(downloader.writes) == write_count


@pytest.mark.parametrize("remainoldtag,tag_enabled", [(True, True), (False, True), (True, False)])
def test_transfer_then_site_tag_respects_retention_setting(tag_case, remainoldtag, tag_enabled):
    """实际调用转移添加与目标回读，验证保留开关和新增标签互不覆盖。"""
    plugin = tag_case.plugin
    plugin._remainoldtag = remainoldtag
    plugin._torrent_tags = ["转移做种"]
    plugin._tag_enabled = tag_enabled
    plugin._fromdownloader = "source"
    plugin.service_info = lambda _name: SimpleNamespace(type="qbittorrent")
    plugin.get_label = get_label
    downloader = MemoryDownloader("transmission", [])
    service = SimpleNamespace(name="target", type="transmission", instance=downloader)

    torrent_hash = transfer.download_torrent(
        plugin, service, b"fixture", "/downloads", {"tags": "MOVIEPILOT, 保种, 已整理"}
    )
    assert torrent_hash == "target-hash"
    assert transfer.post_transfer_process(plugin, service, torrent_hash) is True
    expected = {"转移做种"}
    if remainoldtag:
        expected.update(["MOVIEPILOT", "保种", "已整理"])
    if tag_enabled:
        expected.add("彩虹岛")
    assert set(downloader.labels) == expected


@pytest.mark.parametrize("kind", ["transmission", "qbittorrent"])
@pytest.mark.parametrize("entrypoint", ["iyuu", "rename"])
def test_other_postprocessing_preserves_target_labels(tag_case, monkeypatch, kind, entrypoint):
    """IYUU 和重命名补刀均通过公共入口保留当前目标标签。"""
    plugin = tag_case.plugin
    downloader = MemoryDownloader(kind, ["保种", "IYUU"])
    service = SimpleNamespace(name="target", type=kind, instance=downloader)
    if entrypoint == "iyuu":
        assert iyuu._postprocess_iyuu_target(plugin, service, "target-hash", "source-hash", 0)
    else:
        monkeypatch.setattr(rename, "get_failed_rename_hashes", lambda _plugin: ["target-hash"])
        result = rename.retry_failed_renames(plugin, service)
        assert result["success"] == 1
        assert result["failed"] == 0
    assert set(downloader.labels) == {"保种", "IYUU", "彩虹岛"}


@pytest.mark.parametrize("kind", ["transmission", "qbittorrent"])
@pytest.mark.parametrize("failure", ["false", "exception"])
def test_site_tag_failure_does_not_report_success(tag_case, kind, failure):
    """标签接口拒绝或抛出异常时返回失败，不输出成功日志。"""
    downloader = MemoryDownloader(kind, ["保种"])
    setter = Mock(return_value=False)
    if failure == "exception":
        setter.side_effect = RuntimeError("RPC failed")
    method = "set_torrent_tag" if kind == "transmission" else "set_torrents_tag"
    setattr(downloader, method, setter)

    assert tag_case.plugin._tag_torrent(downloader, kind, "target-hash", ["保种"],
                                       ["https://tracker.example/announce"]) is False
    assert downloader.labels == ["保种"]
    assert not tag_case.log.info.called


def test_transmission_site_tag_does_not_require_org_tags(tag_case):
    """旧式 Transmission 标签包装不接收 org_tags 时仍保留已有标签。"""
    downloader = MemoryDownloader("transmission", ["保种", "IYUU"])
    writes = []

    def legacy_set_torrent_tag(*, ids, tags):
        writes.append((ids, list(tags)))
        downloader.change_torrent(ids=ids, labels=tags)
        return True

    downloader.set_torrent_tag = legacy_set_torrent_tag
    assert tag_case.plugin._tag_torrent(
        downloader, "transmission", "target-hash", ["保种", "IYUU"],
        ["https://tracker.example/announce"],
    ) is True
    assert set(downloader.labels) == {"保种", "IYUU", "彩虹岛"}
    assert writes == [("target-hash", ["保种", "IYUU", "彩虹岛"])]


def test_transmission_site_tag_merges_latest_labels(tag_case):
    """Transmission 打站点标签时以写入前最新 labels 为准。"""
    downloader = MemoryDownloader("transmission", ["保种", "扫描后新增"])

    assert tag_case.plugin._tag_torrent(
        downloader, "transmission", "target-hash", ["保种"],
        ["https://tracker.example/announce"],
    ) is True

    assert set(downloader.labels) == {"保种", "扫描后新增", "彩虹岛"}


@pytest.mark.parametrize("value,expected", [
    ("https://TRACKER.Example:443/announce", "tracker.example"),
    ("udp://tracker.example:6969/announce", "tracker.example"),
    ("tracker.example:443", "tracker.example"),
    ("tracker.example.", "tracker.example"),
])
def test_tracker_host_normalization(value, expected):
    """Tracker URL、裸 host:port 和尾点归一到主机名。"""
    assert site_tag._read_tracker_domain(value) == expected


def test_default_tracker_aliases_cover_reported_domains():
    """默认映射覆盖 issue 报告的别名 tracker。"""
    mappings = parse_tracker_mappings(DEFAULT_TRACKER_MAPPINGS)
    assert site_tag._mapped_tracker_domain("tracker.m-team.cc:443", mappings) == "m-team.cc"
    assert site_tag._mapped_tracker_domain("agsvpt.cn", mappings) == "agsvpt.com"
    assert site_tag._mapped_tracker_domain("x-anime.cc", mappings) == "u2.dmhy.org"
    assert site_tag._mapped_tracker_domain("anime.dmhy.org:443", mappings) == "u2.dmhy.org"
    assert site_tag._mapped_tracker_domain("daydream.dmhy.best", mappings) == "u2.dmhy.org"


def test_site_lookup_uses_longest_parent_domain_and_rejects_lookalikes(monkeypatch):
    """父域匹配取最具体站点，并以点边界拒绝相似后缀。"""
    monkeypatch.setattr(site_tag, "list_site_dicts", lambda: [
        {"domain": "example.com", "name": "父站"},
        {"domain": "https://foo.example.com/", "name": "子站"},
    ])
    monkeypatch.setattr(site_tag, "get_site_indexer", lambda _: None)
    assert site_tag.find_site_by_domain("tracker.foo.example.com:443") == "子站"
    assert site_tag.find_site_by_domain("evil-example.com") is None
