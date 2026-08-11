"""上传限速常驻协调 worker。"""

from __future__ import annotations

import logging
import threading
from typing import Any

from ..model.upload_limit import UPLOAD_LIMIT_INTERVAL_SECONDS
from ..utils.config import is_upload_limit_active


logger = logging.getLogger(__name__)
_CONTROL_LOCK = threading.RLock()


def start_upload_limit_worker(plugin: Any) -> bool:
    """确保插件实例只启动一个上传限速协调 worker。"""
    with _worker_lock(plugin):
        current = getattr(plugin, "_upload_limit_thread", None)
        if current and current.is_alive():
            return False
        stop_event = threading.Event()
        wake_event = threading.Event()
        thread = threading.Thread(
            target=_upload_limit_loop,
            args=(plugin, stop_event, wake_event),
            name=f"{plugin.__class__.__name__}-UploadLimiter",
            daemon=True,
        )
        plugin._upload_limit_stop_event = stop_event
        plugin._upload_limit_wake_event = wake_event
        plugin._upload_limit_thread = thread
        try:
            thread.start()
        except Exception:
            plugin._upload_limit_thread = None
            plugin._upload_limit_stop_event = None
            plugin._upload_limit_wake_event = None
            raise
        return True


def wake_upload_limit_worker(plugin: Any) -> bool:
    """唤醒协调 worker 立即执行一轮重新分配。"""
    with _worker_lock(plugin):
        wake_event = getattr(plugin, "_upload_limit_wake_event", None)
        thread = getattr(plugin, "_upload_limit_thread", None)
        if not wake_event or not thread or not thread.is_alive():
            return False
        wake_event.set()
        return True


def is_upload_limit_worker_running(plugin: Any) -> bool:
    """判断上传限速协调 worker 是否正在运行。"""
    with _worker_lock(plugin):
        thread = getattr(plugin, "_upload_limit_thread", None)
        return bool(thread and thread.is_alive())


def stop_upload_limit_worker(plugin: Any, join_timeout: float = 10.0) -> bool:
    """停止 worker；仅结束协调，不恢复已写入下载器的限速。"""
    with _worker_lock(plugin):
        thread = getattr(plugin, "_upload_limit_thread", None)
        stop_event = getattr(plugin, "_upload_limit_stop_event", None)
        wake_event = getattr(plugin, "_upload_limit_wake_event", None)
        if stop_event is not None:
            stop_event.set()
        if wake_event is not None:
            wake_event.set()
        if thread is None:
            plugin._upload_limit_stop_event = None
            plugin._upload_limit_wake_event = None
            return False
    if thread is not threading.current_thread() and thread.is_alive():
        thread.join(timeout=max(0.0, float(join_timeout)))
    with _worker_lock(plugin):
        if not thread.is_alive():
            if getattr(plugin, "_upload_limit_thread", None) is thread:
                plugin._upload_limit_thread = None
            if getattr(plugin, "_upload_limit_stop_event", None) is stop_event:
                plugin._upload_limit_stop_event = None
            if getattr(plugin, "_upload_limit_wake_event", None) is wake_event:
                plugin._upload_limit_wake_event = None
    return True


def _upload_limit_loop(
    plugin: Any,
    stop_event: threading.Event,
    wake_event: threading.Event,
) -> None:
    """启动后立即协调，并按 30 秒或事件唤醒持续重新分配。"""
    try:
        while not stop_event.is_set():
            if not is_upload_limit_active(plugin):
                return
            try:
                plugin._coordinate_upload_limits()
            except Exception:
                logger.exception("上传限速协调 worker 执行失败，将在下一轮重试")
            if stop_event.is_set():
                return
            wake_event.wait(UPLOAD_LIMIT_INTERVAL_SECONDS)
            wake_event.clear()
    finally:
        with _worker_lock(plugin):
            if getattr(plugin, "_upload_limit_thread", None) is threading.current_thread():
                plugin._upload_limit_thread = None
            if getattr(plugin, "_upload_limit_stop_event", None) is stop_event:
                plugin._upload_limit_stop_event = None
            if getattr(plugin, "_upload_limit_wake_event", None) is wake_event:
                plugin._upload_limit_wake_event = None


def _worker_lock(plugin: Any) -> threading.RLock:
    """获取插件实例独享的上传限速 worker 控制锁。"""
    lock = getattr(plugin, "_upload_limit_worker_lock", None)
    if lock is None:
        with _CONTROL_LOCK:
            lock = getattr(plugin, "_upload_limit_worker_lock", None)
            if lock is None:
                lock = threading.RLock()
                plugin._upload_limit_worker_lock = lock
    return lock


__all__ = (
    "is_upload_limit_worker_running",
    "start_upload_limit_worker",
    "stop_upload_limit_worker",
    "wake_upload_limit_worker",
)
