"""Webhook event service helpers for DoubanCenter."""

import datetime
import threading
from typing import Callable

from app.core.event import Event

_played_lock = threading.Lock()


def handle_sync_log(plugin, event: Event, played: bool = False) -> None:
    """Handle media playback events and sync them to Douban folio."""
    if not plugin._enabled or not plugin._folio_enabled:
        return
    if not hasattr(plugin, "_sync_lock"):
        plugin._sync_lock = threading.Lock()
    if not plugin._sync_lock.acquire(blocking=False):
        now = datetime.datetime.now().timestamp()
        if not hasattr(plugin, "_last_skip_log_time"):
            plugin._last_skip_log_time = 0
        if now - plugin._last_skip_log_time > 600:
            plugin._last_skip_log_time = now
        return
    try:
        from .. import folio

        folio.check_cookie_periodically(plugin)
        folio.sync_log_handler(plugin, event.event_data, played=played)
    finally:
        plugin._sync_lock.release()


def handle_sync_played(plugin, event: Event, sync_log: Callable[..., None]) -> None:
    """Handle explicit played/scrobble events and serialize folio sync."""
    if not plugin._enabled or not plugin._folio_enabled:
        return
    event_info = event.event_data
    played_events = {"item.markplayed", "media.scrobble"}
    is_played = event_info.event in played_events
    if event_info.channel == "jellyfin":
        is_played = event_info.event == "UserDataSaved" and event_info.save_reason == "TogglePlayed"
    if is_played and event_info.user_name in plugin._folio_user.split(","):
        with _played_lock:
            sync_log(event=event, played=True)
