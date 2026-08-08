"""下载速度监控按需后台 worker。"""

from __future__ import annotations

import logging
import threading
from typing import Any

from .speed_monitor import SESSION_ACTIVE
from ..utils.config import is_speed_monitor_active


logger = logging.getLogger(__name__)
_CONTROL_LOCK = threading.RLock()


def _worker_lock(plugin: Any) -> threading.RLock:
    """获取插件实例独享的速度监控 worker 锁。"""
    lock = getattr(plugin, "_speed_monitor_worker_lock", None)
    if lock is None:
        with _CONTROL_LOCK:
            lock = getattr(plugin, "_speed_monitor_worker_lock", None)
            if lock is None:
                lock = threading.RLock()
                plugin._speed_monitor_worker_lock = lock
    return lock


def _runtime_has_active_sessions(runtime: Any) -> bool:
    """判断指定运行态中是否仍有活跃监控会话。"""
    sessions = getattr(runtime, "sessions", {}) or {}
    return any(
        getattr(session, "status", "") == SESSION_ACTIVE
        for session in sessions.values()
    )


def is_speed_monitor_worker_running(plugin: Any) -> bool:
    """判断插件实例的速度监控 worker 是否正在运行。"""
    with _worker_lock(plugin):
        thread = getattr(plugin, "_speed_monitor_thread", None)
        return bool(thread and thread.is_alive())


def start_speed_monitor_worker(plugin: Any) -> bool:
    """确保插件实例只启动一个速度监控 worker。"""
    lock = _worker_lock(plugin)
    with lock:
        current = getattr(plugin, "_speed_monitor_thread", None)
        if current and current.is_alive():
            return False
        stop_event = threading.Event()
        thread = threading.Thread(
            target=_speed_monitor_loop,
            args=(plugin, stop_event),
            name=f"{plugin.__class__.__name__}-SpeedMonitor",
            daemon=True,
        )
        plugin._speed_monitor_stop_event = stop_event
        plugin._speed_monitor_thread = thread
        try:
            thread.start()
        except Exception:
            plugin._speed_monitor_thread = None
            plugin._speed_monitor_stop_event = None
            raise
        return True


def start_speed_monitor_worker_if_needed(plugin: Any, runtime: Any) -> bool:
    """仅在恢复出的运行态仍有活跃会话时启动 worker。"""
    if not _runtime_has_active_sessions(runtime):
        return False
    return start_speed_monitor_worker(plugin)


def _speed_monitor_loop(plugin: Any, stop_event: threading.Event) -> None:
    """按配置间隔扫描，最后一个活跃会话结束后自动退出。"""
    lock = _worker_lock(plugin)
    try:
        while True:
            interval = max(
                10,
                min(300, int(getattr(plugin, "_speed_monitor_interval_seconds", 30) or 30)),
            )
            if stop_event.wait(interval):
                return
            try:
                result = plugin._scan_download_speed()
            except Exception:
                logger.exception("下载速度监控 worker 扫描失败，将在下一轮重试")
                continue
            if not isinstance(result, dict) or int(result.get("active_sessions") or 0) > 0:
                continue
            with lock:
                runtime = getattr(plugin, "_speed_monitor_runtime", None)
                if (
                    is_speed_monitor_active(plugin)
                    and _runtime_has_active_sessions(runtime)
                ):
                    continue
                if getattr(plugin, "_speed_monitor_thread", None) is threading.current_thread():
                    plugin._speed_monitor_thread = None
                if getattr(plugin, "_speed_monitor_stop_event", None) is stop_event:
                    plugin._speed_monitor_stop_event = None
                return
    finally:
        with lock:
            if getattr(plugin, "_speed_monitor_thread", None) is threading.current_thread():
                plugin._speed_monitor_thread = None
            if getattr(plugin, "_speed_monitor_stop_event", None) is stop_event:
                plugin._speed_monitor_stop_event = None


def stop_speed_monitor_worker(plugin: Any, join_timeout: float = 10.0) -> bool:
    """停止并等待插件实例的速度监控 worker 退出。"""
    lock = _worker_lock(plugin)
    with lock:
        thread = getattr(plugin, "_speed_monitor_thread", None)
        stop_event = getattr(plugin, "_speed_monitor_stop_event", None)
        if stop_event is not None:
            stop_event.set()
        if thread is None:
            plugin._speed_monitor_stop_event = None
            return False
    if thread is not threading.current_thread() and thread.is_alive():
        thread.join(timeout=max(0.0, float(join_timeout)))
    with lock:
        if not thread.is_alive():
            if getattr(plugin, "_speed_monitor_thread", None) is thread:
                plugin._speed_monitor_thread = None
            if getattr(plugin, "_speed_monitor_stop_event", None) is stop_event:
                plugin._speed_monitor_stop_event = None
    return True


__all__ = (
    "is_speed_monitor_worker_running",
    "start_speed_monitor_worker",
    "start_speed_monitor_worker_if_needed",
    "stop_speed_monitor_worker",
)
