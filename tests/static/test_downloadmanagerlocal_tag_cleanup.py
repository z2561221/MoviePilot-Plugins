from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"


def _load_module(name: str, path: Path):
    """按指定模块名加载源码文件。"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_tag_cleanup_service():
    """在最小桩环境中加载站点标签服务。"""
    package = types.ModuleType("downloadmanagerlocal")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["downloadmanagerlocal"] = package
    for subpackage in ["adapter", "utils", "service"]:
        module = types.ModuleType(f"downloadmanagerlocal.{subpackage}")
        module.__path__ = [str(PLUGIN_DIR / subpackage)]
        sys.modules[f"downloadmanagerlocal.{subpackage}"] = module

    logger = types.SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)
    app_module = types.ModuleType("app")
    app_log_module = types.ModuleType("app.log")
    app_log_module.logger = logger
    sys.modules["app"] = app_module
    sys.modules["app.log"] = app_log_module

    adapter = types.ModuleType("downloadmanagerlocal.adapter.moviepilot")
    adapter.generate_random_tag = lambda length=10: "X" * length
    adapter.get_site_indexer = lambda domain: None
    adapter.get_url_domain = lambda value: value
    adapter.get_user_sites = lambda: {}
    sys.modules[adapter.__name__] = adapter

    _load_module("downloadmanagerlocal.utils.tag_cleanup", PLUGIN_DIR / "utils" / "tag_cleanup.py")
    _load_module("downloadmanagerlocal.utils.torrent_adapter", PLUGIN_DIR / "utils" / "torrent_adapter.py")
    return _load_module("downloadmanagerlocal.service.site_tag", PLUGIN_DIR / "service" / "site_tag.py")


class FakeQbittorrent:
    """模拟标签读写所需的 qBittorrent 接口。"""

    def __init__(self, torrents: list[dict]):
        self.torrents = torrents
        self.remove_calls = []
        self.delete_calls = []

    def get_torrents(self, ids=None):
        """返回全部任务或指定 hash 的任务。"""
        if not ids:
            return list(self.torrents), False
        hash_set = set(ids if isinstance(ids, list) else [ids])
        return [item for item in self.torrents if item.get("hash") in hash_set], False

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
        """记录空标签定义删除调用。"""
        self.delete_calls.append((ids, tag))
        return True


class FakePlugin:
    """模拟下载中心标签清理所需状态。"""

    _torrent_tags = ["⏩转种"]
    _iyuu_labelsafterseed = "已整理,辅种"
    _tag_siteprefix = "🏠"

    def __init__(self, downloader):
        self.downloader = downloader
        self._active_temporary_tags = set()

    def service_info(self, name):
        """返回测试下载器服务。"""
        if name != "QB1":
            return None
        return types.SimpleNamespace(type="qbittorrent", instance=self.downloader)


def _torrent(hash_value: str, name: str, tags: str) -> dict:
    """构造 qBittorrent 任务字典。"""
    return {"hash": hash_value, "name": name, "tags": tags}


def test_tag_classifier_requires_owned_prefix_or_legacy_business_anchor():
    utils = _load_module("tag_cleanup_utils", PLUGIN_DIR / "utils" / "tag_cleanup.py")
    torrent_tags = {
        "h1": {"DML_TMP_abcdefghij", "⏩转种"},
        "h2": {"Abc123XyZ9", "已整理"},
        "h3": {"Random1234", "用户标签"},
    }

    assert utils.classify_tag("DML_TMP_abcdefghij", ["h1"], torrent_tags, {"⏩转种"}, set()) == "temporary"
    assert utils.classify_tag("DML_TMP_abcdefghij", ["h1"], torrent_tags, {"⏩转种"}, {"DML_TMP_abcdefghij"}) == "active_temporary"
    assert utils.classify_tag("Abc123XyZ9", ["h2"], torrent_tags, {"已整理"}, set()) == "legacy_temporary"
    assert utils.classify_tag("Random1234", ["h3"], torrent_tags, {"已整理"}, set()) == "other"


def test_scan_auto_removes_owned_and_high_confidence_legacy_temp_tags():
    service = _load_tag_cleanup_service()
    downloader = FakeQbittorrent([
        _torrent("h1", "转种任务", "DML_TMP_abcdefghij,⏩转种,🏠站点A"),
        _torrent("h2", "辅种任务", "Abc123XyZ9,已整理,辅种,TrackerError"),
        _torrent("h3", "普通任务", "Random1234,用户标签"),
    ])
    plugin = FakePlugin(downloader)

    result = service.scan_and_clean_tags(plugin, ["QB1"])

    assert result["code"] == 0
    assert {item["tag"] for item in result["auto_removed"]} == {"DML_TMP_abcdefghij", "Abc123XyZ9"}
    remaining = {item["tag"] for item in result["downloaders"][0]["tags"]}
    assert remaining == {"⏩转种", "🏠站点A", "已整理", "辅种", "TrackerError", "Random1234", "用户标签"}
    assert {tag for _, tag in downloader.delete_calls} == {"DML_TMP_abcdefghij", "Abc123XyZ9"}


def test_scan_never_removes_active_temporary_tag():
    service = _load_tag_cleanup_service()
    downloader = FakeQbittorrent([_torrent("h1", "活动任务", "DML_TMP_abcdefghij,⏩转种")])
    plugin = FakePlugin(downloader)
    plugin._active_temporary_tags.add("DML_TMP_abcdefghij")

    result = service.scan_and_clean_tags(plugin, ["QB1"])

    assert result["auto_removed"] == []
    tag = next(item for item in result["downloaders"][0]["tags"] if item["tag"] == "DML_TMP_abcdefghij")
    assert tag["kind"] == "active_temporary"
    assert downloader.remove_calls == []


def test_confirmed_task_releases_prefixed_temporary_tag_immediately():
    service = _load_tag_cleanup_service()
    downloader = FakeQbittorrent([_torrent("h1", "新任务", "DML_TMP_XXXXXXXXXX,⏩转种")])
    plugin = FakePlugin(downloader)

    tag = service.create_temporary_tag(plugin)
    released = service.release_temporary_tag(plugin, downloader, "h1", tag, "测试")

    assert tag == "DML_TMP_XXXXXXXXXX"
    assert released is True
    assert tag not in plugin._active_temporary_tags
    assert downloader.remove_calls == [(["h1"], tag)]
    assert downloader.delete_calls == [("h1", tag)]


def test_manual_cleanup_only_removes_hashes_from_scan_snapshot():
    service = _load_tag_cleanup_service()
    downloader = FakeQbittorrent([
        _torrent("h1", "旧任务一", "TrackerError"),
        _torrent("h2", "旧任务二", "TrackerError"),
    ])
    plugin = FakePlugin(downloader)
    scan = service.scan_and_clean_tags(plugin, ["QB1"])
    snapshot = next(item for item in scan["downloaders"][0]["tags"] if item["tag"] == "TrackerError")
    downloader.torrents.append(_torrent("h3", "扫描后新增任务", "TrackerError"))

    result = service.execute_tag_cleanup(plugin, [{
        "downloader": "QB1",
        "tag": "TrackerError",
        "hashes": snapshot["hashes"],
    }])

    assert result["code"] == 0
    assert result["removed"][0]["removed"] == 2
    assert result["removed"][0]["definition_deleted"] is False
    assert downloader.torrents[-1]["tags"] == "TrackerError"
    assert downloader.delete_calls == []


def test_transfer_and_iyuu_paths_release_prefixed_temporary_tags():
    transfer_source = (PLUGIN_DIR / "service" / "transfer.py").read_text(encoding="utf-8")
    iyuu_source = (PLUGIN_DIR / "service" / "iyuu.py").read_text(encoding="utf-8")

    for source in [transfer_source, iyuu_source]:
        assert "create_temporary_tag(plugin)" in source
        assert "release_temporary_tag(" in source
        assert "generate_random_tag(10)" not in source
