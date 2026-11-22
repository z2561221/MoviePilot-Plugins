from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace


PLUGIN_DIR = Path(
    os.environ.get("DOWNLOADMANAGERLOCAL_PLUGIN_DIR")
    or Path(__file__).resolve().parents[1]
)


def _load_tag_cleanup():
    """隔离加载 V3 标签归属判断工具。"""
    for name in list(sys.modules):
        if name == "downloadmanagerlocal" or name.startswith("downloadmanagerlocal."):
            sys.modules.pop(name)
    package = types.ModuleType("downloadmanagerlocal")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["downloadmanagerlocal"] = package
    return importlib.import_module("downloadmanagerlocal.utils.tag_cleanup")


def _load_site_tag(host_tag: str):
    """隔离加载站点标签服务并注入用户自定义宿主标签。"""
    cleanup = _load_tag_cleanup()

    app = types.ModuleType("app")
    app.__path__ = []
    app_sdk = types.ModuleType("app.sdk")
    app_sdk.__path__ = []
    app_sdk_config = types.ModuleType("app.sdk.config")
    app_sdk_config.settings = SimpleNamespace(TORRENT_TAG=host_tag)
    app_sdk_logging = types.ModuleType("app.sdk.logging")
    app_sdk_logging.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    adapter = types.ModuleType("downloadmanagerlocal.adapter.moviepilot")
    adapter.generate_random_tag = lambda length=10: "A" * length
    adapter.get_site_indexer = lambda *_args, **_kwargs: None
    adapter.get_url_domain = lambda value: value
    adapter.list_site_dicts = lambda: []
    torrent_adapter = types.ModuleType("downloadmanagerlocal.utils.torrent_adapter")

    def get_hash(torrent, kind):
        if isinstance(torrent, dict):
            return torrent.get("hash", "") if kind == "qbittorrent" else torrent.get("hashString", "")
        return getattr(torrent, "hashString", getattr(torrent, "hash_string", ""))

    def get_label(torrent, kind):
        if isinstance(torrent, dict):
            return torrent.get("tags", "") if kind == "qbittorrent" else torrent.get("labels", [])
        return getattr(torrent, "labels", [])

    torrent_adapter.get_hash = get_hash
    torrent_adapter.get_label = get_label

    stubs = {
        "app": app,
        "app.sdk": app_sdk,
        "app.sdk.config": app_sdk_config,
        "app.sdk.logging": app_sdk_logging,
        "downloadmanagerlocal.adapter.moviepilot": adapter,
        "downloadmanagerlocal.utils.tag_cleanup": cleanup,
        "downloadmanagerlocal.utils.torrent_adapter": torrent_adapter,
    }
    missing = object()
    previous = {name: sys.modules.get(name, missing) for name in stubs}
    sys.modules.update(stubs)
    try:
        return importlib.import_module("downloadmanagerlocal.service.site_tag")
    finally:
        for name, module in previous.items():
            if module is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


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
    cleanup = sys.modules["downloadmanagerlocal.utils.tag_cleanup"]
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
