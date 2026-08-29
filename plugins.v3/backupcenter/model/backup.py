"""备份范围与恢复范围的数据模型。"""

from dataclasses import asdict, dataclass
import re
from typing import Any, Dict, Iterable, List


class ScopeError(ValueError):
    """表示备份或恢复范围无效。"""


@dataclass(frozen=True)
class BackupScope:
    """描述一份备份中包含的数据类别。"""

    mp_settings: bool = False
    plugin_settings: bool = True
    plugin_data: bool = True
    plugin_files: bool = True
    app_env: bool = False
    cookies: bool = False
    database: bool = False

    @classmethod
    def from_payload(cls, payload: Dict[str, Any] | None) -> "BackupScope":
        """从 API 请求体构造经过默认值归一化的备份范围。"""
        raw = payload or {}
        scope = cls(
            mp_settings=bool(raw.get("mp_settings", False)),
            plugin_settings=bool(raw.get("plugin_settings", True)),
            plugin_data=bool(raw.get("plugin_data", True)),
            plugin_files=bool(raw.get("plugin_files", True)),
            app_env=bool(raw.get("app_env", False)),
            cookies=bool(raw.get("cookies", False)),
            database=bool(raw.get("database", False)),
        )
        if scope.database:
            raise ScopeError("完整数据库备份由 MoviePilot 主程序管理")
        if not any(asdict(scope).values()):
            raise ScopeError("至少选择一项备份内容")
        return scope

    def to_dict(self) -> Dict[str, bool]:
        """返回可安全写入 manifest 的范围字典。"""
        return {
            key: value
            for key, value in asdict(self).items()
            if key != "database"
        }


@dataclass(frozen=True)
class ManualBackupSelection:
    """描述 MoviePilot 或单插件手动备份的显式范围。"""

    target: str = "plugin"
    configuration: bool = False
    data: bool = False
    mp_settings: bool = False
    plugin_settings: bool = False
    plugin_data: bool = False
    plugin_files: bool = False
    app_env: bool = False
    cookies: bool = False
    database: bool = False

    @classmethod
    def from_payload(
        cls, payload: Dict[str, Any] | None, target: Any = "plugin"
    ) -> "ManualBackupSelection":
        """从请求构造默认全空的手动备份选择。"""
        raw = payload or {}
        normalized_target = str(target or "").strip().lower()
        if normalized_target not in {"moviepilot", "plugin"}:
            raise ScopeError("手动备份对象无效")
        selection = cls(
            target=normalized_target,
            configuration=bool(raw.get("configuration", False)),
            data=bool(raw.get("data", False)),
            mp_settings=bool(raw.get("mp_settings", False)),
            plugin_settings=bool(raw.get("plugin_settings", False)),
            plugin_data=bool(raw.get("plugin_data", False)),
            plugin_files=bool(raw.get("plugin_files", False)),
            app_env=bool(raw.get("app_env", False)),
            cookies=bool(raw.get("cookies", False)),
            database=bool(raw.get("database", False)),
        )
        if selection.database:
            raise ScopeError("完整数据库备份由 MoviePilot 主程序管理")
        if normalized_target == "plugin" and not (
            selection.configuration or selection.data
        ):
            raise ScopeError("至少选择配置或数据中的一项")
        if normalized_target == "moviepilot" and not any(
            (
                selection.mp_settings,
                selection.plugin_settings,
                selection.plugin_data,
                selection.plugin_files,
                selection.app_env,
                selection.cookies,
            )
        ):
            raise ScopeError("至少选择一项备份内容")
        return selection

    def to_backup_scope(self) -> BackupScope:
        """将显式手动选择映射为底层备份范围。"""
        if self.target == "moviepilot":
            return BackupScope(
                mp_settings=self.mp_settings,
                plugin_settings=self.plugin_settings,
                plugin_data=self.plugin_data,
                plugin_files=self.plugin_files,
                app_env=self.app_env,
                cookies=self.cookies,
                database=False,
            )
        return BackupScope(
            mp_settings=False,
            plugin_settings=self.configuration,
            plugin_data=self.data,
            plugin_files=self.data,
            app_env=False,
            cookies=False,
            database=False,
        )


@dataclass(frozen=True)
class RestoreSelection:
    """描述允许在运行中执行的选择性恢复范围。"""

    mp_settings: bool = False
    plugin_settings: bool = False
    plugin_data: bool = False
    plugin_files: bool = False

    @classmethod
    def from_payload(cls, payload: Dict[str, Any] | None) -> "RestoreSelection":
        """从 API 请求体构造选择性恢复范围。"""
        raw = payload or {}
        selection = cls(
            mp_settings=bool(raw.get("mp_settings", False)),
            plugin_settings=bool(raw.get("plugin_settings", False)),
            plugin_data=bool(raw.get("plugin_data", False)),
            plugin_files=bool(raw.get("plugin_files", False)),
        )
        if not any(asdict(selection).values()):
            raise ScopeError("至少选择一项可在线恢复的数据")
        return selection

    def to_dict(self) -> Dict[str, bool]:
        """返回可安全写入恢复日志的范围字典。"""
        return asdict(self)


def normalize_plugin_ids(values: Iterable[Any] | None) -> List[str]:
    """返回去重且符合 MoviePilot 类名格式的插件 ID 列表。"""
    if isinstance(values, (str, bytes)):
        values = [values]
    result: List[str] = []
    for value in values or []:
        plugin_id = str(value or "").strip()
        if not plugin_id:
            continue
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,127}", plugin_id):
            raise ScopeError(f"插件 ID 无效：{plugin_id}")
        if plugin_id not in result:
            result.append(plugin_id)
    return result
