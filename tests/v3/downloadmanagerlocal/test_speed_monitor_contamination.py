from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path


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


def _sample(speed: float, index: int, downloader_id="qb-main") -> dict:
    """构造指定下载器与平均速度的完成样本。"""
    return {
        "downloader_id": downloader_id,
        "torrent_hash": f"{downloader_id}-{index}",
        "average_speed_bps": speed,
        "eligible": True,
    }


def _record(module, baseline, speed, index, *, floor=0, downloader_id="qb-main"):
    """向指定下载器基准写入一个测试样本。"""
    return module.record_health_sample(
        baseline,
        _sample(speed, index, downloader_id),
        min_samples=5,
        floor_speed_bps=floor,
    )


def test_first_slow_calibration_is_relative_without_floor_and_filtered_with_floor():
    """首批整体慢速无下限时只能形成相对基准，有下限时必须排除。"""
    module = _load("service.speed_baseline")
    relative = None
    protected = None

    for index, speed in enumerate([10, 11, 9, 10, 10]):
        relative, accepted, _ = _record(module, relative, speed, index)
        assert accepted is True
        protected, protected_accepted, reason = _record(
            module, protected, speed, index, floor=100
        )
        assert protected_accepted is False
        assert reason == "below_floor_speed"

    assert relative["status"] == "trusted"
    assert relative["trusted_speed_bps"] == 10
    assert relative["relative_only"] is True
    assert protected is None or protected == {}


def test_trusted_baseline_rejects_repeated_slow_and_fast_pollution():
    """已有 trusted 后连续慢速和极快样本不得逐步拖动基准。"""
    module = _load("service.speed_baseline")
    baseline = None
    for index, speed in enumerate([100, 100, 100, 100, 100]):
        baseline, accepted, _ = _record(module, baseline, speed, index)
        assert accepted is True

    for index, speed in enumerate([60, 55, 50, 1000], start=5):
        updated, accepted, reason = _record(module, baseline, speed, index)
        assert accepted is False
        assert reason in {"below_trusted_band", "above_trusted_band"}
        assert updated["trusted_speed_bps"] == 100
        assert updated["sample_count"] == 5
        baseline = updated

    updated, accepted, reason = _record(module, baseline, 110, 9)
    assert accepted is True
    assert reason == ""
    assert updated["sample_count"] == 6
    assert updated["trusted_speed_bps"] == 100


def test_downloader_floors_and_resets_remain_isolated():
    """不同下载器保护下限与显式重置不得互相污染。"""
    module = _load("service.speed_baseline")
    baselines = {}
    for downloader_id, floor, speeds in (
        ("qb-main", 100, [100, 110, 120, 130, 140]),
        ("tr-backup", 500, [500, 510, 520, 530, 540]),
    ):
        baseline = None
        for index, speed in enumerate(speeds):
            baseline, accepted, _ = _record(
                module,
                baseline,
                speed,
                index,
                floor=floor,
                downloader_id=downloader_id,
            )
            assert accepted is True
        baselines[downloader_id] = baseline

    tr_before = dict(baselines["tr-backup"])
    reset = module.reset_downloader_baseline(
        baselines, "qb-main", reset_at=500
    )

    assert reset["status"] == "provisional"
    assert reset["sample_count"] == 0
    assert reset["trusted_speed_bps"] == 0
    assert baselines["tr-backup"] == tr_before
    assert baselines["tr-backup"]["trusted_speed_bps"] == 520
