"""按下载器隔离的健康速度基准校准与污染过滤。"""

from __future__ import annotations

import statistics
from typing import Any

from ..model.state import trim_health_samples


MAD_SCALE = 1.4826
MAD_MULTIPLIER = 3.0
MIN_RELATIVE_BAND = 0.25


def _positive_number(value: Any) -> float:
    """把输入转换为正数，非法值统一返回零。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def robust_speed_window(samples: list[dict]) -> dict:
    """计算样本速度的中位数、MAD 和固定污染过滤边界。"""
    speeds = [
        speed
        for sample in samples
        if isinstance(sample, dict)
        for speed in [_positive_number(sample.get("average_speed_bps"))]
        if speed > 0
    ]
    if not speeds:
        return {
            "median_speed_bps": 0.0,
            "mad_speed_bps": 0.0,
            "lower_speed_bps": 0.0,
            "upper_speed_bps": 0.0,
        }
    center = float(statistics.median(speeds))
    mad = float(statistics.median(abs(speed - center) for speed in speeds))
    band = max(
        MAD_MULTIPLIER * MAD_SCALE * mad,
        MIN_RELATIVE_BAND * center,
    )
    return {
        "median_speed_bps": center,
        "mad_speed_bps": mad,
        "lower_speed_bps": max(0.0, center - band),
        "upper_speed_bps": center + band,
    }


def _baseline_state(
    samples: list[dict],
    *,
    min_samples: int,
    floor_speed_bps: float,
    trusted_speed_bps: float = 0.0,
) -> dict:
    """从已接受样本构造 provisional 或 trusted 基准状态。"""
    samples = trim_health_samples(samples)
    window = robust_speed_window(samples)
    required = max(1, int(min_samples or 1))
    trusted = _positive_number(trusted_speed_bps)
    if len(samples) >= required:
        trusted = window["median_speed_bps"]
    return {
        "samples": samples,
        "status": "trusted" if trusted else "provisional",
        "sample_count": len(samples),
        "min_samples": required,
        "provisional_speed_bps": window["median_speed_bps"],
        "trusted_speed_bps": trusted,
        "mad_speed_bps": window["mad_speed_bps"],
        "lower_speed_bps": window["lower_speed_bps"],
        "upper_speed_bps": window["upper_speed_bps"],
        "floor_speed_bps": _positive_number(floor_speed_bps),
        "relative_only": not bool(_positive_number(floor_speed_bps)),
    }


def record_health_sample(
    baseline: dict | None,
    sample: dict,
    *,
    min_samples: int,
    floor_speed_bps: float = 0.0,
) -> tuple[dict, bool, str]:
    """校验并写入一个健康完成样本，拒绝值不得改变可信基准。"""
    existing = baseline if isinstance(baseline, dict) else {}
    samples = list(existing.get("samples") or [])
    speed = _positive_number(
        sample.get("average_speed_bps") if isinstance(sample, dict) else 0
    )
    floor = _positive_number(floor_speed_bps)
    if not speed:
        return dict(existing), False, "invalid_average_speed"
    if floor and speed < floor:
        return dict(existing), False, "below_floor_speed"

    trusted_speed = _positive_number(existing.get("trusted_speed_bps"))
    if trusted_speed:
        lower = _positive_number(existing.get("lower_speed_bps"))
        upper = _positive_number(existing.get("upper_speed_bps"))
        if lower and speed < lower:
            return dict(existing), False, "below_trusted_band"
        if upper and speed > upper:
            return dict(existing), False, "above_trusted_band"

    samples.append(dict(sample))
    required = max(1, int(min_samples or 1))
    if not trusted_speed and len(samples) >= required:
        initial_window = robust_speed_window(samples)
        incoming_accepted = (
            initial_window["lower_speed_bps"]
            <= speed
            <= initial_window["upper_speed_bps"]
        )
        filtered = [
            item
            for item in samples
            if initial_window["lower_speed_bps"]
            <= _positive_number(item.get("average_speed_bps"))
            <= initial_window["upper_speed_bps"]
        ]
        samples = filtered
        if not incoming_accepted:
            state = _baseline_state(
                samples,
                min_samples=required,
                floor_speed_bps=floor,
            )
            reason = (
                "below_calibration_band"
                if speed < initial_window["lower_speed_bps"]
                else "above_calibration_band"
            )
            return state, False, reason
    state = _baseline_state(
        samples,
        min_samples=required,
        floor_speed_bps=floor,
        trusted_speed_bps=trusted_speed,
    )
    return state, True, ""


def reset_downloader_baseline(
    baselines: dict,
    downloader_id: str,
    *,
    reset_at: float = 0.0,
) -> dict:
    """显式清空指定下载器的 provisional 与 trusted 基准。"""
    clean_id = str(downloader_id or "").strip()
    if not clean_id:
        return {}
    reset_state = {
        "samples": [],
        "status": "provisional",
        "sample_count": 0,
        "provisional_speed_bps": 0.0,
        "trusted_speed_bps": 0.0,
        "mad_speed_bps": 0.0,
        "lower_speed_bps": 0.0,
        "upper_speed_bps": 0.0,
        "floor_speed_bps": 0.0,
        "relative_only": True,
        "reset_at": max(0.0, float(reset_at or 0.0)),
    }
    baselines[clean_id] = reset_state
    return reset_state


__all__ = (
    "record_health_sample",
    "reset_downloader_baseline",
    "robust_speed_window",
)
