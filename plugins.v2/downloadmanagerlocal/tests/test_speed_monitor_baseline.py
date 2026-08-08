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


def _prepare_imports() -> None:
    """安装不执行插件入口的 downloadmanagerlocal 包壳。"""
    for name in list(sys.modules):
        if name == "downloadmanagerlocal" or name.startswith("downloadmanagerlocal."):
            sys.modules.pop(name)
    package = types.ModuleType("downloadmanagerlocal")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["downloadmanagerlocal"] = package


def _load(module_name: str):
    """加载指定下载中心纯 Python 模块。"""
    _prepare_imports()
    return importlib.import_module(f"downloadmanagerlocal.{module_name}")


def _sample(speed: float, index: int = 0) -> dict:
    """构造指定平均速度的健康完成样本。"""
    return {
        "downloader_id": "qb-main",
        "torrent_hash": f"hash-{index}",
        "average_speed_bps": speed,
        "eligible": True,
    }


def _record(baseline_module, baseline, speed, index=0, **kwargs):
    """写入一个测试样本并返回基准、接受状态和原因。"""
    return baseline_module.record_health_sample(
        baseline,
        _sample(speed, index),
        min_samples=kwargs.get("min_samples", 5),
        floor_speed_bps=kwargs.get("floor_speed_bps", 0),
    )


def test_auto_baseline_stays_provisional_until_minimum_samples():
    """自动模式样本不足时只形成相对 provisional 基准。"""
    baseline_module = _load("service.speed_baseline")
    decision = _load("service.speed_decision")
    baseline = None

    for index, speed in enumerate([90, 100, 110, 100]):
        baseline, accepted, reason = _record(
            baseline_module, baseline, speed, index
        )
        assert accepted is True
        assert reason == ""

    reference, source = decision.resolve_reference_speed(
        mode="auto",
        downloader_id="qb-main",
        baseline=baseline,
        manual_speeds={},
        floor_speeds={},
    )
    assert baseline["status"] == "provisional"
    assert baseline["sample_count"] == 4
    assert baseline["relative_only"] is True
    assert baseline["trusted_speed_bps"] == 0
    assert (reference, source) == (0.0, "baseline_unavailable")

    baseline, accepted, _ = _record(baseline_module, baseline, 100, 4)
    assert accepted is True
    assert baseline["status"] == "trusted"
    assert baseline["trusted_speed_bps"] == 100
    assert baseline["relative_only"] is True
    reference, source = decision.resolve_reference_speed(
        mode="auto",
        downloader_id="qb-main",
        baseline=baseline,
        manual_speeds={},
        floor_speeds={},
    )
    assert (reference, source) == (100.0, "trusted_relative_baseline")


def test_threshold_suggestions_use_sample_percentile_and_fixed_safety_values():
    """样本足够时建议容忍倍数和宽限，其余安全参数保持固定建议。"""
    baseline_module = _load("service.speed_baseline")
    samples = [
        {"average_speed_bps": speed, "effective_seconds": duration}
        for speed, duration in [
            (10_760_061.85, 133.1),
            (4_578_128.82, 320.9),
            (8_439_449.67, 150.2),
            (20_097_503.15, 60.1),
            (26_982_894.64, 300.4),
            (12_399_564.26, 90.1),
            (5_734_183.36, 210.2),
        ]
    ]

    suggestion = baseline_module.suggest_thresholds(
        samples,
        trusted_speed_bps=10_760_061.85,
        min_samples=5,
    )

    assert suggestion["ready"] is True
    assert suggestion["sample_count"] == 7
    assert suggestion["tolerance"] == 2.2
    assert suggestion["grace_minutes"] == 5
    assert suggestion["interval_seconds"] == 30
    assert suggestion["consecutive_abnormal_samples"] == 2

    pending = baseline_module.suggest_thresholds(
        samples[:4],
        trusted_speed_bps=10_760_061.85,
        min_samples=5,
    )
    assert pending["ready"] is False
    assert pending["tolerance"] is None
    assert pending["grace_minutes"] is None


def test_floor_filters_slow_calibration_samples_and_isolates_downloaders():
    """保护下限应排除低速样本且各下载器基准互不影响。"""
    baseline_module = _load("service.speed_baseline")
    baselines = {}

    qb, accepted, reason = _record(
        baseline_module, None, 99, floor_speed_bps=100
    )
    assert accepted is False
    assert reason == "below_floor_speed"
    assert qb == {}

    for index, speed in enumerate([100, 110, 120, 130, 140]):
        qb, accepted, _ = _record(
            baseline_module,
            qb,
            speed,
            index,
            floor_speed_bps=100,
        )
        assert accepted is True
    tr, accepted, _ = _record(
        baseline_module, None, 500, floor_speed_bps=400, min_samples=1
    )
    assert accepted is True
    baselines["qb-main"] = qb
    baselines["tr-backup"] = tr

    assert qb["trusted_speed_bps"] == 120
    assert qb["relative_only"] is False
    assert tr["trusted_speed_bps"] == 500
    assert baselines["qb-main"]["samples"] != baselines["tr-backup"]["samples"]


def test_mad_zero_rejects_outlier_and_preserves_trusted_baseline():
    """MAD 为零时应使用 25% 相对带并保留最后可信基准。"""
    baseline_module = _load("service.speed_baseline")
    provisional = None
    for index in range(4):
        provisional, accepted, _ = _record(
            baseline_module, provisional, 100, index
        )
        assert accepted is True
    provisional, accepted, reason = _record(
        baseline_module, provisional, 1000, 4
    )
    assert accepted is False
    assert reason == "above_calibration_band"
    assert provisional["sample_count"] == 4
    assert provisional["trusted_speed_bps"] == 0

    baseline = None
    for index in range(5):
        baseline, accepted, _ = _record(baseline_module, baseline, 100, index)
        assert accepted is True

    assert baseline["mad_speed_bps"] == 0
    assert baseline["lower_speed_bps"] == 75
    assert baseline["upper_speed_bps"] == 125
    before = dict(baseline)
    rejected, accepted, reason = _record(baseline_module, baseline, 1000, 6)

    assert accepted is False
    assert reason == "above_trusted_band"
    assert rejected == before
    assert rejected["trusted_speed_bps"] == 100

    updated, accepted, reason = _record(baseline_module, baseline, 110, 7)
    assert accepted is True
    assert reason == ""
    assert updated["sample_count"] == 6
    assert updated["trusted_speed_bps"] == 100


def test_explicit_reset_clears_trusted_state_and_manual_mode_ignores_history():
    """显式重置应清空可信状态，手动模式不得读取历史基准。"""
    baseline_module = _load("service.speed_baseline")
    decision = _load("service.speed_decision")
    baselines = {
        "qb-main": {
            "samples": [_sample(100)],
            "trusted_speed_bps": 100,
        }
    }

    reset = baseline_module.reset_downloader_baseline(
        baselines, "qb-main", reset_at=123
    )
    reference, source = decision.resolve_reference_speed(
        mode="manual",
        downloader_id="qb-main",
        baseline={"trusted_speed_bps": 9999},
        manual_speeds={"qb-main": 256},
        floor_speeds={"qb-main": 5000},
    )

    assert reset["samples"] == []
    assert reset["trusted_speed_bps"] == 0
    assert reset["reset_at"] == 123
    assert baselines["qb-main"] is reset
    assert (reference, source) == (256.0, "manual")


def test_manual_mode_requires_positive_speed_for_every_selected_downloader():
    """手动模式缺少任一选中下载器的正数速度时不得运行。"""
    config = _load("utils.config")
    plugin = SimpleNamespace(
        _enabled=True,
        _speed_monitor_enabled=True,
        _speed_monitor_downloaders=["qb-main", "tr-backup"],
        _speed_monitor_mode="manual",
        _speed_monitor_manual_speed_bps={"qb-main": 100},
    )

    assert config.is_speed_monitor_active(plugin) is False
    plugin._speed_monitor_manual_speed_bps["tr-backup"] = 200
    assert config.is_speed_monitor_active(plugin) is True
    plugin._speed_monitor_manual_speed_bps["tr-backup"] = 0
    assert config.is_speed_monitor_active(plugin) is False


def test_baseline_state_round_trips_through_versioned_plugin_storage():
    """可信基准和相对限制标记应通过版本化状态完整回读。"""
    state = _load("model.state")

    class FakeDataPlugin:
        """提供版本化状态读写所需的内存接口。"""

        def __init__(self):
            """初始化空数据字典。"""
            self.data = {}

        def get_data(self, key):
            """读取内存数据。"""
            return self.data.get(key)

        def save_data(self, key, value):
            """保存内存数据。"""
            self.data[key] = value

    plugin = FakeDataPlugin()
    items = {
        "qb-main": {
            "samples": [_sample(100)],
            "trusted_speed_bps": 100,
            "relative_only": True,
        }
    }
    state.save_speed_monitor_items(
        plugin, state.SPEED_MONITOR_BASELINES_KEY, items
    )

    restored = state.load_speed_monitor_items(
        plugin, state.SPEED_MONITOR_BASELINES_KEY, "baselines"
    )
    assert restored == items
    assert plugin.data[state.SPEED_MONITOR_BASELINES_KEY]["schema_version"] == 1
