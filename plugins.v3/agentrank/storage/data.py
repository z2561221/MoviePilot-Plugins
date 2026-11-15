"""Own plugin data reads, validation, readback and reversible raw updates."""

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any, TypeVar

ModelType = TypeVar("ModelType")


class PluginDataStore:
    """Share one data facility between leaf stores and transaction coordinators."""

    def __init__(self, plugin: Any, recovery_log_key: str) -> None:
        """Bind the plugin API and its existing recovery-log key."""
        self._plugin = plugin
        self.recovery_log_key = recovery_log_key

    def get_data(self, key: str | None = None) -> Any:
        """Read plugin data through the same owner interface."""
        return self._plugin.get_data(key=key)

    def save_data(self, key: str, value: Any) -> None:
        """Write plugin data through the same owner interface."""
        self._plugin.save_data(key=key, value=value)

    def del_data(self, key: str) -> Any:
        """Delete plugin data through the same owner interface."""
        return self._plugin.del_data(key=key)

    def record_recovery(self, key: str, action: str, detail: str = "") -> None:
        """记录迁移或损坏数据恢复证据，且不因日志损坏而失败。"""
        try:
            history = self._plugin.get_data(key=self.recovery_log_key)
            history = list(history) if isinstance(history, list) else []
        except Exception:
            history = []
        history.append(
            {
                "key": key,
                "action": action,
                "detail": detail,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._plugin.save_data(key=self.recovery_log_key, value=history[-100:])

    def atomic_update(
        self,
        *,
        updates: Mapping[str, Any] = None,
        delete_keys: Iterable[str] = (),
        recovery_key: str,
        action: str,
    ) -> None:
        """原子应用一组插件数据变更，失败时逐键恢复旧状态。"""
        safe_updates = dict(updates or {})
        safe_deletes = [
            str(key)
            for key in dict.fromkeys(delete_keys or ())
            if key not in safe_updates
        ]
        touched = list(safe_updates) + safe_deletes
        old_values = {key: self._plugin.get_data(key=key) for key in touched}
        try:
            for key, value in safe_updates.items():
                self._plugin.save_data(key=key, value=value)
            for key in safe_deletes:
                self._plugin.del_data(key=key)
            for key, value in safe_updates.items():
                if self._plugin.get_data(key=key) != value:
                    raise ValueError(f"profile data readback mismatch: {key}")
            for key in safe_deletes:
                if self._plugin.get_data(key=key) is not None:
                    raise ValueError(f"profile data delete readback mismatch: {key}")
        except Exception as error:
            rollback_errors: list[str] = []
            for key in reversed(touched):
                try:
                    self.restore_raw(key, old_values[key])
                except Exception as rollback_error:
                    rollback_errors.append(f"{key}: {rollback_error}")
            detail = type(error).__name__
            if rollback_errors:
                detail = f"{detail}; rollback_failed={len(rollback_errors)}"
            try:
                self.record_recovery(recovery_key, action, detail)
            except Exception:
                pass
            if rollback_errors:
                raise RuntimeError(
                    "profile data update and rollback both failed"
                ) from error
            raise

    def load_model(
        self,
        key: str,
        model_type: type[ModelType],
    ) -> ModelType | None:
        """容错读取新命名空间模型，不触碰旧 username 键。"""
        value = self._plugin.get_data(key=key)
        if value is None:
            return None
        try:
            model = model_type.from_dict(value)
        except (TypeError, ValueError, KeyError) as error:
            self.record_recovery(key, "ignored_corrupt_data", str(error))
            return None
        return model

    def load_scoped_model(
        self,
        key: str,
        model_type: type[ModelType],
        profile_id: str,
    ) -> ModelType | None:
        """读取并校验载荷 profile_id 与请求作用域完全一致。"""
        model = self.load_model(key, model_type)
        if model is None:
            return None
        stored_profile_id = str(getattr(model, "profile_id", "") or "")
        if stored_profile_id != str(profile_id):
            self.record_recovery(
                key,
                "ignored_cross_profile_data",
                stored_profile_id,
            )
            return None
        return model

    def data_entries(self) -> list[tuple[str, Any]]:
        """读取宿主全部插件数据行，兼容模型对象和测试字典。"""
        try:
            raw = self._plugin.get_data()
        except (TypeError, AttributeError):
            return []
        if isinstance(raw, Mapping):
            return [(str(key), value) for key, value in raw.items()]
        entries: list[tuple[str, Any]] = []
        for record in raw or ():
            if isinstance(record, Mapping):
                key = record.get("key")
                value = record.get("value")
            else:
                key = getattr(record, "key", None)
                value = getattr(record, "value", None)
            if key not in (None, ""):
                entries.append((str(key), value))
        return entries

    def restore_raw(self, key: str, value: Any) -> None:
        """在复合写入失败后恢复单个键的原始值。"""
        if value is None:
            self._plugin.del_data(key=key)
        else:
            self._plugin.save_data(key=key, value=value)
