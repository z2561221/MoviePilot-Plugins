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
    torrent_adapter.get_hash = lambda torrent, _kind: torrent.get("hash")
    torrent_adapter.get_label = lambda torrent, _kind: torrent.get("tags", "")

    sys.modules.update({
        "app": app,
        "app.sdk": app_sdk,
        "app.sdk.config": app_sdk_config,
        "app.sdk.logging": app_sdk_logging,
        "downloadmanagerlocal.adapter.moviepilot": adapter,
        "downloadmanagerlocal.utils.tag_cleanup": cleanup,
        "downloadmanagerlocal.utils.torrent_adapter": torrent_adapter,
    })
    return importlib.import_module("downloadmanagerlocal.service.site_tag")


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


def test_frontend_preselects_only_legacy_candidates_for_confirmation():
    """V3 配置页应默认待清理疑似旧临时标签并保留其他标签。"""
    source = (
        PLUGIN_DIR / "frontend" / "src" / "components" / "Config.vue"
    ).read_text(encoding="utf-8")

    assert "item.kind !== 'legacy_candidate'" in source
    assert "legacy_candidate: { label: '疑似旧临时'" in source
