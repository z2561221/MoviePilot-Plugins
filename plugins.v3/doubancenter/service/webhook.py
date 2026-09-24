"""Webhook event service helpers for DoubanCenter."""

import threading
from typing import Callable

from app.sdk.events import Event

from . import folio

def handle_sync_log(plugin, event: Event, played: bool = False) -> None:
    """处理媒体播放事件并同步到豆瓣时间。"""
    if not plugin._enabled or not plugin._folio_enabled:
        return
    if not hasattr(plugin, "_sync_lock"):
        plugin._sync_lock = threading.Lock()
    # 不同媒体的已看事件不能当作重复请求丢弃；等待当前实例完成后逐条处理。
    with plugin._sync_lock:
        folio.check_cookie_periodically(plugin)
        folio.sync_log_handler(plugin, event.event_data, played=played)


def handle_sync_played(plugin, event: Event, sync_log: Callable[..., None]) -> None:
    """处理已播放事件并串行执行豆瓣时间同步。"""
    if not plugin._enabled or not plugin._folio_enabled:
        return
    event_info = event.event_data
    played_events = {"item.markplayed", "media.scrobble"}
    is_played = event_info.event in played_events
    if event_info.channel == "jellyfin":
        is_played = event_info.event == "UserDataSaved" and event_info.save_reason == "TogglePlayed"
    if is_played and event_info.user_name in plugin._folio_user.split(","):
        sync_log(event=event, played=True)
