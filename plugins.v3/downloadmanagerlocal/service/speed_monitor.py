"""下载速度异常监控扫描、会话计时与持久化运行时。"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from ..model.state import (
    SPEED_MONITOR_ALERTS_KEY,
    SPEED_MONITOR_BASELINES_KEY,
    SPEED_MONITOR_SCHEMA_VERSION,
    SPEED_MONITOR_SESSIONS_KEY,
    SpeedMonitorStateMigrationError,
    load_speed_monitor_items,
    save_speed_monitor_items,
    trim_health_samples,
    trim_terminal_records,
)
from ..utils.config import is_speed_monitor_active
from ..utils.torrent_adapter import (
    TORRENT_ACTIVE,
    TORRENT_COMPLETED,
    TORRENT_ERROR,
    DownloaderPollResult,
    poll_downloader,
    poll_error,
)
from .speed_decision import evaluate_speed_anomaly, resolve_reference_speed
from .speed_baseline import record_health_sample, reset_downloader_baseline
from .speed_notification import dispatch_pending_speed_alerts


SUPPORTED_DOWNLOADER_TYPES = {"qbittorrent", "transmission"}
SESSION_ACTIVE = "active"


@dataclass
class SpeedMonitorSession:
    """可持久化且从插件首次观察开始计时的下载任务会话。"""

    downloader_id: str
    downloader_type: str
    torrent_hash: str
    name: str
    total_bytes: int
    start_downloaded_bytes: int
    start_remaining_bytes: int
    last_downloaded_bytes: int
    first_observed_at: float
    last_observed_at: float
    last_effective_at: float
    last_valid_sample_at: float
    last_success_poll_at: float
    effective_seconds: float
    last_state: str
    anomaly_epoch: int = 0
    anomaly_active: bool = False
    status: str = SESSION_ACTIVE
    terminal_at: float = 0.0
    terminal_reason: str = ""
    had_error: bool = False
    had_anomaly: bool = False
    sample_eligible: bool = False
    completion_stats: dict = field(default_factory=dict)
    current_speed_bps: float = 0.0
    consecutive_abnormal_samples: int = 0
    decision: dict = field(default_factory=dict)
    schema_version: int = SPEED_MONITOR_SCHEMA_VERSION

    def to_dict(self) -> dict:
        """转换为可由 MoviePilot 插件数据接口保存的字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> "SpeedMonitorSession":
        """从已迁移字典恢复速度监控会话。"""
        if not isinstance(value, dict):
            raise SpeedMonitorStateMigrationError("session item must be a dict")
        downloader_id = str(value.get("downloader_id") or "").strip()
        torrent_hash = str(value.get("torrent_hash") or "").strip().lower()
        if not downloader_id or not torrent_hash:
            raise SpeedMonitorStateMigrationError("session identity is incomplete")
        first_observed_at = _float(value.get("first_observed_at"))
        last_observed_at = _float(value.get("last_observed_at"), first_observed_at)
        last_effective_at = _float(value.get("last_effective_at"), last_observed_at)
        last_state = str(value.get("last_state") or TORRENT_ACTIVE)
        return cls(
            downloader_id=downloader_id,
            downloader_type=str(value.get("downloader_type") or ""),
            torrent_hash=torrent_hash,
            name=str(value.get("name") or ""),
            total_bytes=_int(value.get("total_bytes")),
            start_downloaded_bytes=_int(value.get("start_downloaded_bytes")),
            start_remaining_bytes=_int(value.get("start_remaining_bytes")),
            last_downloaded_bytes=_int(value.get("last_downloaded_bytes")),
            first_observed_at=first_observed_at,
            last_observed_at=last_observed_at,
            last_effective_at=last_effective_at,
            last_valid_sample_at=_float(value.get("last_valid_sample_at")),
            last_success_poll_at=_float(value.get("last_success_poll_at"), last_observed_at),
            effective_seconds=_float(value.get("effective_seconds")),
            last_state=last_state,
            anomaly_epoch=_int(value.get("anomaly_epoch")),
            anomaly_active=bool(value.get("anomaly_active", False)),
            status=str(value.get("status") or SESSION_ACTIVE),
            terminal_at=_float(value.get("terminal_at")),
            terminal_reason=str(value.get("terminal_reason") or ""),
            had_error=bool(value.get("had_error", False)),
            had_anomaly=bool(value.get("had_anomaly", False)),
            sample_eligible=bool(value.get("sample_eligible", False)),
            completion_stats=(
                dict(value.get("completion_stats"))
                if isinstance(value.get("completion_stats"), dict)
                else {}
            ),
            current_speed_bps=_float(value.get("current_speed_bps")),
            consecutive_abnormal_samples=_int(
                value.get("consecutive_abnormal_samples")
            ),
            decision=(
                dict(value.get("decision"))
                if isinstance(value.get("decision"), dict)
                else {}
            ),
            schema_version=SPEED_MONITOR_SCHEMA_VERSION,
        )


class SpeedMonitorRuntime:
    """隔离多下载器扫描锁、会话锁和版本化持久化状态。"""

    def __init__(
        self,
        sessions: dict[str, SpeedMonitorSession] | None = None,
        baselines: dict | None = None,
        alerts: dict | None = None,
        state_error: str = "",
    ) -> None:
        """初始化线程安全的速度监控运行态。"""
        self._lock = threading.RLock()
        self.downloader_locks: dict[str, threading.RLock] = {}
        self.session_locks: dict[str, threading.RLock] = {}
        self.sessions = dict(sessions or {})
        self.baselines = dict(baselines or {})
        self.alerts = dict(alerts or {})
        self.last_poll_results: dict[str, DownloaderPollResult] = {}
        self.state_error = str(state_error or "")

    def downloader_lock(self, downloader_id: str) -> threading.RLock:
        """返回指定下载器实例独享的扫描锁。"""
        with self._lock:
            return self.downloader_locks.setdefault(downloader_id, threading.RLock())

    def session_lock(self, session_key: str) -> threading.RLock:
        """返回指定下载会话独享的状态锁。"""
        with self._lock:
            return self.session_locks.setdefault(session_key, threading.RLock())


def _float(value: Any, default: float = 0.0) -> float:
    """安全转换持久化浮点字段。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int(value: Any, default: int = 0) -> int:
    """安全转换持久化整数字段。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _session_key(downloader_id: str, torrent_hash: str) -> str:
    """生成按下载器实例隔离的稳定会话 key。"""
    return f"{downloader_id}:{torrent_hash}"


def _restore_sessions(items: dict) -> dict[str, SpeedMonitorSession]:
    """从版本化状态项恢复全部速度监控会话。"""
    restored = {}
    for key, value in items.items():
        session = SpeedMonitorSession.from_dict(value)
        expected_key = _session_key(session.downloader_id, session.torrent_hash)
        if str(key) != expected_key:
            raise SpeedMonitorStateMigrationError("session key does not match identity")
        restored[expected_key] = session
    return restored


def load_speed_monitor_runtime_snapshot(plugin: Any) -> SpeedMonitorRuntime:
    """从持久层构造独立快照，不复用或覆盖当前进程的可写运行态。"""
    try:
        session_items = load_speed_monitor_items(
            plugin, SPEED_MONITOR_SESSIONS_KEY, "sessions"
        )
        baselines = load_speed_monitor_items(
            plugin, SPEED_MONITOR_BASELINES_KEY, "baselines"
        )
        alerts = load_speed_monitor_items(plugin, SPEED_MONITOR_ALERTS_KEY, "alerts")
        return SpeedMonitorRuntime(
            sessions=_restore_sessions(session_items),
            baselines=baselines,
            alerts=alerts,
        )
    except SpeedMonitorStateMigrationError as error:
        return SpeedMonitorRuntime(state_error=str(error))


def ensure_speed_monitor_runtime(plugin: Any) -> SpeedMonitorRuntime:
    """恢复或创建速度监控运行态，迁移失败时明确停用监控。"""
    runtime = getattr(plugin, "_speed_monitor_runtime", None)
    if isinstance(runtime, SpeedMonitorRuntime):
        return runtime
    runtime = load_speed_monitor_runtime_snapshot(plugin)
    if not runtime.state_error:
        plugin._speed_monitor_state_error = ""
    else:
        plugin._speed_monitor_enabled = False
        plugin._speed_monitor_state_error = runtime.state_error
    plugin._speed_monitor_runtime = runtime
    return runtime


def _trim_runtime(runtime: SpeedMonitorRuntime, now: float) -> None:
    """裁剪终态会话、已处理告警和每下载器健康样本窗口。"""
    session_items = trim_terminal_records(
        {key: session.to_dict() for key, session in runtime.sessions.items()},
        now=now,
        active_statuses=(SESSION_ACTIVE,),
    )
    runtime.sessions = {
        key: runtime.sessions[key]
        for key in session_items
        if key in runtime.sessions
    }
    runtime.alerts = trim_terminal_records(
        runtime.alerts,
        now=now,
        active_statuses=("pending", "notified", "confirming"),
        timestamp_field="handled_at",
    )
    for downloader_id, baseline in list(runtime.baselines.items()):
        if not isinstance(baseline, dict):
            continue
        baseline["samples"] = trim_health_samples(baseline.get("samples"))
        runtime.baselines[downloader_id] = baseline


def persist_speed_monitor_runtime(plugin: Any, runtime: SpeedMonitorRuntime, now: float) -> None:
    """清理并保存速度监控会话、基准和告警状态。"""
    _trim_runtime(runtime, now)
    save_speed_monitor_items(
        plugin,
        SPEED_MONITOR_SESSIONS_KEY,
        {key: session.to_dict() for key, session in runtime.sessions.items()},
    )
    save_speed_monitor_items(plugin, SPEED_MONITOR_BASELINES_KEY, runtime.baselines)
    save_speed_monitor_items(plugin, SPEED_MONITOR_ALERTS_KEY, runtime.alerts)


def stop_speed_monitor_runtime(plugin: Any) -> None:
    """保存速度监控运行态后释放锁引用。"""
    runtime = getattr(plugin, "_speed_monitor_runtime", None)
    if isinstance(runtime, SpeedMonitorRuntime) and not runtime.state_error:
        persist_speed_monitor_runtime(plugin, runtime, time.time())
    plugin._speed_monitor_runtime = None


def _downloader_type(service: Any) -> str:
    """从 MoviePilot 服务或实例类型归一出受支持下载器类型。"""
    raw_type = getattr(service, "type", "")
    value = getattr(raw_type, "value", raw_type)
    normalized = str(value or "").strip().lower()
    if "qbittorrent" in normalized or normalized in {"qb", "qbit"}:
        return "qbittorrent"
    if "transmission" in normalized or normalized == "tr":
        return "transmission"
    instance_name = service.instance.__class__.__name__.lower()
    if "qbittorrent" in instance_name:
        return "qbittorrent"
    if "transmission" in instance_name:
        return "transmission"
    return ""


def _finish_session(
    runtime: SpeedMonitorRuntime,
    key: str,
    status: str,
    observed_at: float,
) -> bool:
    """把活跃会话原子更新为唯一终态。"""
    with runtime.session_lock(key):
        session = runtime.sessions.get(key)
        if session is None or session.status != SESSION_ACTIVE:
            return False
        _close_anomaly_cycle(runtime, session, status, observed_at)
        session.status = status
        session.terminal_reason = status
        session.terminal_at = observed_at
        session.last_observed_at = observed_at
        session.last_success_poll_at = observed_at
        return True


def _alert_key(session: SpeedMonitorSession) -> str:
    """生成按下载器、hash 和异常 epoch 隔离的告警 key。"""
    session_key = _session_key(session.downloader_id, session.torrent_hash)
    return f"{session_key}:{session.anomaly_epoch}"


def _close_anomaly_cycle(
    runtime: SpeedMonitorRuntime,
    session: SpeedMonitorSession,
    status: str,
    observed_at: float,
) -> None:
    """把当前异常周期收束为终态并允许后续建立新周期。"""
    if not session.anomaly_active or session.anomaly_epoch <= 0:
        return
    alert = runtime.alerts.get(_alert_key(session))
    if isinstance(alert, dict) and alert.get("status") in {
        "pending", "notified", "confirming"
    }:
        alert["status"] = str(status or "recovered")
        alert["handled_at"] = observed_at
        alert["updated_at"] = observed_at
    session.anomaly_active = False


def _update_anomaly_cycle(
    runtime: SpeedMonitorRuntime,
    session: SpeedMonitorSession,
    observed_at: float,
) -> None:
    """根据判定快照创建唯一 pending 告警或收束恢复周期。"""
    if session.decision.get("is_anomalous"):
        session.had_anomaly = True
        if session.anomaly_active:
            return
        session.anomaly_epoch += 1
        session.anomaly_active = True
        key = _alert_key(session)
        runtime.alerts.setdefault(key, {
            "status": "pending",
            "downloader_id": session.downloader_id,
            "torrent_hash": session.torrent_hash,
            "name": session.name,
            "anomaly_epoch": session.anomaly_epoch,
            "created_at": observed_at,
            "updated_at": observed_at,
            "handled_at": 0.0,
            "decision": dict(session.decision),
        })
        return
    _close_anomaly_cycle(runtime, session, "recovered", observed_at)


def _completion_stats(session: SpeedMonitorSession, completed_at: float) -> dict:
    """根据观察期间新增字节和有效时长生成原始完成统计。"""
    observed_bytes = max(
        0, session.last_downloaded_bytes - session.start_downloaded_bytes
    )
    effective_seconds = max(0.0, session.effective_seconds)
    average_speed_bps = (
        observed_bytes / effective_seconds
        if observed_bytes > 0 and effective_seconds > 0
        else 0.0
    )
    rejection_reasons = []
    if session.total_bytes <= 0:
        rejection_reasons.append("zero_total_bytes")
    if observed_bytes <= 0:
        rejection_reasons.append("no_observed_bytes")
    if effective_seconds <= 0:
        rejection_reasons.append("no_effective_time")
    if session.had_error:
        rejection_reasons.append("session_error")
    if session.had_anomaly:
        rejection_reasons.append("session_anomaly")
    return {
        "downloader_id": session.downloader_id,
        "torrent_hash": session.torrent_hash,
        "name": session.name,
        "total_bytes": session.total_bytes,
        "observed_bytes": observed_bytes,
        "effective_seconds": effective_seconds,
        "average_speed_bps": average_speed_bps,
        "completed_at": completed_at,
        "eligible": not rejection_reasons,
        "rejection_reasons": rejection_reasons,
    }


def _complete_session(
    plugin: Any,
    runtime: SpeedMonitorRuntime,
    key: str,
    observed_at: float,
    resume_after_error: bool,
) -> bool:
    """结束完成会话并仅保存合格的健康样本候选。"""
    with runtime.session_lock(key):
        session = runtime.sessions.get(key)
        if session is None or session.status != SESSION_ACTIVE:
            return False
        if (
            not resume_after_error
            and session.last_state == TORRENT_ACTIVE
        ):
            session.effective_seconds += max(
                0.0, observed_at - session.last_effective_at
            )
        session.last_effective_at = observed_at
        session.last_valid_sample_at = observed_at
        stats = _completion_stats(session, observed_at)
        session.completion_stats = stats
        session.sample_eligible = bool(stats["eligible"])
        if session.sample_eligible:
            floor_speeds = getattr(
                plugin, "_speed_monitor_floor_speed_bps", {}
            )
            floor_speed = (
                floor_speeds.get(session.downloader_id, 0.0)
                if isinstance(floor_speeds, dict)
                else 0.0
            )
            baseline, accepted, rejection_reason = record_health_sample(
                runtime.baselines.get(session.downloader_id),
                stats,
                min_samples=_int(
                    getattr(plugin, "_speed_monitor_min_samples", 5), 5
                ),
                floor_speed_bps=_float(floor_speed),
            )
            runtime.baselines[session.downloader_id] = baseline
            session.sample_eligible = accepted
            if not accepted:
                stats["eligible"] = False
                stats["rejection_reasons"].append(rejection_reason)
        return _finish_session(runtime, key, "completed", observed_at)


def _mark_downloader_error(
    runtime: SpeedMonitorRuntime,
    downloader_id: str,
) -> None:
    """标记下载器错误期间仍活跃的会话不可作为健康样本。"""
    for session in runtime.sessions.values():
        if (
            session.downloader_id == downloader_id
            and session.status == SESSION_ACTIVE
        ):
            session.had_error = True


def _evaluate_session(
    plugin: Any,
    runtime: SpeedMonitorRuntime,
    key: str,
    snapshot: Any,
    observed_at: float,
) -> None:
    """更新活跃会话的当前速度与连续异常判定快照。"""
    session = runtime.sessions.get(key)
    if session is None or session.status != SESSION_ACTIVE:
        return
    mode = str(getattr(plugin, "_speed_monitor_mode", "auto") or "auto")
    reference_speed, reference_source = resolve_reference_speed(
        mode=mode,
        downloader_id=session.downloader_id,
        baseline=runtime.baselines.get(session.downloader_id),
        manual_speeds=getattr(plugin, "_speed_monitor_manual_speed_bps", {}),
        floor_speeds=getattr(plugin, "_speed_monitor_floor_speed_bps", {}),
    )
    session.current_speed_bps = max(
        0.0, _float(getattr(snapshot, "download_speed_bps", 0.0))
    )
    decision = evaluate_speed_anomaly(
        start_remaining_bytes=session.start_remaining_bytes,
        total_bytes=session.total_bytes,
        downloaded_bytes=session.last_downloaded_bytes,
        current_speed_bps=session.current_speed_bps,
        effective_seconds=session.effective_seconds,
        reference_speed_bps=reference_speed,
        reference_source=reference_source,
        tolerance=_float(getattr(plugin, "_speed_monitor_tolerance", 1.5), 1.5),
        grace_seconds=(
            _float(getattr(plugin, "_speed_monitor_grace_minutes", 10.0), 10.0)
            * 60.0
        ),
        required_samples=_int(
            getattr(plugin, "_speed_monitor_consecutive_abnormal_samples", 2), 2
        ),
        previous_abnormal_samples=session.consecutive_abnormal_samples,
    )
    session.decision = decision
    session.consecutive_abnormal_samples = _int(
        decision.get("abnormal_samples")
    )
    _update_anomaly_cycle(runtime, session, observed_at)


def _observe_snapshot(
    plugin: Any,
    runtime: SpeedMonitorRuntime,
    snapshot: Any,
    observed_at: float,
    resume_after_error: bool,
) -> tuple[bool, str]:
    """首次创建或刷新会话，并仅累计连续有效在线下载时长。"""
    if not snapshot.torrent_hash:
        return False, ""
    key = _session_key(snapshot.downloader_id, snapshot.torrent_hash)
    with runtime.session_lock(key):
        session = runtime.sessions.get(key)
        is_completed = (
            snapshot.state_category == TORRENT_COMPLETED
            or (
                snapshot.total_bytes > 0
                and snapshot.downloaded_bytes >= snapshot.total_bytes
            )
        )
        if is_completed:
            if session is not None and session.status == SESSION_ACTIVE:
                session.last_downloaded_bytes = snapshot.downloaded_bytes
                session.total_bytes = snapshot.total_bytes or session.total_bytes
                session.last_success_poll_at = observed_at
                _complete_session(
                    plugin, runtime, key, observed_at, resume_after_error
                )
            return False, key
        if session is None:
            is_active = snapshot.state_category == TORRENT_ACTIVE
            runtime.sessions[key] = SpeedMonitorSession(
                downloader_id=snapshot.downloader_id,
                downloader_type=snapshot.downloader_type,
                torrent_hash=snapshot.torrent_hash,
                name=snapshot.name,
                total_bytes=snapshot.total_bytes,
                start_downloaded_bytes=snapshot.downloaded_bytes,
                start_remaining_bytes=max(
                    0, snapshot.total_bytes - snapshot.downloaded_bytes
                ),
                last_downloaded_bytes=snapshot.downloaded_bytes,
                first_observed_at=observed_at,
                last_observed_at=observed_at,
                last_effective_at=observed_at,
                last_valid_sample_at=observed_at if is_active else 0.0,
                last_success_poll_at=observed_at,
                effective_seconds=0.0,
                last_state=snapshot.state_category,
            )
            return True, key
        if session.status != SESSION_ACTIVE:
            return False, key
        if (
            not resume_after_error
            and session.last_state == TORRENT_ACTIVE
            and snapshot.state_category == TORRENT_ACTIVE
        ):
            session.effective_seconds += max(
                0.0, observed_at - session.last_effective_at
            )
        session.name = snapshot.name or session.name
        session.total_bytes = snapshot.total_bytes or session.total_bytes
        session.last_downloaded_bytes = snapshot.downloaded_bytes
        session.last_observed_at = observed_at
        session.last_effective_at = observed_at
        session.last_success_poll_at = observed_at
        if snapshot.state_category == TORRENT_ACTIVE:
            session.last_valid_sample_at = observed_at
        session.last_state = snapshot.state_category
        if snapshot.state_category == TORRENT_ERROR:
            session.had_error = True
        return False, key


def scan_speed_monitor(plugin: Any, now: float | None = None) -> dict:
    """扫描全部已选下载器，持久化会话并区分空列表与 API 错误。"""
    if not is_speed_monitor_active(plugin):
        return {
            "scanned_downloaders": 0,
            "created_sessions": 0,
            "active_sessions": 0,
            "errors": {},
        }
    runtime = ensure_speed_monitor_runtime(plugin)
    if runtime.state_error:
        return {
            "scanned_downloaders": 0,
            "created_sessions": 0,
            "active_sessions": 0,
            "errors": {"state": runtime.state_error},
        }
    observed_at = float(time.time() if now is None else now)
    selected = list(dict.fromkeys(
        getattr(plugin, "_speed_monitor_downloaders", []) or []
    ))
    summary = {
        "scanned_downloaders": 0,
        "created_sessions": 0,
        "active_sessions": 0,
        "errors": {},
    }
    for downloader_id in selected:
        if not isinstance(downloader_id, str) or not downloader_id.strip():
            continue
        downloader_id = downloader_id.strip()
        with runtime.downloader_lock(downloader_id):
            service = plugin.service_info(downloader_id)
            if not service or not getattr(service, "instance", None):
                summary["errors"][downloader_id] = "downloader unavailable"
                runtime.last_poll_results[downloader_id] = poll_error(
                    "downloader unavailable"
                )
                _mark_downloader_error(runtime, downloader_id)
                continue
            downloader_type = _downloader_type(service)
            if downloader_type not in SUPPORTED_DOWNLOADER_TYPES:
                summary["errors"][downloader_id] = "unsupported downloader"
                runtime.last_poll_results[downloader_id] = poll_error(
                    "unsupported downloader"
                )
                _mark_downloader_error(runtime, downloader_id)
                continue
            previous_result = runtime.last_poll_results.get(downloader_id)
            result = poll_downloader(service.instance, downloader_id, downloader_type)
            runtime.last_poll_results[downloader_id] = result
            summary["scanned_downloaders"] += 1
            if not result.success:
                summary["errors"][downloader_id] = result.error
                _mark_downloader_error(runtime, downloader_id)
                continue
            resume_after_error = bool(previous_result and not previous_result.success)
            seen_keys = set()
            for snapshot in result.items:
                created, key = _observe_snapshot(
                    plugin, runtime, snapshot, observed_at, resume_after_error
                )
                if key:
                    seen_keys.add(key)
                    _evaluate_session(plugin, runtime, key, snapshot, observed_at)
                if created:
                    summary["created_sessions"] += 1
            for key, session in list(runtime.sessions.items()):
                if (
                    session.downloader_id == downloader_id
                    and session.status == SESSION_ACTIVE
                    and key not in seen_keys
                ):
                    _finish_session(runtime, key, "missing", observed_at)
    dispatch_pending_speed_alerts(plugin, runtime, observed_at)
    persist_speed_monitor_runtime(plugin, runtime, observed_at)
    summary["active_sessions"] = sum(
        session.status == SESSION_ACTIVE
        for session in runtime.sessions.values()
    )
    return summary


def handle_download_added_event(
    plugin: Any,
    event: Any,
    now: float | None = None,
) -> dict:
    """处理下载新增事件并立即为目标任务建立监控会话。"""
    if not is_speed_monitor_active(plugin):
        return {
            "handled": False,
            "reason": "monitor disabled",
            "created_sessions": 0,
            "active_sessions": 0,
            "errors": {},
        }

    runtime = ensure_speed_monitor_runtime(plugin)
    if runtime.state_error:
        return {
            "handled": False,
            "reason": "state error",
            "created_sessions": 0,
            "active_sessions": 0,
            "errors": {"state": runtime.state_error},
        }

    event_data = getattr(event, "event_data", None)
    if not isinstance(event_data, dict):
        event_data = {}
    downloader_id = str(
        event_data.get("downloader")
        or event_data.get("downloader_name")
        or ""
    ).strip()
    torrent_hash = str(
        event_data.get("hash") or event_data.get("torrent_hash") or ""
    ).strip().lower()
    selected = {
        str(value).strip()
        for value in (getattr(plugin, "_speed_monitor_downloaders", []) or [])
        if str(value).strip()
    }
    if not downloader_id or not torrent_hash or downloader_id not in selected:
        return {
            "handled": False,
            "reason": "event outside selected downloaders",
            "created_sessions": 0,
            "active_sessions": sum(
                session.status == SESSION_ACTIVE for session in runtime.sessions.values()
            ),
            "errors": {},
        }

    observed_at = float(time.time() if now is None else now)
    with runtime.downloader_lock(downloader_id):
        service = plugin.service_info(downloader_id)
        if not service or not getattr(service, "instance", None):
            error = "downloader unavailable"
            runtime.last_poll_results[downloader_id] = poll_error(error)
            _mark_downloader_error(runtime, downloader_id)
            persist_speed_monitor_runtime(plugin, runtime, observed_at)
            return {
                "handled": False,
                "reason": error,
                "created_sessions": 0,
                "active_sessions": sum(
                    session.status == SESSION_ACTIVE
                    for session in runtime.sessions.values()
                ),
                "errors": {downloader_id: error},
            }

        downloader_type = _downloader_type(service)
        if downloader_type not in SUPPORTED_DOWNLOADER_TYPES:
            error = "unsupported downloader"
            runtime.last_poll_results[downloader_id] = poll_error(error)
            _mark_downloader_error(runtime, downloader_id)
            persist_speed_monitor_runtime(plugin, runtime, observed_at)
            return {
                "handled": False,
                "reason": error,
                "created_sessions": 0,
                "active_sessions": sum(
                    session.status == SESSION_ACTIVE
                    for session in runtime.sessions.values()
                ),
                "errors": {downloader_id: error},
            }

        previous_result = runtime.last_poll_results.get(downloader_id)
        result = poll_downloader(service.instance, downloader_id, downloader_type)
        runtime.last_poll_results[downloader_id] = result
        if not result.success:
            _mark_downloader_error(runtime, downloader_id)
            persist_speed_monitor_runtime(plugin, runtime, observed_at)
            return {
                "handled": False,
                "reason": result.error,
                "created_sessions": 0,
                "active_sessions": sum(
                    session.status == SESSION_ACTIVE
                    for session in runtime.sessions.values()
                ),
                "errors": {downloader_id: result.error},
            }

        snapshot = next(
            (
                item
                for item in result.items
                if str(item.torrent_hash or "").strip().lower() == torrent_hash
            ),
            None,
        )
        created = False
        key = _session_key(downloader_id, torrent_hash)
        if snapshot is not None:
            created, key = _observe_snapshot(
                plugin,
                runtime,
                snapshot,
                observed_at,
                bool(previous_result and not previous_result.success),
            )
            _evaluate_session(plugin, runtime, key, snapshot, observed_at)

    dispatch_pending_speed_alerts(plugin, runtime, observed_at)
    persist_speed_monitor_runtime(plugin, runtime, observed_at)
    return {
        "handled": snapshot is not None,
        "found": snapshot is not None,
        "created_sessions": int(created),
        "active_sessions": sum(
            session.status == SESSION_ACTIVE for session in runtime.sessions.values()
        ),
        "errors": {},
    }


def reset_speed_monitor_baseline(
    plugin: Any,
    downloader_id: str,
    now: float | None = None,
) -> dict:
    """显式重置指定下载器基准并立即持久化。"""
    runtime = ensure_speed_monitor_runtime(plugin)
    if runtime.state_error:
        return {"success": False, "error": runtime.state_error}
    clean_id = str(downloader_id or "").strip()
    if not clean_id:
        return {"success": False, "error": "downloader_id is required"}
    observed_at = float(time.time() if now is None else now)
    baseline = reset_downloader_baseline(
        runtime.baselines, clean_id, reset_at=observed_at
    )
    persist_speed_monitor_runtime(plugin, runtime, observed_at)
    return {
        "success": True,
        "downloader_id": clean_id,
        "baseline": dict(baseline),
    }
