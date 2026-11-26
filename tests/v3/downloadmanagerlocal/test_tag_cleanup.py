from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


PLUGIN_DIR = Path(
    os.environ.get("DOWNLOADMANAGERLOCAL_PLUGIN_DIR")
    or Path(__file__).resolve().parents[1]
)


def _load_tag_cleanup():
    """通过生产命名空间加载纯标签归属工具。"""
    return importlib.import_module("app.plugins.downloadmanagerlocal.utils.tag_cleanup")


@pytest.fixture(autouse=True)
def isolated_tag_service(monkeypatch):
    """只替换外部适配器和配置投影，保留真实共享协调及模型。"""
    service = importlib.import_module("app.plugins.downloadmanagerlocal.service.site_tag")
    monkeypatch.setattr(service, "settings", SimpleNamespace(TORRENT_TAG="MoviePilot"))
    monkeypatch.setattr(service, "logger", SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    ))
    monkeypatch.setattr(service, "generate_random_tag", lambda length=10: "A" * length)
    monkeypatch.setattr(service, "get_site_indexer", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "list_site_dicts", lambda: [])
    monkeypatch.setattr(service, "find_site_by_domain", service.find_site_by_domain)
    monkeypatch.setattr(service, "get_tracker_urls", service.get_tracker_urls)


def _load_site_tag(host_tag: str):
    """注入本用例宿主标签，不创建另一份插件模块身份。"""
    service = importlib.import_module("app.plugins.downloadmanagerlocal.service.site_tag")
    service.settings = SimpleNamespace(TORRENT_TAG=host_tag)
    return service


class FakeQbittorrent:
    """模拟事件标签清理所需的 qBittorrent 接口。"""

    def __init__(self, torrents: list[dict]):
        """保存任务并记录标签写操作。"""
        self.torrents = torrents
        self.remove_calls = []
        self.delete_calls = []

    def get_torrents(self, ids=None):
        """按 hash 返回任务，兼容 qBittorrent 的二元组响应。"""
        if not ids:
            return list(self.torrents), None
        hash_set = set(ids if isinstance(ids, list) else [ids])
        return [item for item in self.torrents if item.get("hash") in hash_set], None

    def remove_torrents_tag(self, ids, tag):
        """从指定任务移除标签。"""
        hash_set = set(ids if isinstance(ids, list) else [ids])
        self.remove_calls.append((sorted(hash_set), tag))
        for torrent in self.torrents:
            if torrent.get("hash") not in hash_set:
                continue
            tags = [value.strip() for value in torrent.get("tags", "").split(",") if value.strip()]
            torrent["tags"] = ",".join(value for value in tags if value != tag)
        return True

    def delete_torrents_tag(self, ids, tag):
        """记录 qBittorrent 标签定义删除。"""
        self.delete_calls.append((ids, tag))
        return True

    def set_torrents_tag(self, ids, tags):
        """向指定任务追加标签。"""
        hash_set = set(ids if isinstance(ids, list) else [ids])
        for torrent in self.torrents:
            if torrent.get("hash") not in hash_set:
                continue
            current = [value.strip() for value in torrent.get("tags", "").split(",") if value.strip()]
            torrent["tags"] = ", ".join(dict.fromkeys([*current, *tags]))
        return True


class FakeTransmission:
    """模拟 Transmission 对象任务、整组覆盖写入及空标签更新。"""

    def __init__(self, torrents: list[SimpleNamespace]):
        self.torrents = torrents
        self.writes = []
        self.definition_calls = []
        self.trc = self

    def get_torrents(self, ids=None):
        if ids is None:
            return list(self.torrents), None
        hash_set = set(ids if isinstance(ids, list) else [ids])
        return [item for item in self.torrents if item.hashString in hash_set], None

    def set_torrent_tag(self, *, ids, tags):
        return self.change_torrent(ids=ids, labels=tags)

    def change_torrent(self, *, ids, labels):
        hash_set = set(ids if isinstance(ids, list) else [ids])
        self.writes.append((sorted(hash_set), list(labels)))
        for torrent in self.torrents:
            if torrent.hashString in hash_set:
                torrent.labels = list(labels)
        return True

class EventPlugin:
    """模拟转移配置中来源与目标下载器均参与事件清理的插件。"""

    def __init__(self, services):
        """保存双端下载器配置与服务。"""
        self._fromdownloader = "QB1"
        self._todownloader = "QB2"
        self._active_temporary_tags = set()
        self._torrent_tags = []
        self._iyuu_labelsafterseed = ""
        self._tag_siteprefix = ""
        self.services = services

    def service_info(self, name):
        """按名称返回下载器服务。"""
        return self.services.get(name)


def _event_torrent(hash_value: str, tags: str) -> dict:
    """构造事件清理用的 qBittorrent 任务。"""
    return {"hash": hash_value, "name": hash_value, "tags": tags}


def _transmission_torrent(hash_value: str, labels: list[str]) -> SimpleNamespace:
    """构造 Transmission 风格对象。"""
    return SimpleNamespace(hashString=hash_value, name=hash_value, labels=list(labels))


@pytest.mark.parametrize("kind", ["qbittorrent", "transmission"])
@pytest.mark.parametrize("has_official", [False, True])
def test_confirmed_official_repair_without_history(kind, has_official, monkeypatch):
    """无历史老种可补官种，已含官种仍清角色；拒选、站点变化和重复扫描不误写。"""
    service = _load_site_tag("MoviePilot")
    labels = ["⏩转种", "辅种", "已整理", "用户标签"] + (["🏅官种"] if has_official else [])
    if kind == "qbittorrent":
        row = {"hash": "old", "name": "Series@ADWeb [副标题]", "tags": ",".join(labels),
               "trackers": [{"tier": 0, "url": "https://a.test/announce"}]}
        downloader = FakeQbittorrent([row])
    else:
        row = _transmission_torrent("old", labels.copy())
        row.name = "Series@ADWeb [副标题]"
        row.trackers = [{"tier": 0, "announce": "https://a.test/announce"}]
        downloader = FakeTransmission([row])
    plugin = EventPlugin({"Dest": SimpleNamespace(name="Dest", instance=downloader, type=kind)})
    plugin._tag_official_enabled, plugin._tag_enabled = True, False
    plugin._official_groups = {"观众": {"adweb"}}
    monkeypatch.setattr(service, "find_site_by_domain", lambda _: "观众")
    scan = lambda: service.scan_tag_completion(plugin, ["Dest"])["downloaders"][0]["tags"]
    groups = scan()
    assert [(group["kind"], group["tag"]) for group in groups] == [("official", "🏅官种")]
    assert set(service.get_label(row, kind)) == set(labels)
    repairs = [{**groups[0], "downloader": "Dest"}]
    monkeypatch.setattr(service, "find_site_by_domain", lambda _: "青蛙")
    assert service.execute_tag_completion(plugin, repairs)["skipped"]
    assert set(service.get_label(row, kind)) == set(labels)
    monkeypatch.setattr(service, "find_site_by_domain", lambda _: "观众")
    if not has_official and kind == "qbittorrent":
        with monkeypatch.context() as local:
            local.setattr(downloader, "set_torrents_tag", lambda **_: True)
            assert service.execute_tag_completion(plugin, repairs)["failed"]
            assert not downloader.remove_calls
    assert service.execute_tag_completion(plugin, repairs)["added"][0]["replaced"] == sorted(["⏩转种", "辅种"])
    assert set(service.get_label(row, kind)) == {"🏅官种", "已整理", "用户标签"}
    assert not scan()


def test_managed_anchor_recognizes_single_task_legacy_temporary_tag():
    """当前业务锚点应识别单任务上的十位旧临时标签。"""
    cleanup = _load_tag_cleanup()
    torrent_tags = {"qb-hash": {"⏩转种", "SUURFaG0p7"}}

    assert cleanup.classify_tag(
        "SUURFaG0p7",
        ["qb-hash"],
        torrent_tags,
        {"⏩转种"},
        set(),
    ) == "legacy_temporary"


def test_custom_host_tag_is_protected_and_anchors_legacy_cleanup():
    """用户自定义宿主标签应受保护并能证明同任务旧随机标签的归属。"""
    site_tag = _load_site_tag("CustomTag1")
    cleanup = _load_tag_cleanup()
    plugin = SimpleNamespace(_torrent_tags=[], _iyuu_labelsafterseed="")
    managed_tags = site_tag._managed_tag_anchors(plugin)
    torrent_tags = {"qb-hash": {"CustomTag1", "SUURFaG0p7"}}

    assert cleanup.classify_tag(
        "CustomTag1",
        ["qb-hash"],
        torrent_tags,
        managed_tags,
        set(),
    ) == "managed"
    assert cleanup.classify_tag(
        "SUURFaG0p7",
        ["qb-hash"],
        torrent_tags,
        managed_tags,
        set(),
    ) == "legacy_temporary"


def test_shared_legacy_tag_is_not_treated_as_cleanup_candidate():
    """被多个任务共用的十位标签不得按旧临时标签自动清理。"""
    cleanup = _load_tag_cleanup()
    torrent_tags = {
        "qb-hash-1": {"任意标签", "SUURFaG0p7"},
        "qb-hash-2": {"任意标签", "SUURFaG0p7"},
    }

    assert cleanup.classify_tag(
        "SUURFaG0p7",
        torrent_tags,
        torrent_tags,
        {"⏩转种"},
        set(),
    ) == "other"


def test_single_task_legacy_tag_without_anchor_requires_confirmation():
    """无业务锚点的单任务十位标签应进入人工确认而非自动删除。"""
    cleanup = _load_tag_cleanup()
    torrent_tags = {"qb-hash": {"任意标签", "SUURFaG0p7"}}

    assert cleanup.classify_tag(
        "SUURFaG0p7",
        ["qb-hash"],
        torrent_tags,
        {"⏩转种"},
        set(),
    ) == "legacy_candidate"
    assert cleanup.is_auto_removable("legacy_candidate") is False


def test_non_legacy_user_tag_remains_untouched():
    """任意标签旁的非十位普通标签不得被误判。"""
    cleanup = _load_tag_cleanup()
    torrent_tags = {"qb-hash": {"任意标签", "my-user-label"}}

    assert cleanup.classify_tag(
        "my-user-label",
        ["qb-hash"],
        torrent_tags,
        {"⏩转种"},
        set(),
    ) == "other"


def test_download_added_event_cleans_selected_source_and_target_downloaders():
    """下载新增事件应清理来源和目标 qBittorrent 的新临时标签。"""
    service = _load_site_tag("MoviePilot")
    qb1 = FakeQbittorrent([_event_torrent("h1", "MoviePilot,DML_TMP_source")])
    qb2 = FakeQbittorrent([_event_torrent("h2", "MoviePilot,DML_TMP_target")])
    plugin = EventPlugin({
        "QB1": SimpleNamespace(type="qbittorrent", instance=qb1),
        "QB2": SimpleNamespace(type="qbittorrent", instance=qb2),
    })

    source_result = service.cleanup_temporary_tags_for_event(
        plugin,
        SimpleNamespace(event_data={"downloader": "QB1", "hash": "h1"}),
    )
    target_result = service.cleanup_temporary_tags_for_event(
        plugin,
        SimpleNamespace(event_data={"downloader": "QB2", "hash": "h2"}),
    )

    assert source_result["removed"] == ["DML_TMP_source"]
    assert target_result["removed"] == ["DML_TMP_target"]
    assert qb1.torrents[0]["tags"] == "MoviePilot"
    assert qb2.torrents[0]["tags"] == "MoviePilot"


def test_download_added_event_cleans_new_legacy_random_tag():
    """下载新增事件应清理新任务上的旧式随机临时标签。"""
    service = _load_site_tag("MoviePilot")
    qb1 = FakeQbittorrent([_event_torrent("h1", "MoviePilot,o8higAGF9S")])
    plugin = EventPlugin({"QB1": SimpleNamespace(type="qbittorrent", instance=qb1)})

    result = service.cleanup_temporary_tags_for_event(
        plugin,
        SimpleNamespace(event_data={"downloader": "QB1", "hash": "h1"}),
    )

    assert result["removed"] == ["o8higAGF9S"]
    assert qb1.torrents[0]["tags"] == "MoviePilot"


def test_download_added_event_keeps_shared_legacy_tag_for_config_scan():
    """下载新增事件不得删除被多个任务共用的旧式标签。"""
    service = _load_site_tag("MoviePilot")
    qb1 = FakeQbittorrent([
        _event_torrent("h1", "MoviePilot,o8higAGF9S"),
        _event_torrent("h2", "MoviePilot,o8higAGF9S"),
    ])
    plugin = EventPlugin({"QB1": SimpleNamespace(type="qbittorrent", instance=qb1)})

    result = service.cleanup_temporary_tags_for_event(
        plugin,
        SimpleNamespace(event_data={"downloader": "QB1", "hash": "h1"}),
    )

    assert result["removed"] == []
    assert qb1.torrents[0]["tags"] == "MoviePilot,o8higAGF9S"
    assert qb1.remove_calls == []


def test_download_added_event_keeps_active_temporary_tag_until_confirmation():
    """下载新增事件不得抢先移除仍在等待 hash 确认的临时标签。"""
    service = _load_site_tag("MoviePilot")
    qb1 = FakeQbittorrent([_event_torrent("h1", "MoviePilot,DML_TMP_active")])
    plugin = EventPlugin({"QB1": SimpleNamespace(type="qbittorrent", instance=qb1)})
    plugin._active_temporary_tags.add("DML_TMP_active")

    result = service.cleanup_temporary_tags_for_event(
        plugin,
        SimpleNamespace(event_data={"downloader": "QB1", "hash": "h1"}),
    )

    assert result["removed"] == []
    assert qb1.torrents[0]["tags"] == "MoviePilot,DML_TMP_active"
    assert qb1.remove_calls == []


def test_download_added_event_ignores_unselected_downloader():
    """下载新增事件不得触碰转移配置之外的下载器。"""
    service = _load_site_tag("MoviePilot")
    qb3 = FakeQbittorrent([_event_torrent("h3", "MoviePilot,DML_TMP_other")])
    plugin = EventPlugin({"QB3": SimpleNamespace(type="qbittorrent", instance=qb3)})

    result = service.cleanup_temporary_tags_for_event(
        plugin,
        SimpleNamespace(event_data={"downloader": "QB3", "hash": "h3"}),
    )

    assert result["handled"] is False
    assert result["reason"] == "downloader_not_selected"
    assert qb3.remove_calls == []


def test_transmission_scan_groups_labels_and_auto_removes_only_temporary(monkeypatch):
    """TR 扫描读取 labels 字段，只自动移除明确临时标签。"""
    service = _load_site_tag("MoviePilot")
    transmission = FakeTransmission([
        _transmission_torrent("tr-1", ["DML_TMP_stale", "保种", "站点/Example"]),
        _transmission_torrent("tr-2", ["DML_TMP_active", "用户标签"]),
    ])
    plugin = EventPlugin({"TR": SimpleNamespace(type="transmission", instance=transmission)})
    plugin._active_temporary_tags.add("DML_TMP_active")

    result = service.scan_and_clean_tags(plugin, ["TR"])

    assert result["code"] == 0 and result["errors"] == []
    assert result["downloaders"][0]["task_count"] == 2
    assert {item["tag"] for item in result["downloaders"][0]["tags"]} == {
        "保种", "站点/Example", "DML_TMP_active", "用户标签",
    }
    assert result["auto_removed"][0]["tag"] == "DML_TMP_stale"
    assert transmission.torrents[0].labels == ["保种", "站点/Example"]
    assert transmission.torrents[1].labels == ["DML_TMP_active", "用户标签"]
    assert transmission.writes == [(["tr-1"], ["保种", "站点/Example"])]
    assert transmission.definition_calls == []


def test_transmission_manual_cleanup_preserves_other_labels():
    """人工确认只移除选中标签，保留任务上的其他 TR labels。"""
    service = _load_site_tag("MoviePilot")
    transmission = FakeTransmission([
        _transmission_torrent("tr-1", ["保种", "错误标签", "DML_TMP_active"]),
        _transmission_torrent("tr-2", ["保种", "其他标签"]),
    ])
    plugin = EventPlugin({"TR": SimpleNamespace(type="transmission", instance=transmission)})

    result = service.execute_tag_cleanup(plugin, [{
        "downloader": "TR", "tag": "错误标签", "hashes": ["tr-1"],
    }])

    assert result["code"] == 0
    assert result["removed"][0]["hashes"] == ["tr-1"]
    assert transmission.torrents[0].labels == ["保种", "DML_TMP_active"]
    assert transmission.torrents[1].labels == ["保种", "其他标签"]
    assert transmission.writes == [(["tr-1"], ["保种", "DML_TMP_active"])]
    assert transmission.definition_calls == []


def test_transmission_manual_cleanup_uses_only_confirmed_hashes_and_latest_labels():
    """只清理确认过的 hash，保留扫描后新增标签及新任务。"""
    service = _load_site_tag("MoviePilot")
    transmission = FakeTransmission([
        _transmission_torrent("tr-1", ["错误标签", "保种", "扫描后新增"]),
        _transmission_torrent("tr-2", ["错误标签", "新任务标签"]),
    ])
    plugin = EventPlugin({"TR": SimpleNamespace(type="transmission", instance=transmission)})

    result = service.execute_tag_cleanup(plugin, [{
        "downloader": "TR", "tag": "错误标签", "hashes": ["tr-1"],
    }])

    assert result["code"] == 0
    assert result["removed"][0]["hashes"] == ["tr-1"]
    assert transmission.torrents[0].labels == ["保种", "扫描后新增"]
    assert transmission.torrents[1].labels == ["错误标签", "新任务标签"]
    assert transmission.writes == [(["tr-1"], ["保种", "扫描后新增"])]


def test_transmission_manual_cleanup_skips_missing_confirmed_hash():
    """确认的任务已消失时作为 no-op，不因别的任务使用同标签而扩展清理范围。"""
    service = _load_site_tag("MoviePilot")
    transmission = FakeTransmission([
        _transmission_torrent("tr-new", ["错误标签", "新任务"]),
    ])
    plugin = EventPlugin({"TR": SimpleNamespace(type="transmission", instance=transmission)})

    result = service.execute_tag_cleanup(plugin, [{
        "downloader": "TR", "tag": "错误标签", "hashes": ["tr-gone"],
    }])

    assert result["code"] == 0
    assert result["removed"] == [] and result["failed"] == []
    assert result["skipped"][0]["hashes"] == ["tr-gone"]
    assert "无需清理" in result["msg"]
    assert transmission.torrents[0].labels == ["错误标签", "新任务"]
    assert transmission.writes == []


def test_transmission_scan_reports_missing_auto_cleanup_hash_as_skipped():
    """自动清理前任务消失时不计为已移除。"""
    service = _load_site_tag("MoviePilot")
    transmission = FakeTransmission([
        _transmission_torrent("tr-gone", ["DML_TMP_stale"]),
    ])

    def torrents_disappear_before_cleanup(ids=None):
        if ids is None:
            return [_transmission_torrent("tr-gone", ["DML_TMP_stale"])], None
        return [], None

    transmission.get_torrents = torrents_disappear_before_cleanup
    plugin = EventPlugin({"TR": SimpleNamespace(type="transmission", instance=transmission)})

    result = service.scan_and_clean_tags(plugin, ["TR"])

    assert result["code"] == 0
    assert result["auto_removed"] == []
    assert result["skipped"][0]["hashes"] == ["tr-gone"]
    assert transmission.writes == []


def test_transmission_cleanup_can_remove_last_task_label():
    """清掉 TR 任务最后一个标签时使用整体空 labels 更新，不碰全局定义。"""
    service = _load_site_tag("MoviePilot")
    transmission = FakeTransmission([_transmission_torrent("tr-1", ["旧标签"])])
    plugin = EventPlugin({"TR": SimpleNamespace(type="transmission", instance=transmission)})

    result = service.execute_tag_cleanup(plugin, [{
        "downloader": "TR", "tag": "旧标签", "hashes": ["tr-1"],
    }])

    assert result["code"] == 0
    assert transmission.torrents[0].labels == []
    assert transmission.writes == [(["tr-1"], [])]
    assert transmission.definition_calls == []


def test_frontend_preselects_only_legacy_candidates_for_confirmation():
    """V3 配置页应默认待清理疑似旧临时标签并保留其他标签。"""
    source = (
        PLUGIN_DIR / "frontend" / "src" / "components" / "Config.vue"
    ).read_text(encoding="utf-8")

    assert "item.kind !== 'legacy_candidate'" in source
    assert "legacy_candidate: { label: '疑似旧临时'" in source
    assert "{ key: 'tag_repair', title: '补全标签'" in source
    assert "tag_completion_scan" in source
    assert "tag_completion_execute" in source


def test_completion_scan_and_execute_restore_all_proven_tag_categories():
    """补全按 tracker、转移状态与 IYUU 历史还原缺失标签。"""
    service = _load_site_tag("MoviePilot")
    service.find_site_by_domain = lambda _domain: "彩虹岛"
    target = FakeQbittorrent([{
        "hash": "h1",
        "name": "Example.Release",
        "tags": "",
        "trackers": [{"url": "https://tracker.example/announce", "tier": 0}],
    }])
    source_service = SimpleNamespace(name="QB1", type="qbittorrent", instance=object())
    target_service = SimpleNamespace(name="QB2 display", type="qbittorrent", instance=target)
    data = {
        "QB1-h1": {
            "to_download": "QB2 display",
            "to_download_id": "h1",
            "transfer_state": "completed",
        },
        "iyuu_source_h1": "mother-hash",
        "iyuu_mother-hash": [{"downloader": "QB2 display", "torrents": ["h1"]}],
    }
    data_reads = []

    def get_data(key=None):
        data_reads.append(key)
        if key is None:
            return [
                SimpleNamespace(key=name, value=value) for name, value in data.items()
            ]
        return data.get(key)

    plugin = SimpleNamespace(
        _fromdownloader="QB1",
        _tracker_mappings={},
        _tag_siteprefix="🏠",
        _torrent_tags=["⏩转种"],
        _iyuu_labelsafterseed="已整理,辅种",
        service_info=lambda name: {"QB1": source_service, "QB2": target_service}.get(name),
        get_data=get_data,
    )

    scan = service.scan_tag_completion(plugin, ["QB2"])
    groups = scan["downloaders"][0]["tags"]
    assert data_reads == [None]
    assert {(item["kind"], item["tag"]) for item in groups} == {
        ("site", "🏠彩虹岛"),
        ("transfer", "⏩转种"),
        ("iyuu", "已整理"),
        ("iyuu", "辅种"),
    }

    repairs = [{
        "downloader": "QB2",
        "kind": item["kind"],
        "tag": item["tag"],
        "hashes": item["hashes"],
    } for item in groups]
    result = service.execute_tag_completion(plugin, repairs)
    assert data_reads == [None, None]
    assert result["code"] == 0
    assert set(target.torrents[0]["tags"].split(", ")) == {"🏠彩虹岛", "⏩转种", "已整理", "辅种"}

    repeated = service.execute_tag_completion(plugin, repairs)
    assert data_reads == [None, None, None]
    assert repeated["added"] == []
    assert repeated["skipped"][0]["message"] == "标签已存在"


def test_completion_scan_reads_trackers_once_per_torrent():
    """扫描复用同一份 tracker 结果计算站点标签与未识别计数。"""
    service = _load_site_tag("MoviePilot")
    service.find_site_by_domain = lambda _domain: "彩虹岛"
    target = FakeQbittorrent([{
        "hash": "h1",
        "name": "Example.Release",
        "tags": "",
        "trackers": ["https://tracker.example/announce"],
    }])
    tracker_reads = []
    service.get_tracker_urls = lambda torrent, _kind: tracker_reads.append(torrent["hash"]) or torrent["trackers"]
    plugin = SimpleNamespace(
        _fromdownloader="",
        _tracker_mappings={},
        _tag_siteprefix="🏠",
        _torrent_tags=[],
        _iyuu_labelsafterseed="",
        service_info=lambda name: SimpleNamespace(name=name, type="qbittorrent", instance=target),
    )

    result = service.scan_tag_completion(plugin, ["QB"])

    assert result["downloaders"][0]["tags"][0]["tag"] == "🏠彩虹岛"
    assert tracker_reads == ["h1"]


def test_completion_only_restores_proven_categories_and_preserves_transmission_labels():
    """无来源记录的任务不获转种/IYUU标签，TR 补站点标签保留已有 labels。"""
    service = _load_site_tag("MoviePilot")
    service.find_site_by_domain = lambda _domain: "彩虹岛"
    target = FakeTransmission([_transmission_torrent("h2", ["用户标签"])])
    target.torrents[0].trackers = [{"announce": "https://tracker.example/announce", "tier": 0}]
    target_service = SimpleNamespace(name="TR1", type="transmission", instance=target)
    source_service = SimpleNamespace(name="QB1", type="qbittorrent", instance=object())
    plugin = SimpleNamespace(
        _fromdownloader="QB1",
        _tracker_mappings={},
        _tag_siteprefix="🏠",
        _torrent_tags=["⏩转种"],
        _iyuu_labelsafterseed="已整理,辅种",
        service_info=lambda name: {"QB1": source_service, "TR1": target_service}.get(name),
        get_data=lambda key=None: (
            {} if key is None else None
        ),
    )

    scan = service.scan_tag_completion(plugin, ["TR1"])
    groups = scan["downloaders"][0]["tags"]
    assert [(item["kind"], item["tag"]) for item in groups] == [("site", "🏠彩虹岛")]
    result = service.execute_tag_completion(plugin, [{
        "downloader": "TR1",
        "kind": "site",
        "tag": "🏠彩虹岛",
        "hashes": ["h2"],
    }])

    assert result["code"] == 0
    assert set(target.torrents[0].labels) == {"用户标签", "🏠彩虹岛"}
