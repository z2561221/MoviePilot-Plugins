"""Share locks within a plugin data namespace without retaining idle locks."""

import threading
from dataclasses import dataclass
from weakref import WeakValueDictionary

from app.sdk.plugin import _PluginBase


@dataclass(frozen=True, eq=False)
class _ObjectNamespace:
    """Keep custom data owners separate and prevent object ID reuse."""

    owner: object

    def __hash__(self) -> int:
        return id(self.owner)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _ObjectNamespace) and self.owner is other.owner


class RepositoryLocks:
    """Share active locks while contexts and waiters keep strong references."""

    _guard = threading.Lock()
    _locks: WeakValueDictionary[tuple[object, str, str], threading.RLock] = (
        WeakValueDictionary()
    )

    def __init__(self, plugin: object) -> None:
        """Resolve the native SDK data namespace or a custom owner's identity."""
        # 宿主 44606a 的原生 get_data/save_data/del_data 默认均以实例类名为键。
        # 自定义 get_data 按对象身份隔离.
        native_read = getattr(_PluginBase, "get_data", None)
        actual_read = getattr(getattr(plugin, "get_data", None), "__func__", None)
        self._namespace = (
            ("plugin", plugin.__class__.__name__)
            if native_read is not None and actual_read is native_read
            else _ObjectNamespace(plugin)
        )

    def lock(self, kind: str, profile_scope: str = "") -> threading.RLock:
        """Return a shared reentrant lock without extending its idle lifetime."""
        key = (self._namespace, kind, profile_scope)
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.RLock()
                self._locks[key] = lock
            return lock

    @classmethod
    def live_lock_count(cls) -> int:
        """Count registry entries that are still held or referenced."""
        with cls._guard:
            return len(cls._locks)
