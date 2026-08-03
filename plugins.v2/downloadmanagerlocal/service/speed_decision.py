"""下载速度异常监控的参考速度与超时判定。"""

from __future__ import annotations

from typing import Any


def _positive_number(value: Any) -> float:
    """把输入转换为正数，非法值统一返回零。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def resolve_reference_speed(
    *,
    mode: str,
    downloader_id: str,
    baseline: dict | None,
    manual_speeds: dict | None,
    floor_speeds: dict | None,
) -> tuple[float, str]:
    """按监控模式解析当前下载器可用于判定的参考速度。"""
    if mode == "manual":
        speed = _positive_number((manual_speeds or {}).get(downloader_id))
        return speed, "manual" if speed else "manual_unavailable"

    trusted_speed = _positive_number(
        (baseline or {}).get("trusted_speed_bps")
    )
    if not trusted_speed:
        return 0.0, "baseline_unavailable"
    floor_speed = _positive_number((floor_speeds or {}).get(downloader_id))
    if floor_speed > trusted_speed:
        return floor_speed, "trusted_baseline_with_floor"
    return trusted_speed, "trusted_baseline"


def evaluate_speed_anomaly(
    *,
    start_remaining_bytes: int,
    total_bytes: int,
    downloaded_bytes: int,
    current_speed_bps: float,
    effective_seconds: float,
    reference_speed_bps: float,
    reference_source: str,
    tolerance: float,
    grace_seconds: float,
    required_samples: int,
    previous_abnormal_samples: int,
) -> dict:
    """根据首次观察剩余预算和有效时长生成一次异常判定快照。"""
    remaining_bytes = max(0, int(start_remaining_bytes or 0))
    total = max(0, int(total_bytes or 0))
    downloaded = max(0, int(downloaded_bytes or 0))
    elapsed = max(0.0, float(effective_seconds or 0.0))
    speed = max(0.0, float(current_speed_bps or 0.0))
    reference = _positive_number(reference_speed_bps)
    grace = max(0.0, float(grace_seconds or 0.0))
    required = max(1, int(required_samples or 1))
    progress = min(1.0, downloaded / total) if total > 0 else 0.0
    result = {
        "status": "unready",
        "reason": "reference_unavailable",
        "reference_source": str(reference_source or "unavailable"),
        "reference_speed_bps": reference,
        "current_speed_bps": speed,
        "start_remaining_bytes": remaining_bytes,
        "effective_seconds": elapsed,
        "expected_seconds": 0.0,
        "allowed_seconds": 0.0,
        "grace_seconds": grace,
        "progress": progress,
        "abnormal_samples": 0,
        "required_samples": required,
        "is_anomalous": False,
    }
    if tolerance <= 1.0:
        result["reason"] = "invalid_tolerance"
        return result
    if remaining_bytes <= 0:
        result["reason"] = "no_remaining_bytes"
        return result
    if reference <= 0:
        return result

    expected_seconds = remaining_bytes / reference
    allowed_seconds = expected_seconds * float(tolerance)
    result["expected_seconds"] = expected_seconds
    result["allowed_seconds"] = allowed_seconds
    if elapsed < grace:
        result["status"] = "grace"
        result["reason"] = "startup_grace"
        return result
    if elapsed <= allowed_seconds:
        result["status"] = "normal"
        result["reason"] = "within_allowed_time"
        return result

    abnormal_samples = max(0, int(previous_abnormal_samples or 0)) + 1
    result["abnormal_samples"] = abnormal_samples
    if abnormal_samples < required:
        result["status"] = "suspected"
        result["reason"] = "awaiting_consecutive_samples"
        return result
    result["status"] = "anomalous"
    result["reason"] = "allowed_time_exceeded"
    result["is_anomalous"] = True
    return result


__all__ = ("evaluate_speed_anomaly", "resolve_reference_speed")
