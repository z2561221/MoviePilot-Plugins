"""站点目录优先级、边界及批次快照回归。"""

from types import SimpleNamespace
from unittest.mock import Mock

from app.plugins.downloadmanagerlocal.adapter import moviepilot
from app.plugins.downloadmanagerlocal.service import site_tag
from app.plugins.downloadmanagerlocal.service.config import DEFAULT_TRACKER_MAPPINGS
from app.plugins.downloadmanagerlocal.utils.tracker import parse_tracker_mappings
from app.plugins.downloadmanagerlocal.utils.tracker_directory import (
    build_directory,
    normalized_aliases,
    resolve_tracker,
)


def test_adapter_associates_template_aliases_with_local_site_names(monkeypatch):
    """模板的显示名不等于配置站点名；用 ID 关联，目录不泄露认证字段。"""
    monkeypatch.setattr(moviepilot, "list_builtin_sites", lambda: [
        SimpleNamespace(domain="frog.test", name="我的青蛙", url="https://www.frog.test/", cookie="private"),
    ])
    catalog = {"frog.test": {"id": "frog", "name": "模板名"}, "alias.test": {"id": "frog"},
               "child.frog.test": {"id": "independent", "name": "独立子站"}}
    monkeypatch.setattr(moviepilot, "SitesHelper", lambda: SimpleNamespace(get_indexsites=lambda: catalog))
    directory = moviepilot.load_tracker_directory()
    override = {"alias.test": "elsewhere.test", "child.frog.test": "frog.test"}
    assert resolve_tracker("tracker.alias.test", directory, override, override) == "我的青蛙"
    assert resolve_tracker("www.frog.test", directory, override, {}) == "我的青蛙"
    assert resolve_tracker("tracker.child.frog.test", directory, override, {}) is None
    assert resolve_tracker("not-frog.test", directory, {}, {}) is None


def test_fallback_only_for_unknown_hosts_and_never_chains():
    """原站优先；未知才用自定义、内置，且自定义失效不能偷偷改选内置。"""
    directory = {"original.test": "原站", "builtin.test": "内置目标", "custom.test": "自选目标"}
    builtin = {"original.test": "builtin.test", "tk.unknown.test": "builtin.test", "other.test": "builtin.test"}
    custom = normalized_aliases({"ORIGINAL.TEST.": "custom.test", "UNKNOWN.TEST:443": "custom.test"})
    assert resolve_tracker("original.test", directory, custom, builtin) == "原站"
    assert resolve_tracker("tk.unknown.test", directory, custom, builtin) == "自选目标"
    assert resolve_tracker("tk.unknown.test", directory, {}, builtin) == "内置目标"
    assert resolve_tracker("tk.unknown.test", directory, {"unknown.test": "other.test"}, builtin) is None


def test_conflicting_sites_are_not_a_mapping_miss():
    """相同模板绑定多站，或两个配置争用同一原域名，不能借兜底随意选站。"""
    catalog = {domain: {"id": "shared"} for domain in ("a.test", "b.test", "old.test")}
    rows = [("A", "a.test", None), ("B", "b.test", None), ("另一个 A", "a.test", None)]
    directory = build_directory(rows, catalog)
    for domain in ("a.test", "old.test"):
        assert resolve_tracker(domain, directory, {domain: "b.test"}, {}) is None
    assert resolve_tracker("b.test", directory, {}, {}) == "B"


def test_shared_parent_does_not_capture_independent_tracker():
    """动漫花园和 U2 同父域；只有 U2 已配置时其别名才能打上 U2 标签。"""
    sites = [("动漫花园", "dmhy.org", "https://share.dmhy.org/")]
    templates = {"dmhy.org": {"id": "dmhy"}, "u2.dmhy.org": {"id": "U2"}}
    builtin = parse_tracker_mappings(DEFAULT_TRACKER_MAPPINGS)
    directory = build_directory(sites, templates)
    assert resolve_tracker("share.dmhy.org", directory, {}, builtin) == "动漫花园"
    assert resolve_tracker("anime.dmhy.org", directory, {}, builtin) is None
    directory = build_directory([*sites, ("幼儿园", "u2.dmhy.org", None)], templates)
    assert resolve_tracker("anime.dmhy.org", directory, {}, builtin) == "幼儿园"


def test_labels_share_one_snapshot_per_batch_and_decline_conflicts(monkeypatch):
    """所有种子复用当前批目录；重新扫描则读取新目录，未知或冲突不打标签。"""
    plugin = SimpleNamespace(_tracker_mappings=parse_tracker_mappings(DEFAULT_TRACKER_MAPPINGS), _tag_siteprefix="🏠")
    snapshot = Mock(side_effect=[{"qingwapt.com": "青蛙", "pterclub.net": "猫站"}, {"qingwapt.com": "更名后"}])
    monkeypatch.setattr(site_tag, "load_tracker_directory", snapshot)
    cache = {}
    assert site_tag.official_site(plugin, ["tracker.qingwapt.org", "tracker.qingwapt.com"], cache) == "青蛙"
    assert site_tag._site_tag_for_trackers(plugin, ["tracker.qingwapt.org"], cache) == "🏠青蛙"
    for conflict in ("pterclub.net", "unsupported.test"):
        assert site_tag.official_site(plugin, ["tracker.qingwapt.org", conflict], cache) is None
        assert not site_tag._site_tag_for_trackers(plugin, [conflict, "tracker.qingwapt.org"], cache)
    snapshot.assert_called_once()
    assert site_tag.official_site(plugin, ["tracker.qingwapt.org"], {}) == "更名后"


def test_directory_errors_fail_closed(monkeypatch):
    """无法读取主程序时不通过别名或模板名生成虚假的站点归属。"""
    monkeypatch.setattr(site_tag, "load_tracker_directory", Mock(side_effect=RuntimeError))
    plugin = SimpleNamespace(_custom_tracker_mappings={"unknown.test": "known.test"})
    assert site_tag.official_site(plugin, ["unknown.test"], {}) is None
