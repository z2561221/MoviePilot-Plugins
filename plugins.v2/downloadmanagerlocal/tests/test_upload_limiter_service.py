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
        self.session_calls = []
        self.torrent_calls = []

    def get_session(self):
        """返回 Session。"""
        return dict(self.session)

    def set_session(self, **kwargs):
        """记录并应用 Session 更新。"""
        self.session_calls.append(dict(kwargs))
        self.session.update(kwargs)

    def get_torrents(self, arguments):
        """返回当前 Transmission 任务。"""
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


def test_first_activation_treats_existing_torrents_as_stock_and_applies_priority():
    """首次启用应立即管理存量任务，不给宽限，并按高低 4:1 分配。"""
    limiter = _load("service.upload_limiter")
    torrents = [qb_torrent("high", "A"), qb_torrent("low", "B")]
    instance = FakeQbInstance(torrents)
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 100},
        {
            "A": {"priority": "high", "limit_kib": 0},
            "B": {"priority": "low", "limit_kib": 0},
        },
    )

    result = limiter.run_upload_limit_cycle(plugin, now=1000)
    state = plugin.data["upload_limit_state"]

    assert result["service_status"] == "running"
    assert result["managed_torrents"] == 2
    assert result["grace_torrents"] == 0
    assert instance.qbc.transfer.upload_limit == 100 * 1024
    assert instance.qbc.preferences["alt_up_limit"] == 100 * 1024
    assert torrents[0]["up_limit"] == 80 * 1024
    assert torrents[1]["up_limit"] == 20 * 1024
    assert state["torrents"]["QB2:high"]["grace_until"] == 0
    assert state["torrents"]["QB2:low"]["grace_until"] == 0


def test_new_completed_torrent_uses_absolute_thirty_minute_grace_then_joins_pool():
    """启用后新增完成任务应保持绝对 30 分钟宽限，重启语义不重置。"""
    limiter = _load("service.upload_limiter")
    torrents = [qb_torrent("stock", "A")]
    instance = FakeQbInstance(torrents)
    data = {}
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 100},
        {"A": {"priority": "medium", "limit_kib": 0}},
        data=data,
    )
    limiter.run_upload_limit_cycle(plugin, now=1000)
    torrents.append(qb_torrent("new", "A", added=1100, completed=1100))

    grace = limiter.run_upload_limit_cycle(plugin, now=1100)
    state = data["upload_limit_state"]

    assert grace["managed_torrents"] == 1
    assert grace["grace_torrents"] == 1
    assert state["torrents"]["QB2:new"]["grace_until"] == 2900
    assert not any(call[0] == "new" for call in instance.qbc.torrent_calls)

    reloaded = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 100},
        {"A": {"priority": "medium", "limit_kib": 0}},
        data=data,
    )
    after = limiter.run_upload_limit_cycle(reloaded, now=3000)

    assert after["managed_torrents"] == 2
    assert after["grace_torrents"] == 0
    assert any(call[0] == "new" for call in instance.qbc.torrent_calls)


def test_site_hard_limit_is_shared_between_qb_and_transmission_in_real_cycle():
    """协调器应把同站点跨 qB/TR 的常规池总额度限制在共享硬上限内。"""
    limiter = _load("service.upload_limiter")
    qb_items = [qb_torrent("qb-site", "A"), qb_torrent("qb-default", "")]
    tr_items = [tr_torrent("tr-site", "A"), tr_torrent("tr-default", "")]
    qb = FakeQbInstance(qb_items)
    tr = FakeTransmissionInstance(tr_items)
    plugin = FakePlugin(
        {
            "QB": SimpleNamespace(type="qbittorrent", instance=qb),
            "TR": SimpleNamespace(type="transmission", instance=tr),
        },
        ["QB", "TR"],
        {"QB": 100, "TR": 100},
        {"A": {"priority": "high", "limit_kib": 20}},
    )

    result = limiter.run_upload_limit_cycle(plugin, now=1000)
    sites = {item["key"]: item for item in result["sites"]}

    assert sites["A"]["allocated_kib"] == 20
    assert sites["A"]["hard_limit_kib"] == 20
    assert sum(item["allocated_kib"] for item in result["downloaders"]) == 200
    assert tr.trc.session["speed_limit_up"] == 100
    assert tr.trc.session["speed_limit_down"] == 777


def test_manual_changes_become_restore_baseline_but_plugin_reasserts_while_enabled():
    """运行期以插件分配为准，用户手工改值应成为停用时的新恢复基线。"""
    limiter = _load("service.upload_limiter")
    torrents = [qb_torrent("seed", "A", limit_kib=10)]
    instance = FakeQbInstance(torrents)
    instance.qbc.transfer.upload_limit = 20 * 1024
    instance.qbc.preferences["alt_up_limit"] = 30 * 1024
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 100},
        {"A": {"priority": "medium", "limit_kib": 0}},
    )
    limiter.run_upload_limit_cycle(plugin, now=1000)

    instance.qbc.transfer.upload_limit = 7 * 1024
    instance.qbc.preferences["alt_up_limit"] = 8 * 1024
    torrents[0]["up_limit"] = 5 * 1024
    limiter.run_upload_limit_cycle(plugin, now=1030)

    assert instance.qbc.transfer.upload_limit == 100 * 1024
    assert torrents[0]["up_limit"] == 100 * 1024

    plugin._upload_limit_enabled = False
    restored = limiter.restore_upload_limits(plugin)

    assert restored["code"] == 0
    assert instance.qbc.transfer.upload_limit == 7 * 1024
    assert instance.qbc.preferences["alt_up_limit"] == 8 * 1024
    assert torrents[0]["up_limit"] == 5 * 1024
    assert plugin.data["upload_limit_state"]["management_active"] is False


def test_active_upload_keeps_capacity_and_only_two_idle_peer_tasks_probe():
    """活跃任务保留主额度，每个下载器每轮最多放行两个待探测任务。"""
    limiter = _load("service.upload_limiter")
    torrents = [
        qb_torrent("active", "A", rate=80 * 1024, peers=1),
        qb_torrent("probe-a", "A", peers=1),
        qb_torrent("probe-b", "A", peers=1),
        qb_torrent("probe-c", "A", peers=1),
    ]
    instance = FakeQbInstance(torrents)
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 120},
        {"A": {"priority": "medium", "limit_kib": 0}},
    )

    result = limiter.run_upload_limit_cycle(plugin, now=1000)

    assert torrents[0]["up_limit"] == 104 * 1024
    assert torrents[1]["up_limit"] == 8 * 1024
    assert torrents[2]["up_limit"] == 8 * 1024
    assert torrents[3]["up_limit"] == 1
    assert result["uploading_torrents"] == 1
    assert result["probing_torrents"] == 2
    assert result["protected_torrents"] == 1


def test_probe_slots_are_global_per_downloader_across_sites():
    """多个站点候选也只能共享下载器的两个探测槽。"""
    limiter = _load("service.upload_limiter")
    torrents = [
        qb_torrent("active", "Active", rate=80 * 1024, peers=1),
        qb_torrent("high-a", "HighA", peers=1),
        qb_torrent("high-b", "HighB", peers=1),
        qb_torrent("medium", "Medium", peers=1),
        qb_torrent("low", "Low", peers=1),
    ]
    instance = FakeQbInstance(torrents)
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 122},
        {
            "Active": {"priority": "medium", "limit_kib": 0},
            "HighA": {"priority": "high", "limit_kib": 0},
            "HighB": {"priority": "high", "limit_kib": 0},
            "Medium": {"priority": "medium", "limit_kib": 0},
            "Low": {"priority": "low", "limit_kib": 0},
        },
    )

    result = limiter.run_upload_limit_cycle(plugin, now=1000)
    probe_limits = [
        torrent["up_limit"] // 1024
        for torrent in torrents[1:]
        if torrent["up_limit"] > 1
    ]

    assert torrents[0]["up_limit"] == 106 * 1024
    assert probe_limits == [8, 8]
    assert result["probing_torrents"] == 2
    assert result["allocated_kib"] == 122


def test_two_global_probes_share_full_cap_without_real_upload():
    """没有真实上传时，当前两个全局探测任务应共享下载器全部额度。"""
    limiter = _load("service.upload_limiter")
    torrents = [
        qb_torrent("high", "High", peers=1),
        qb_torrent("medium", "Medium", peers=1),
        qb_torrent("low", "Low", peers=1),
        qb_torrent("other", "Other", peers=1),
    ]
    instance = FakeQbInstance(torrents)
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 122},
        {
            "High": {"priority": "high", "limit_kib": 0},
            "Medium": {"priority": "medium", "limit_kib": 0},
            "Low": {"priority": "low", "limit_kib": 0},
            "Other": {"priority": "medium", "limit_kib": 0},
        },
    )

    result = limiter.run_upload_limit_cycle(plugin, now=1000)
    positive_limits = [
        torrent["up_limit"] // 1024
        for torrent in torrents
        if torrent["up_limit"] > 1
    ]

    assert len(positive_limits) == 2
    assert sum(positive_limits) == 122
    assert result["probing_torrents"] == 2
    assert result["allocated_kib"] == 122


def test_global_probe_selection_keeps_site_hard_limit_absolute():
    """全局探测轮换不得突破站点共享硬上限。"""
    limiter = _load("service.upload_limiter")
    torrents = [
        qb_torrent("high", "High", peers=1),
        qb_torrent("medium", "Medium", peers=1),
        qb_torrent("low", "Low", peers=1),
    ]
    instance = FakeQbInstance(torrents)
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 122},
        {
            "High": {"priority": "high", "limit_kib": 5},
            "Medium": {"priority": "medium", "limit_kib": 0},
            "Low": {"priority": "low", "limit_kib": 0},
        },
    )

    result = limiter.run_upload_limit_cycle(plugin, now=1000)
    sites = {item["key"]: item for item in result["sites"]}

    assert sites["High"]["allocated_kib"] <= 5
    assert result["probing_torrents"] <= 2
    assert result["allocated_kib"] == 122


def test_invalid_or_multiple_site_labels_enter_default_group():
    """未配置、无标签或多个站点标签任务都应进入默认组。"""
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
        {"A": {"priority": "high", "limit_kib": 10}},
    )

    result = limiter.run_upload_limit_cycle(plugin, now=1000)

    assert [item["key"] for item in result["sites"]] == ["__default__"]
    assert result["sites"][0]["allocated_kib"] == 90
    assert result["sites"][0]["priority"] == "medium"


def test_downloader_only_mode_avoids_per_torrent_limits_for_large_fleet():
    """无站点策略时只写下载器总上限，不得把额度摊薄到全部种子。"""
    limiter = _load("service.upload_limiter")
    torrents = [
        qb_torrent(
            f"seed-{index:04d}",
            "",
            rate=10 * 1024 if index == 0 else 0,
            peers=0,
        )
        for index in range(3874)
    ]
    instance = FakeQbInstance(torrents)
    instance.qbc.transfer.upload_limit = 100 * 1024
    instance.qbc.preferences["alt_up_limit"] = 100 * 1024
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 120},
        {},
    )

    result = limiter.run_upload_limit_cycle(plugin, now=1000)

    assert result["mode"] == "downloader_only"
    assert result["managed_torrents"] == 3874
    assert result["uploading_torrents"] == 1
    assert result["probing_torrents"] == 0
    assert result["protected_torrents"] == 0
    assert result["allocated_kib"] == 120
    assert instance.qbc.transfer.upload_limit == 120 * 1024
    assert instance.qbc.preferences["alt_up_limit"] == 120 * 1024
    assert instance.qbc.torrent_calls == []
    assert all(item["up_limit"] == 0 for item in torrents)

    plugin._upload_limit_enabled = False
    restored = limiter.restore_upload_limits(plugin)

    assert restored["code"] == 0
    assert instance.qbc.transfer.upload_limit == 100 * 1024
    assert instance.qbc.preferences["alt_up_limit"] == 100 * 1024
    assert instance.qbc.torrent_calls == []


def test_clearing_site_rules_releases_per_torrent_limits_but_keeps_global_cap():
    """运行中清空站点规则时应恢复单种设置，并继续保持下载器总上限。"""
    limiter = _load("service.upload_limiter")
    torrents = [qb_torrent("seed", "A", limit_kib=5, peers=1)]
    instance = FakeQbInstance(torrents)
    plugin = FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"],
        {"QB2": 120},
        {"A": {"priority": "medium", "limit_kib": 0}},
    )
    limiter.run_upload_limit_cycle(plugin, now=1000)
    assert torrents[0]["up_limit"] == 120 * 1024

    plugin._upload_limit_site_rules = {}
    result = limiter.run_upload_limit_cycle(plugin, now=1030)

    assert result["mode"] == "downloader_only"
    assert instance.qbc.transfer.upload_limit == 120 * 1024
    assert torrents[0]["up_limit"] == 5 * 1024
    assert plugin.data["upload_limit_state"]["torrents"] == {}


def test_persist_site_rules_updates_config_and_runtime_immediately():
    """站点策略操作应同时更新持久化配置和运行态字段。"""
    limiter = _load("service.upload_limiter")
    plugin = FakePlugin({}, [], {}, {"A": {"priority": "high", "limit_kib": 20}})

    rules = limiter.persist_upload_limit_site_rules(plugin, {})

    assert rules == {}
    assert plugin.config["upload_limit_site_rules"] == {}
    assert plugin._upload_limit_site_rules == {}
