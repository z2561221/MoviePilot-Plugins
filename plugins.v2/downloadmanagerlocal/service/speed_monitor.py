"""下载速度异常监控扫描与会话运行时。"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from ..utils.torrent_adapter import (
    TORRENT_COMPLETED,
    DownloaderPollResult,
    poll_downloader,
)
from ..utils.config import is_speed_monitor_active


SUPPORTED_DOWNLOADER_TYPES = {"qbittorrent", "transmission"}


@dataclass
class SpeedMonitorSession:
    """从插件首次观察开始计时的下载任务会话。"""

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
    last_state: str


class SpeedMonitorRuntime:
    """隔离多下载器扫描锁、会话锁和当前活跃会话。"""

    def __init__(self) -> None:
        """初始化线程安全的内存运行态。"""
        self._lock = threading.RLock()
        self.downloader_locks: dict[str, threading.RLock] = {}
        self.session_locks: dict[str, threading.RLock] = {}
        self.sessions: dict[str, SpeedMonitorSession] = {}
        self.last_poll_results: dict[str, DownloaderPollResult] = {}

    def downloader_lock(self, downloader_id: str) -> threading.RLock:
        """返回指定下载器实例独享的扫描锁。"""
        with self._lock:
            return self.downloader_locks.setdefault(downloader_id, threading.RLock())

    def session_lock(self, session_key: str) -> threading.RLock:
        """返回指定下载会话独享的状态锁。"""
        with self._lock:
            return self.session_locks.setdefault(session_key, threading.RLock())


def ensure_speed_monitor_runtime(plugin: Any) -> SpeedMonitorRuntime:
    """确保插件持有速度监控内存运行态。"""
    runtime = getattr(plugin, "_speed_monitor_runtime", None)
    if not isinstance(runtime, SpeedMonitorRuntime):
        runtime = SpeedMonitorRuntime()
        plugin._speed_monitor_runtime = runtime
    return runtime


def stop_speed_monitor_runtime(plugin: Any) -> None:
    """停止速度监控内存运行态并释放锁引用。"""
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


def _session_key(downloader_id: str, torrent_hash: str) -> str:
    """生成按下载器实例隔离的稳定会话 key。"""
    return f"{downloader_id}:{torrent_hash}"


def _observe_snapshot(
    runtime: SpeedMonitorRuntime,
    snapshot: Any,
    observed_at: float,
) -> bool:
    """首次创建会话或刷新既有会话，不回填未知历史时长。"""
    if (
        not snapshot.torrent_hash
        or snapshot.state_category == TORRENT_COMPLETED
        or (snapshot.total_bytes > 0 and snapshot.downloaded_bytes >= snapshot.total_bytes)
    ):
        return False
    key = _session_key(snapshot.downloader_id, snapshot.torrent_hash)
    with runtime.session_lock(key):
        session = runtime.sessions.get(key)
        if session is None:
            runtime.sessions[key] = SpeedMonitorSession(
                downloader_id=snapshot.downloader_id,
                downloader_type=snapshot.downloader_type,
                torrent_hash=snapshot.torrent_hash,
                name=snapshot.name,
                total_bytes=snapshot.total_bytes,
                start_downloaded_bytes=snapshot.downloaded_bytes,
                start_remaining_bytes=max(0, snapshot.total_bytes - snapshot.downloaded_bytes),
                last_downloaded_bytes=snapshot.downloaded_bytes,
                first_observed_at=observed_at,
                last_observed_at=observed_at,
                last_state=snapshot.state_category,
            )
            return True
        session.name = snapshot.name or session.name
        session.total_bytes = snapshot.total_bytes or session.total_bytes
        session.last_downloaded_bytes = snapshot.downloaded_bytes
        session.last_observed_at = observed_at
        session.last_state = snapshot.state_category
        return False


def scan_speed_monitor(plugin: Any, now: float | None = None) -> dict:
    """扫描全部已选下载器并建立或刷新活跃下载会话。"""
    if not is_speed_monitor_active(plugin):
        return {
            "scanned_downloaders": 0,
            "created_sessions": 0,
            "active_sessions": 0,
            "errors": {},
        }
    runtime = ensure_speed_monitor_runtime(plugin)
    observed_at = float(time.time() if now is None else now)
    selected = list(dict.fromkeys(getattr(plugin, "_speed_monitor_downloaders", []) or []))
    summary = {
        "scanned_downloaders": 0,
        "created_sessions": 0,
        "active_sessions": len(runtime.sessions),
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
                continue
            downloader_type = _downloader_type(service)
            if downloader_type not in SUPPORTED_DOWNLOADER_TYPES:
                summary["errors"][downloader_id] = "unsupported downloader"
                continue
            result = poll_downloader(service.instance, downloader_id, downloader_type)
            runtime.last_poll_results[downloader_id] = result
            summary["scanned_downloaders"] += 1
            if not result.success:
                summary["errors"][downloader_id] = result.error
                continue
            for snapshot in result.items:
                if _observe_snapshot(runtime, snapshot, observed_at):
                    summary["created_sessions"] += 1
    summary["active_sessions"] = len(runtime.sessions)
    return summary
