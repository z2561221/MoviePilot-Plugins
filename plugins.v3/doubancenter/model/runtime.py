"""插件实例内存状态的唯一归属；不改变宿主配置和持久化数据键。"""

from dataclasses import dataclass, field
from threading import Event, Lock, RLock
from typing import Any


@dataclass
class RuntimeState:
    stop_event: Event | None = None
    sync_lock: Any = field(default_factory=Lock)
    rank_lock: Any = field(default_factory=RLock)
    poster_lock: Any = field(default_factory=RLock)
    series_cache: dict = field(default_factory=dict)
    poster_cache: dict = field(default_factory=dict)
    season_cache: dict = field(default_factory=dict)
    repair_plans: dict = field(default_factory=dict)
    waiting: dict | None = None
    notification_times: dict = field(default_factory=dict)
    last_cookie_check: float = 0


class _StateField:
    """保留既有内部字段名，让服务和旧实例接入统一状态容器。"""

    def __init__(self, name):
        self.name = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return getattr(instance.runtime_state, self.name)

    def __set__(self, instance, value):
        setattr(instance.runtime_state, self.name, value)


class RuntimeOwner:
    @property
    def runtime_state(self) -> RuntimeState:
        state = self.__dict__.get("_runtime_state")
        if state is None:
            state = RuntimeState()
            self._runtime_state = state
        return state

    _run_stop = _StateField("stop_event")
    _sync_lock = _StateField("sync_lock")
    _rank_lock = _StateField("rank_lock")
    _folio_poster_lock = _StateField("poster_lock")
    _folio_series_cache = _StateField("series_cache")
    _folio_library_poster_cache = _StateField("poster_cache")
    _folio_library_season_cache = _StateField("season_cache")
    _folio_repair_plans = _StateField("repair_plans")
    _wait_process = _StateField("waiting")
    _wish_notification_last_times = _StateField("notification_times")
    _last_cookie_check_time = _StateField("last_cookie_check")
