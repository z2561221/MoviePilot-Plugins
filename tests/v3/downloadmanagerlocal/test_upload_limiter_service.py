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


def _load(module_name: str):
    """加载不执行插件入口的上传限速服务模块。"""
    for name in list(sys.modules):
        if name == "downloadmanagerlocal" or name.startswith("downloadmanagerlocal."):
            sys.modules.pop(name)
    package = types.ModuleType("downloadmanagerlocal")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["downloadmanagerlocal"] = package
    return importlib.import_module(f"downloadmanagerlocal.{module_name}")


class FakeQbClient:
    """提供可变 qB 全局与单种限速状态。"""

    def __init__(self, torrents):
        """保存任务并初始化全局限速。"""
        self.torrents = torrents
        self.transfer = SimpleNamespace(upload_limit=0, download_limit=888888)
        self.preferences = {"alt_up_limit": 0}
        self.global_calls = []
        self.torrent_calls = []

    def app_preferences(self):
        """返回 qB 偏好。"""
        return dict(self.preferences)

    def app_set_preferences(self, payload):
        """记录并应用 qB 备用限速。"""
        self.global_calls.append(dict(payload))
        self.preferences.update(payload)

    def torrents_set_upload_limit(self, limit, torrent_hashes):
        """记录并应用 qB 单种限速。"""
        self.torrent_calls.append((torrent_hashes, limit))
        for torrent in self.torrents:
            if torrent.get("hash", "").lower() == str(torrent_hashes).lower():
                torrent["up_limit"] = limit


class FakeQbInstance:
    """提供 MoviePilot qB wrapper 最小接口。"""

    def __init__(self, torrents):
        """创建底层 qB 客户端。"""
        self.qbc = FakeQbClient(torrents)

    def get_torrents(self):
        """返回当前 qB 任务。"""
        return list(self.qbc.torrents), False


class FakeTransmissionClient:
    """提供可变 Transmission Session 与任务状态。"""

    def __init__(self, torrents):
        """保存任务并初始化 Session。"""
        self.torrents = torrents
        self.session = {
            "speed_limit_up": 0,
            "speed_limit_up_enabled": False,
            "speed_limit_down": 777,
            "speed_limit_down_enabled": False,
        }
        self.torrent_calls = []

    def get_session(self):
        """返回 Session。"""
        return dict(self.session)

    def set_session(self, **kwargs):
        """应用 Session 更新。"""
        self.session.update(kwargs)

    def get_torrents(self, arguments):
        """返回当前 Transmission 任务。"""
        del arguments
        return list(self.torrents)

    def change_torrent(self, **kwargs):
        """记录并应用单种限速。"""
        self.torrent_calls.append(dict(kwargs))
        target = str(kwargs.get("ids") or "").lower()
        for torrent in self.torrents:
            if str(torrent.hashString).lower() == target:
                torrent.uploadLimit = kwargs.get("uploadLimit", torrent.uploadLimit)
                torrent.uploadLimited = kwargs.get("uploadLimited", torrent.uploadLimited)


class FakeTransmissionInstance:
    """提供 MoviePilot Transmission wrapper 最小接口。"""

    def __init__(self, torrents):
        """创建底层 Transmission 客户端。"""
        self.trc = FakeTransmissionClient(torrents)


class FakePlugin:
    """提供上传限速服务所需的最小插件接口。"""

    _enabled = True
    _upload_limit_enabled = True
    _upload_limit_grace_minutes = 30
    _tag_siteprefix = "🏠"

    def __init__(self, services, selected, limits, rules=None, data=None):
        """保存 fake 下载器服务和配置。"""
        self.services = services
        self._upload_limit_downloaders = list(selected)
        self._upload_limit_downloader_limits_kib = dict(limits)
        self._upload_limit_site_rules = dict(rules or {})
        self.data = data if data is not None else {}
        self._upload_limit_state = None
        self._upload_limit_state_error = ""
        self._upload_limit_cycle_lock = None
        self.messages = []
        self.config = {
            "upload_limit_enabled": True,
            "upload_limit_downloaders": list(selected),
            "upload_limit_downloader_limits_kib": dict(limits),
            "upload_limit_site_rules": dict(rules or {}),
            "upload_limit_grace_minutes": 30,
        }

    def service_info(self, name):
        """按名称返回 fake 下载器服务。"""
        return self.services.get(name)

    def get_data(self, key):
        """读取内存插件数据。"""
        return self.data.get(key)

    def save_data(self, key, value):
        """保存内存插件数据。"""
        self.data[key] = value

    def post_message(self, **kwargs):
        """记录异常通知。"""
        self.messages.append(kwargs)

    def get_config(self):
        """返回 fake 插件配置。"""
        return dict(self.config)

    def update_config(self, config, plugin_id=None):
        """保存 fake 插件配置。"""
        del plugin_id
        self.config = dict(config)
        return True


def qb_torrent(
    torrent_hash,
    site,
    *,
    added=100,
    completed=120,
    rate=0,
    limit_kib=0,
    peers=1,
):
    """构造已完成 qB 任务。"""
    return {
        "hash": torrent_hash,
        "name": torrent_hash,
        "tags": f"🏠{site}" if site else "",
        "state": "uploading",
        "progress": 1,
        "total_size": 1024,
        "amount_left": 0,
        "added_on": added,
        "completion_on": completed,
        "upspeed": rate,
        "num_leechs": peers,
        "up_limit": limit_kib * 1024,
    }


def tr_torrent(torrent_hash, site, *, rate=0, limit_kib=0, peers=1):
    """构造已完成 Transmission 任务。"""
    return SimpleNamespace(
        hashString=torrent_hash,
        name=torrent_hash,
        labels=[f"🏠{site}"] if site else [],
        status="seeding",
        totalSize=1024,
        percentDone=1,
        leftUntilDone=0,
        addedDate=100,
        doneDate=120,
        rateUpload=rate,
        peersConnected=peers,
        peersGettingFromUs=peers,
        uploadLimit=limit_kib,
        uploadLimited=limit_kib > 0,
    )


def test_scanned_empty_site_limits_only_apply_qb_global_cap():
    """站点为空或零值时只写 qB 全局上限，不得写任何单种限速。"""
    limiter = _load("service.upload_limiter")
    torrents = [
        qb_torrent("a", "A", rate=70 * 1024),
        qb_torrent("b", "B", rate=20 * 1024),
    ]
    instance = FakeQbInstance(torrents)
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 122},
        {"A": {"limit_kib": 0}, "B": {"limit_kib": 0}},
    )

    result = limiter.run_upload_limit_cycle(plugin, now=1000)

    assert result["mode"] == "downloader_only"
    assert result["upload_rate_bps"] == 90 * 1024
    assert result["sites"] == []
    assert instance.qbc.transfer.upload_limit == 122 * 1024
    assert instance.qbc.preferences["alt_up_limit"] == 122 * 1024
    assert instance.qbc.torrent_calls == []
    assert all(torrent["up_limit"] == 0 for torrent in torrents)


def test_positive_site_limit_manages_stock_without_priority_or_grace():
    """正数站点上限应立即接管存量任务并限制该站点合计速度。"""
    limiter = _load("service.upload_limiter")
    torrents = [qb_torrent("a", "A"), qb_torrent("b", "A")]
    instance = FakeQbInstance(torrents)
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 100},
        {"A": {"limit_kib": 20}},
    )

    result = limiter.run_upload_limit_cycle(plugin, now=1000)

    assert result["mode"] == "site_policy"
    assert result["managed_torrents"] == 2
    assert result["grace_torrents"] == 0
    assert sum(torrent["up_limit"] for torrent in torrents) == 20 * 1024
    assert result["sites"] == [{
        "key": "A",
        "name": "A",
        "limit_kib": 20,
        "allocated_kib": 20,
        "upload_rate_bps": 0,
        "torrent_count": 2,
        "uploading_torrents": 0,
        "probing_torrents": 2,
        "protected_torrents": 0,
        "downloaders": ["QB2"],
    }]


def test_unlimited_site_is_not_managed_but_counts_in_realtime_rate():
    """空上限站点不得被单种接管，但其实时上传应计入下载器总速率。"""
    limiter = _load("service.upload_limiter")
    torrents = [
        qb_torrent("limited", "A", rate=5 * 1024),
        qb_torrent("unlimited", "B", rate=80 * 1024),
    ]
    instance = FakeQbInstance(torrents)
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 122},
        {"A": {"limit_kib": 20}, "B": {"limit_kib": 0}},
    )

    result = limiter.run_upload_limit_cycle(plugin, now=1000)

    assert result["managed_torrents"] == 1
    assert result["upload_rate_bps"] == 85 * 1024
    assert result["downloaders"][0]["upload_rate_bps"] == 85 * 1024
    assert torrents[0]["up_limit"] == 20 * 1024
    assert torrents[1]["up_limit"] == 0
    assert [call[0] for call in instance.qbc.torrent_calls] == ["limited"]


def test_changing_positive_site_limit_to_zero_restores_original_torrent_limit():
    """站点上限改为零时恢复原始单种设置，并继续保持 qB 全局上限。"""
    limiter = _load("service.upload_limiter")
    torrents = [qb_torrent("seed", "A", limit_kib=5)]
    instance = FakeQbInstance(torrents)
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 120},
        {"A": {"limit_kib": 20}},
    )
    limiter.run_upload_limit_cycle(plugin, now=1000)
    assert torrents[0]["up_limit"] == 20 * 1024

    plugin._upload_limit_site_rules = {"A": {"limit_kib": 0}}
    result = limiter.run_upload_limit_cycle(plugin, now=1030)

    assert result["mode"] == "downloader_only"
    assert instance.qbc.transfer.upload_limit == 120 * 1024
    assert torrents[0]["up_limit"] == 5 * 1024
    assert plugin.data["upload_limit_state"]["torrents"] == {}


def test_manual_torrent_change_is_preserved_when_site_limit_is_cleared():
    """用户手工修改单种限速后，清空站点上限不得覆盖该人工值。"""
    limiter = _load("service.upload_limiter")
    torrents = [qb_torrent("seed", "A", limit_kib=5)]
    instance = FakeQbInstance(torrents)
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 120},
        {"A": {"limit_kib": 20}},
    )
    limiter.run_upload_limit_cycle(plugin, now=1000)
    torrents[0]["up_limit"] = 7 * 1024

    plugin._upload_limit_site_rules = {"A": {"limit_kib": 0}}
    limiter.run_upload_limit_cycle(plugin, now=1030)

    assert torrents[0]["up_limit"] == 7 * 1024
    assert plugin.data["upload_limit_state"]["torrents"] == {}


def test_new_limited_site_torrent_uses_absolute_grace_then_joins_pool():
    """正数受限站点的新任务应经过绝对宽限期后再进入站点池。"""
    limiter = _load("service.upload_limiter")
    torrents = [qb_torrent("stock", "A")]
    instance = FakeQbInstance(torrents)
    data = {}
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 100},
        {"A": {"limit_kib": 50}},
        data=data,
    )
    limiter.run_upload_limit_cycle(plugin, now=1000)
    torrents.append(qb_torrent("new", "A", added=1100, completed=1100))

    grace = limiter.run_upload_limit_cycle(plugin, now=1100)

    assert grace["managed_torrents"] == 1
    assert grace["grace_torrents"] == 1
    assert data["upload_limit_state"]["torrents"]["QB2:new"]["grace_until"] == 2900
    assert not any(call[0] == "new" for call in instance.qbc.torrent_calls)

    after = limiter.run_upload_limit_cycle(plugin, now=3000)
    assert after["managed_torrents"] == 2
    assert after["grace_torrents"] == 0
    assert any(call[0] == "new" for call in instance.qbc.torrent_calls)


def test_site_limit_is_shared_between_qb_and_transmission():
    """同一站点合计上限应跨 qB 与 Transmission 共享。"""
    limiter = _load("service.upload_limiter")
    qb_items = [qb_torrent("qb-site", "A")]
    tr_items = [tr_torrent("tr-site", "A")]
    qb = FakeQbInstance(qb_items)
    tr = FakeTransmissionInstance(tr_items)
    plugin = FakePlugin(
        {
            "QB": SimpleNamespace(type="qbittorrent", instance=qb),
            "TR": SimpleNamespace(type="transmission", instance=tr),
        },
        ["QB", "TR"],
        {"QB": 100, "TR": 100},
        {"A": {"limit_kib": 20}},
    )

    result = limiter.run_upload_limit_cycle(plugin, now=1000)

    assert result["sites"][0]["limit_kib"] == 20
    assert result["sites"][0]["allocated_kib"] == 20
    assert qb_items[0]["up_limit"] + tr_items[0].uploadLimit * 1024 == 20 * 1024
    assert tr.trc.session["speed_limit_up"] == 100
    assert tr.trc.session["speed_limit_down"] == 777


def test_unknown_empty_or_multiple_site_labels_remain_unlimited():
    """未配置、无标签或多站点标签任务均不得进入受限站点池。"""
    limiter = _load("service.upload_limiter")
    torrents = [
        qb_torrent("unknown", "Unknown"),
        qb_torrent("empty", ""),
        qb_torrent("multiple", "A"),
    ]
    torrents[-1]["tags"] = "🏠A,🏠B"
    instance = FakeQbInstance(torrents)
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 90},
        {"A": {"limit_kib": 10}},
    )

    result = limiter.run_upload_limit_cycle(plugin, now=1000)

    assert result["mode"] == "site_policy"
    assert result["managed_torrents"] == 0
    assert result["sites"] == []
    assert instance.qbc.torrent_calls == []


def test_persisting_only_empty_limits_resets_site_management_runtime():
    """保存空上限站点时应清除旧探测状态并移除旧优先级字段。"""
    limiter = _load("service.upload_limiter")
    plugin = FakePlugin(
        {},
        [],
        {},
        {"A": {"priority": "high", "limit_kib": 20}},
        data={
            "upload_limit_state": {
                "schema_version": 1,
                "management_active": True,
                "cycle": 8,
                "downloaders": {
                    "QB2": {
                        "initial_scan_complete": True,
                        "per_torrent_management_active": True,
                        "auto_probe_count": 12,
                        "last_probe_keys": ["QB2:old"],
                    },
                },
                "torrents": {"QB2:old": {"downloader_id": "QB2"}},
                "failures": {},
                "last_summary": {},
            },
        },
    )

    rules = limiter.persist_upload_limit_site_rules(
        plugin,
        {"A": {"priority": "low", "limit_kib": 0}},
    )

    assert rules == {"A": {"limit_kib": 0}}
    assert plugin.config["upload_limit_site_rules"] == rules
    entry = plugin.data["upload_limit_state"]["downloaders"]["QB2"]
    assert entry["initial_scan_complete"] is False
    assert entry["per_torrent_management_active"] is False
    assert "auto_probe_count" not in entry
    assert "last_probe_keys" not in entry


def test_reenabling_positive_site_limit_rescans_stock_without_grace():
    """从空上限改为正数时，现有任务按存量立即进入站点池。"""
    limiter = _load("service.upload_limiter")
    torrents = [qb_torrent(f"old-{index}", "A", peers=1) for index in range(4)]
    instance = FakeQbInstance(torrents)
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 122},
        {"A": {"limit_kib": 0}},
    )
    limiter.run_upload_limit_cycle(plugin, now=1000)

    limiter.persist_upload_limit_site_rules(plugin, {"A": {"limit_kib": 40}})
    result = limiter.run_upload_limit_cycle(plugin, now=1030)

    assert result["mode"] == "site_policy"
    assert result["managed_torrents"] == 4
    assert result["grace_torrents"] == 0
    assert result["sites"][0]["limit_kib"] == 40


def test_disabling_upload_limit_restores_global_and_torrent_settings():
    """停用上传限速应恢复接管前的 qB 全局与单种上传设置。"""
    limiter = _load("service.upload_limiter")
    torrents = [qb_torrent("seed", "A", limit_kib=5)]
    instance = FakeQbInstance(torrents)
    instance.qbc.transfer.upload_limit = 80 * 1024
    instance.qbc.preferences["alt_up_limit"] = 70 * 1024
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 120},
        {"A": {"limit_kib": 20}},
    )
    limiter.run_upload_limit_cycle(plugin, now=1000)

    plugin._upload_limit_enabled = False
    restored = limiter.restore_upload_limits(plugin)

    assert restored["code"] == 0
    assert instance.qbc.transfer.upload_limit == 80 * 1024
    assert instance.qbc.preferences["alt_up_limit"] == 70 * 1024
    assert torrents[0]["up_limit"] == 5 * 1024
    assert plugin.data["upload_limit_state"]["management_active"] is False


def test_disabled_status_clears_stale_runtime_metrics():
    """上传限速停用后不得继续展示上一周期的运行指标。"""
    limiter = _load("service.upload_limiter")
    plugin = FakePlugin({}, ["QB2"], {"QB2": 120})
    plugin._upload_limit_enabled = False
    state = {
        "management_active": True,
        "cycle": 8,
        "last_run_at": 1000,
        "last_summary": {
            "service_status": "running",
            "downloaders": [{"id": "QB2", "upload_rate_bps": 80 * 1024}],
            "sites": [{"name": "A", "limit_kib": 20}],
            "errors": ["old error"],
            "managed_torrents": 5,
            "grace_torrents": 2,
            "uploading_torrents": 4,
            "probing_torrents": 3,
            "protected_torrents": 1,
            "upload_rate_bps": 80 * 1024,
            "allocated_kib": 100,
        },
    }

    result = limiter.get_upload_limit_status(plugin, state=state)

    assert result["enabled"] is False
    assert result["active"] is False
    assert result["service_status"] == "disabled"
    assert result["selected_downloaders"] == []
    assert result["downloaders"] == []
    assert result["sites"] == []
    assert result["errors"] == []
    for key in (
        "managed_torrents",
        "grace_torrents",
        "uploading_torrents",
        "probing_torrents",
        "protected_torrents",
        "upload_rate_bps",
        "allocated_kib",
    ):
        assert result[key] == 0
