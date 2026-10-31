"""Webhook event service helpers for DoubanCenter."""

import threading
from collections.abc import Callable, Mapping

from app.sdk.events import Event

from . import folio, lifecycle


def _is_played_event(event_info) -> bool:
    """只认可服务端完播证据，不用停止事件或转码百分比猜测观看完成。"""
    name = getattr(event_info, "event", None)
    channel = getattr(event_info, "channel", None)
    payload = getattr(event_info, "json_object", None)
    payload = payload if isinstance(payload, Mapping) else {}
    if channel == "jellyfin":
        if name == "PlaybackStop":
            return payload.get("PlayedToCompletion") is True
        if name != "UserDataSaved":
            return False
        reason = getattr(event_info, "save_reason", None)
        if reason == "TogglePlayed":
            # 兼容不含 Played 的旧模板；有该字段时必须排除取消已看。
            return "Played" not in payload or payload["Played"] is True
        return reason == "PlaybackFinished" and payload.get("Played") is True
    if name in {"item.markplayed", "media.scrobble"}:
        return True
    if channel == "emby" and name == "playback.stop":
        playback = payload.get("PlaybackInfo")
        return isinstance(playback, Mapping) and playback.get("PlayedToCompletion") is True
    return False


@lifecycle.managed
def handle_sync_log(plugin, event: Event, played: bool = False) -> None:
    """处理媒体播放事件并同步到豆瓣时间。"""
    if not plugin._enabled or not plugin._folio_enabled:
        return
    event_info = event.event_data
    if not played and (
        getattr(event_info, "event", None) not in {"playback.start", "media.play", "PlaybackStart"}
        or getattr(event_info, "user_name", None) not in (plugin._folio_user or "").split(",")
    ):
        return
    if not hasattr(plugin, "_sync_lock"):
        plugin._sync_lock = threading.Lock()
    # 不同媒体的已看事件不能当作重复请求丢弃；等待当前实例完成后逐条处理。
    with lifecycle.serialized(plugin, plugin._sync_lock):
        lifecycle.checkpoint(plugin)
        if not plugin._enabled or not plugin._folio_enabled:
            return
        folio.check_cookie_periodically(plugin)
        lifecycle.checkpoint(plugin)
        folio.sync_log_handler(plugin, event.event_data, played=played)


def handle_sync_played(plugin, event: Event, sync_log: Callable[..., None]) -> None:
    """处理已播放事件并串行执行豆瓣时间同步。"""
    if not plugin._enabled or not plugin._folio_enabled:
        return
    event_info = event.event_data
    user_name = getattr(event_info, "user_name", None)
    if user_name and user_name in (plugin._folio_user or "").split(",") and _is_played_event(event_info):
        sync_log(event=event, played=True)
