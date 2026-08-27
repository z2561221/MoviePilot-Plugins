"""验证下载中心今日与累计计数器（转移做种 / IYUU 铺种）。"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


PLUGIN_DIR = Path(
    os.environ.get("DOWNLOADMANAGERLOCAL_PLUGIN_DIR")
    or Path(__file__).resolve().parents[1]
)


def _load_state_module():
    """隔离加载状态模块，避免引入完整 MoviePilot 运行时。"""
    path = PLUGIN_DIR / "model" / "state.py"
    spec = importlib.util.spec_from_file_location("dml_v3_model_state", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakePlugin:
    """提供最小 get_data/save_data 行为的插件替身。"""

    def __init__(self, data: dict | None = None) -> None:
        """初始化内存持久化数据与写入记录。"""
        self.data = dict(data or {})
        self.saved: list[tuple[str, object]] = []

    def get_data(self, key: str):
        """读取内存持久化数据。"""
        return self.data.get(key)

    def save_data(self, key: str, value) -> None:
        """写入内存持久化数据并记录一次落盘。"""
        self.saved.append((key, value))
        self.data[key] = value


def test_transfer_stats_expose_today_and_total_counters() -> None:
    """转种成功必须同时累加累计与今日计数，兜底只计入兜底子集。"""
    state = _load_state_module()
    plugin = FakePlugin()

    state.record_transfer_success(plugin, 3, fallback=False)
    stats = state.record_transfer_success(plugin, 2, fallback=True)

    assert stats["schema_version"] == 2
    assert stats["success_total"] == 5
    assert stats["fallback_success"] == 2
    assert stats["today_success"] == 5
    assert stats["today_fallback"] == 2
    assert stats["today_date"] == state.today_stamp()


def test_transfer_today_counters_reset_across_days_without_writing() -> None:
    """跨天读取必须把今日计数视为归零，且只读路径不得触发落盘。"""
    state = _load_state_module()
    plugin = FakePlugin({
        "transfer_stats": {
            "schema_version": 2,
            "success_total": 47,
            "fallback_success": 8,
            "today_date": "2000-01-01",
            "today_success": 9,
            "today_fallback": 4,
        }
    })

    stats = state.load_transfer_stats(plugin)

    assert stats["success_total"] == 47
    assert stats["fallback_success"] == 8
    assert stats["today_success"] == 0
    assert stats["today_fallback"] == 0
    assert stats["today_date"] == state.today_stamp()
    assert plugin.saved == []


def test_transfer_today_counters_clamp_to_parent_totals() -> None:
    """脏数据下今日计数不得超过累计，兜底不得超过今日成功。"""
    state = _load_state_module()
    plugin = FakePlugin({
        "transfer_stats": {
            "success_total": 5,
            "fallback_success": 2,
            "today_date": None,
            "today_success": 99,
            "today_fallback": 99,
        }
    })
    plugin.data["transfer_stats"]["today_date"] = state.today_stamp()

    stats = state.load_transfer_stats(plugin)

    assert stats["today_success"] == 5
    assert stats["today_fallback"] == 2


def test_legacy_transfer_payload_upgrades_without_today_fields() -> None:
    """旧版只有累计字段的持久化数据必须可读，并补出今日计数。"""
    state = _load_state_module()
    plugin = FakePlugin({
        "transfer_stats": {"schema_version": 1, "success_total": 47, "fallback_success": 8}
    })

    stats = state.load_transfer_stats(plugin)

    assert stats["schema_version"] == 2
    assert stats["success_total"] == 47
    assert stats["today_success"] == 0
    assert plugin.saved == []


def test_iyuu_stats_accumulate_real_totals_instead_of_cache_size() -> None:
    """IYUU 统计必须是只增的真实累计计数，而不是缓存唯一数。"""
    state = _load_state_module()
    plugin = FakePlugin()

    state.record_iyuu_results(plugin, success=158, fail=75)
    stats = state.record_iyuu_results(plugin, success=2, fail=1)

    assert stats["schema_version"] == 1
    assert stats["success_total"] == 160
    assert stats["fail_total"] == 76
    assert stats["today_success"] == 160
    assert stats["today_fail"] == 76
    assert plugin.data["iyuu_stats"]["today_date"] == state.today_stamp()


def test_iyuu_stats_skip_write_and_sanitize_dirty_counts() -> None:
    """空结果不得写盘，非法计数必须规范为非负整数。"""
    state = _load_state_module()
    plugin = FakePlugin()

    assert state.record_iyuu_results(plugin, success=0, fail=0)["success_total"] == 0
    assert plugin.saved == []

    stats = state.record_iyuu_results(plugin, success=-5, fail="bad")

    assert stats["success_total"] == 0
    assert stats["fail_total"] == 0
    assert plugin.saved == []


def test_iyuu_today_counters_reset_across_days() -> None:
    """IYUU 今日计数必须按天归零，累计保持不变。"""
    state = _load_state_module()
    plugin = FakePlugin({
        "iyuu_stats": {
            "success_total": 158,
            "fail_total": 75,
            "today_date": "2000-01-01",
            "today_success": 12,
            "today_fail": 3,
        }
    })

    stats = state.load_iyuu_stats(plugin)

    assert stats["success_total"] == 158
    assert stats["fail_total"] == 75
    assert stats["today_success"] == 0
    assert stats["today_fail"] == 0
    assert plugin.saved == []


def test_persisted_state_inventory_documents_iyuu_stats_key() -> None:
    """新增持久化键必须登记在状态清单中。"""
    state = _load_state_module()

    assert state.IYUU_STATS_KEY == "iyuu_stats"
    assert state.PERSISTED_STATE_KEYS["iyuu_stats"] == state.IYUU_STATS_KEY


def test_overview_handler_exposes_today_counters() -> None:
    """总览接口必须输出今日计数，并停止使用缓存唯一数当累计。"""
    source = (PLUGIN_DIR / "controller" / "handlers.py").read_text(encoding="utf-8")

    assert "iyuu_stats = load_iyuu_stats(plugin)" in source
    assert '"today_success": int(transfer_stats["today_success"]),' in source
    assert '"today_fallback": int(transfer_stats["today_fallback"]),' in source
    assert '"today_success": int(iyuu_stats["today_success"]),' in source
    assert '"today_fail": int(iyuu_stats["today_fail"]),' in source
    assert "count_unique_cache_items" not in source


def test_iyuu_service_flushes_round_counters_on_every_exit() -> None:
    """辅种任务必须在所有退出路径把本轮计数并入累计统计。"""
    source = (PLUGIN_DIR / "service" / "iyuu.py").read_text(encoding="utf-8")

    assert "record_iyuu_results" in source
    assert "    finally:\n        _flush_iyuu_stats(plugin)" in source.replace("\r\n", "\n")
    assert "def _flush_iyuu_stats(plugin):" in source


def test_page_cards_show_today_total_and_tail_counters() -> None:
    """详情页两张卡片必须展示今日、累计与尾部计数。"""
    page_source = (
        PLUGIN_DIR / "frontend" / "src" / "components" / "Page.vue"
    ).read_text(encoding="utf-8")

    assert (
        "今日 ${cards.transfer?.today_success || 0}"
        " · 累计 ${cards.transfer?.success_total || 0}"
        " · 兜底 ${cards.transfer?.fallback_success || 0}" in page_source
    )
    assert (
        "今日 ${cards.iyuu?.today_success || 0}"
        " · 累计 ${cards.iyuu?.success_total || 0}"
        " · 失败 ${cards.iyuu?.fail_total || 0}" in page_source
    )
    assert "累计成功 ${cards.transfer?.success_total || 0}" not in page_source
    assert "已铺种 ${cards.iyuu?.success_total || 0}" not in page_source
