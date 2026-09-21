"""执行受限的在线选择性恢复，并委托宿主管理数据库恢复点。"""

from copy import deepcopy
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, Iterator, List, Tuple

from app.sdk.database import create_backup as create_database_backup
from version import APP_VERSION

from ..model.backup import BackupScope, RestoreSelection, normalize_plugin_ids
from .backup_service import BackupService, BackupServiceError
from .crypto_service import BackupCryptoError, CryptoService
from .manifest_service import ManifestError, ManifestService
from .plugin_data import normalize_plugin_data_rows


class RestoreServiceError(RuntimeError):
    """表示恢复预检、兼容性或写入失败。"""


class RestoreService:
    """将明文或加密负载恢复为受限的在线逻辑数据。"""

    _max_zip_members = 100_000
    _max_zip_uncompressed_bytes = 20 * 1024 * 1024 * 1024

    def __init__(self, plugin: Any, backup_service: BackupService) -> None:
        """绑定插件和创建应急备份所需的备份服务。"""
        self.plugin = plugin
        self.backup_service = backup_service

    @staticmethod
    def _major_version(value: Any) -> str:
        """提取 MoviePilot 版本中的主版本号。"""
        match = re.search(r"(?:^|v)(\d+)", str(value or ""), re.IGNORECASE)
        return match.group(1) if match else ""

    def _verify_compatibility(self, public_manifest: Dict[str, Any]) -> None:
        """阻断跨 MoviePilot 主版本的在线恢复。"""
        source_major = self._major_version(public_manifest.get("source_mp_version"))
        target_major = self._major_version(APP_VERSION)
        if not source_major or not target_major or source_major != target_major:
            raise RestoreServiceError("在线恢复只允许相同 MoviePilot 主版本")

    @staticmethod
    def _safe_zip_path(name: str) -> Path:
        """验证 ZIP 成员路径，拒绝路径穿越和绝对路径。"""
        if "\\" in name or ":" in name:
            raise RestoreServiceError("备份负载包含不安全路径")
        value = PurePosixPath(name)
        if value.is_absolute() or ".." in value.parts or not value.parts:
            raise RestoreServiceError("备份负载包含不安全路径")
        return Path(*value.parts)

    @classmethod
    def _validate_zip_members(cls, members: Iterable[zipfile.ZipInfo]) -> None:
        """限制 ZIP 条目数量和展开总大小，避免恶意负载耗尽资源。"""
        members = list(members)
        if len(members) > cls._max_zip_members:
            raise RestoreServiceError("备份负载条目数量超过限制")
        total_size = 0
        names: set[str] = set()
        for item in members:
            if item.filename in names:
                raise RestoreServiceError("备份负载包含重复路径")
            names.add(item.filename)
            if item.file_size < 0:
                raise RestoreServiceError("备份负载大小无效")
            total_size += item.file_size
            if total_size > cls._max_zip_uncompressed_bytes:
                raise RestoreServiceError("备份负载展开大小超过限制")

    @contextmanager
    def _payload_directory(
        self, backup_id: Any, public_manifest: Dict[str, Any], password: Any = None
    ) -> Iterator[Path]:
        """验证、按需解密并安全解压负载，离开作用域后删除临时文件。"""
        backup_path = self.backup_service.get_backup_path(backup_id)
        ManifestService.verify_checksums(backup_path)
        with tempfile.TemporaryDirectory(
            prefix=".restore-",
            dir=self.backup_service.get_backup_root(),
        ) as temporary:
            temporary_root = Path(temporary)
            payload_zip = temporary_root / "payload.zip"
            try:
                encryption = public_manifest.get("encryption") or {}
                if encryption.get("enabled"):
                    restore_password = str(
                        password or self.plugin.get_stored_backup_password() or ""
                    )
                    if not restore_password:
                        raise RestoreServiceError("加密备份需要口令")
                    CryptoService.decrypt_file(
                        backup_path / "payload.enc", payload_zip, restore_password, encryption
                    )
                else:
                    shutil.copy2(backup_path / "payload.zip", payload_zip)
                with zipfile.ZipFile(payload_zip) as archive:
                    members = archive.infolist()
                    self._validate_zip_members(members)
                    for item in members:
                        relative = self._safe_zip_path(item.filename)
                        if item.is_dir():
                            (temporary_root / relative).mkdir(parents=True, exist_ok=True)
                            continue
                        target = temporary_root / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(item) as source, target.open("wb") as destination:
                            shutil.copyfileobj(source, destination)
            except BackupCryptoError as error:
                raise RestoreServiceError(str(error)) from error
            except RestoreServiceError:
                raise
            except (OSError, zipfile.BadZipFile, ManifestError) as error:
                raise RestoreServiceError("无法读取备份负载") from error
            payload_root = temporary_root / "payload"
            if not payload_root.is_dir():
                raise RestoreServiceError("备份负载缺少 payload 目录")
            yield payload_root

    @staticmethod
    def _read_optional_json(path: Path) -> Dict[str, Any]:
        """读取可选 JSON 文件，缺失时返回空对象。"""
        return ManifestService.read_json(path) if path.is_file() else {}

    def preview(self, backup_id: Any) -> Dict[str, Any]:
        """返回不读取负载内容的恢复预检结果。"""
        verification = self.backup_service.verify_backup(backup_id)
        manifest = verification["manifest"]
        source_major = self._major_version(manifest.get("source_mp_version"))
        target_major = self._major_version(APP_VERSION)
        return {
            "manifest": manifest,
            "verified_files": verification["verified_files"],
            "online_restore_allowed": source_major == target_major and bool(source_major),
            "database_restore_mode": (
                "legacy_offline"
                if (manifest.get("database") or {}).get("included")
                else "host_managed"
            ),
            "encrypted": bool((manifest.get("encryption") or {}).get("enabled")),
        }

    @staticmethod
    def _resolve_selected_plugin_ids(
        available_ids: Iterable[str], requested_ids: Iterable[Any] | None
    ) -> List[str]:
        """从备份中选择恢复目标插件，并拒绝不存在的 ID。"""
        available = normalize_plugin_ids(available_ids)
        if requested_ids is None:
            return available
        requested = normalize_plugin_ids(requested_ids)
        unknown = sorted(set(requested).difference(available))
        if unknown:
            raise RestoreServiceError(f"备份中不存在插件：{', '.join(unknown)}")
        return requested

    @staticmethod
    def _verify_private_manifest(
        public_manifest: Dict[str, Any], private_manifest: Dict[str, Any]
    ) -> None:
        """核对公开摘要与明文负载中的恢复边界字段。"""
        comparable_fields = [
            "format_version",
            "backup_id",
            "source_mp_version",
            "scope",
            "selected_plugin_ids",
            "selected_plugins",
            "content_counts",
            "emergency",
            "backup_kind",
            "manual_target",
            "encrypted",
        ]
        if int(private_manifest.get("format_version") or 0) < 3:
            comparable_fields.append("database")
        for field in comparable_fields:
            if private_manifest.get(field) != public_manifest.get(field):
                raise RestoreServiceError("备份公开摘要与负载不匹配")

    def _restore_system_settings(self, payload_root: Path) -> int:
        """恢复非插件系统配置，不在线替换 app.env 或插件安装清单。"""
        settings_data = self._read_optional_json(payload_root / "system_config.json")
        restored = 0
        excluded = {"UserInstalledPlugins"}
        for key, value in settings_data.items():
            if str(key).startswith("plugin.") or str(key) in excluded:
                continue
            self.plugin.systemconfig.set(str(key), value)
            restored += 1
        return restored

    def _system_settings_snapshot(self, payload_root: Path) -> Dict[str, Tuple[bool, Any]]:
        """记录恢复涉及的系统配置原值，供失败时精确回滚。"""
        settings_data = self._read_optional_json(payload_root / "system_config.json")
        all_settings = getattr(self.plugin.systemconfig, "all", None)
        current = all_settings() if callable(all_settings) else {}
        excluded = {"UserInstalledPlugins"}
        return {
            str(key): (str(key) in current, deepcopy(current.get(key)))
            for key in settings_data
            if not str(key).startswith("plugin.") and str(key) not in excluded
        }

    def _rollback_system_settings(
        self, snapshot: Dict[str, Tuple[bool, Any]]
    ) -> None:
        """恢复系统配置快照，缺失项优先走宿主删除接口。"""
        for key, (present, value) in snapshot.items():
            if present:
                self.plugin.systemconfig.set(key, value)
                continue
            deleter = getattr(self.plugin.systemconfig, "delete", None)
            if callable(deleter):
                deleter(key)

    def _read_plugin_config(self, plugin_id: str) -> Any:
        """通过稳定插件配置入口读取指定实例配置。"""
        getter = getattr(self.plugin, "get_config", None)
        if callable(getter):
            try:
                return getter(plugin_id=plugin_id)
            except TypeError:
                return getter(plugin_id)
        all_settings = getattr(self.plugin.systemconfig, "all", None)
        config = all_settings() if callable(all_settings) else {}
        return config.get(f"plugin.{plugin_id}")

    def _write_plugin_config(self, plugin_id: str, value: Any) -> None:
        """通过稳定插件配置入口写入指定实例配置。"""
        updater = getattr(self.plugin, "update_config", None)
        if callable(updater):
            try:
                result = updater(value, plugin_id=plugin_id)
            except TypeError:
                result = updater(value, plugin_id)
            if result is False:
                raise RestoreServiceError(f"插件配置写入失败：{plugin_id}")
            return
        setter = getattr(self.plugin.systemconfig, "set", None)
        if not callable(setter):
            raise RestoreServiceError(f"插件配置写入入口不可用：{plugin_id}")
        setter(f"plugin.{plugin_id}", value)

    def _delete_plugin_config(self, plugin_id: str) -> None:
        """删除恢复前不存在的插件配置，优先使用宿主实例管理器。"""
        deleter = None
        try:
            from app.sdk.plugin.manager import PluginManager

            deleter = getattr(PluginManager(), "delete_plugin_config", None)
        except (AttributeError, ImportError, TypeError):
            pass
        if callable(deleter):
            result = deleter(plugin_id, force=True)
            if result is False:
                raise RestoreServiceError(f"插件配置删除失败：{plugin_id}")
            return
        deleter = getattr(self.plugin.systemconfig, "delete", None)
        if not callable(deleter):
            raise RestoreServiceError(f"插件配置删除入口不可用：{plugin_id}")
        deleter(f"plugin.{plugin_id}")

    def _restore_plugin_settings(self, payload_root: Path, plugin_ids: Iterable[str]) -> int:
        """恢复指定插件的持久化配置键。"""
        configs = self._read_optional_json(payload_root / "plugin_configs.json")
        restored = 0
        for plugin_id in plugin_ids:
            if plugin_id not in configs:
                continue
            self._write_plugin_config(plugin_id, configs[plugin_id])
            restored += 1
        return restored

    def _plugin_config_snapshot(
        self, payload_root: Path, plugin_ids: Iterable[str]
    ) -> Dict[str, Tuple[bool, Any]]:
        """记录备份中目标插件配置的原值和存在性。"""
        configs = self._read_optional_json(payload_root / "plugin_configs.json")
        snapshot: Dict[str, Tuple[bool, Any]] = {}
        for plugin_id in plugin_ids:
            if plugin_id not in configs:
                continue
            current = self._read_plugin_config(plugin_id)
            snapshot[plugin_id] = (current is not None, deepcopy(current))
        return snapshot

    def _rollback_plugin_configs(
        self, snapshot: Dict[str, Tuple[bool, Any]]
    ) -> None:
        """恢复插件配置快照，包含恢复前不存在的键。"""
        for plugin_id, (present, value) in snapshot.items():
            if present:
                self._write_plugin_config(plugin_id, value)
            else:
                self._delete_plugin_config(plugin_id)

    def _validated_plugin_data_rows(
        self, payload_root: Path, plugin_ids: Iterable[str]
    ) -> Tuple[List[str], List[Tuple[str, str, Any]]]:
        """在修改宿主数据前验证并展开全部 PluginData 行。"""
        data = self._read_optional_json(payload_root / "plugin_data.json")
        included_ids: List[str] = []
        validated: List[Tuple[str, str, Any]] = []
        for plugin_id in plugin_ids:
            if plugin_id not in data:
                continue
            rows = data.get(plugin_id)
            if not isinstance(rows, list):
                raise RestoreServiceError(f"插件数据格式无效：{plugin_id}")
            included_ids.append(plugin_id)
            for row in rows:
                if not isinstance(row, dict) or not str(row.get("key") or "").strip():
                    raise RestoreServiceError(f"插件数据项无效：{plugin_id}")
                validated.append((plugin_id, str(row["key"]), row.get("value")))
        return included_ids, validated

    def _read_plugin_data_rows(self, plugin_id: str) -> List[Tuple[str, Any]]:
        """通过宿主公开插件接口读取一个插件的全部数据。"""
        try:
            return normalize_plugin_data_rows(
                self.plugin.get_data(plugin_id=plugin_id), plugin_id
            )
        except ValueError as error:
            raise RestoreServiceError(str(error)) from error

    def _clear_plugin_data(self, plugin_ids: Iterable[str]) -> None:
        """通过宿主公开插件接口删除目标插件的全部数据键。"""
        for plugin_id in plugin_ids:
            for key, _ in self._read_plugin_data_rows(plugin_id):
                self.plugin.del_data(key, plugin_id=plugin_id)

    def _write_plugin_data(self, rows: Iterable[Tuple[str, str, Any]]) -> None:
        """通过宿主公开插件接口逐项写入已经验证的数据。"""
        for plugin_id, key, value in rows:
            self.plugin.save_data(key, value, plugin_id=plugin_id)

    def _restore_plugin_data(self, payload_root: Path, plugin_ids: Iterable[str]) -> int:
        """替换目标插件数据，失败时使用写入前快照补偿回滚。"""
        included_ids, rows = self._validated_plugin_data_rows(payload_root, plugin_ids)
        snapshots = {
            plugin_id: self._read_plugin_data_rows(plugin_id)
            for plugin_id in included_ids
        }
        try:
            self._clear_plugin_data(included_ids)
            self._write_plugin_data(rows)
        # 任意宿主写入异常都必须进入补偿回滚。
        except Exception as error:  # pylint: disable=broad-exception-caught
            try:
                self._clear_plugin_data(included_ids)
                rollback_rows = (
                    (plugin_id, key, value)
                    for plugin_id in included_ids
                    for key, value in snapshots[plugin_id]
                )
                self._write_plugin_data(rollback_rows)
            except Exception as rollback_error:
                raise RestoreServiceError(
                    "插件数据恢复失败且自动回滚失败，请使用应急备份回退"
                ) from rollback_error
            raise RestoreServiceError("插件数据恢复失败，已自动回滚") from error
        return len(rows)

    def _plugin_data_snapshot(
        self, plugin_ids: Iterable[str]
    ) -> Dict[str, List[Tuple[str, Any]]]:
        """记录目标插件的 PluginData 快照，供跨范围失败回滚。"""
        if not callable(getattr(self.plugin, "get_data", None)):
            # 旧宿主测试桩或仅提供数据库恢复点的适配器没有公开数据入口；
            # 生产 V3 基类始终具备该方法。
            return {}
        return {
            plugin_id: self._read_plugin_data_rows(plugin_id)
            for plugin_id in plugin_ids
        }

    def _rollback_plugin_data_snapshot(
        self, snapshot: Dict[str, List[Tuple[str, Any]]]
    ) -> None:
        """恢复全部目标插件的 PluginData 快照。"""
        plugin_ids = list(snapshot)
        self._clear_plugin_data(plugin_ids)
        self._write_plugin_data(
            (plugin_id, key, value)
            for plugin_id, rows in snapshot.items()
            for key, value in rows
        )

    def _restore_plugin_files(self, payload_root: Path, plugin_ids: Iterable[str]) -> List[str]:
        """将插件标准数据目录复制到同卷临时目录后原子替换。"""
        restored: List[str] = []
        files_root = payload_root / "files" / "plugins"
        for plugin_id in plugin_ids:
            source = files_root / plugin_id
            if not source.is_dir():
                continue
            target_getter = getattr(self.plugin, "get_data_path", None)
            if callable(target_getter):
                try:
                    target = Path(target_getter(plugin_id=plugin_id))
                except TypeError:
                    target = Path(target_getter(plugin_id))
            else:
                target = Path(self.backup_service.settings.PLUGIN_DATA_PATH) / plugin_id
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(
                tempfile.mkdtemp(prefix=f".backupcenter-{plugin_id}-", dir=target.parent)
            )
            new_directory = temporary / plugin_id
            rollback_path = target.parent / f".{plugin_id}.pre-restore-{uuid.uuid4().hex[:8]}"
            try:
                shutil.copytree(source, new_directory)
                if target.exists():
                    os_replace = __import__("os").replace
                    os_replace(target, rollback_path)
                    try:
                        os_replace(new_directory, target)
                    except Exception:
                        os_replace(rollback_path, target)
                        raise
                    shutil.rmtree(rollback_path, ignore_errors=True)
                else:
                    __import__("os").replace(new_directory, target)
                restored.append(plugin_id)
            finally:
                shutil.rmtree(temporary, ignore_errors=True)
        return restored

    def _snapshot_plugin_files(
        self, plugin_ids: Iterable[str], snapshot_root: Path
    ) -> Dict[str, Path | None]:
        """在同卷临时目录保存目标插件目录，供跨范围失败回滚。"""
        snapshot_root.mkdir(parents=True, exist_ok=True)
        snapshots: Dict[str, Path | None] = {}
        for plugin_id in plugin_ids:
            target_getter = getattr(self.plugin, "get_data_path", None)
            if callable(target_getter):
                try:
                    target = Path(target_getter(plugin_id=plugin_id))
                except TypeError:
                    target = Path(target_getter(plugin_id))
            else:
                target = Path(self.backup_service.settings.PLUGIN_DATA_PATH) / plugin_id
            if target.is_symlink():
                raise RestoreServiceError(f"不允许恢复符号链接目录：{plugin_id}")
            if not target.is_dir():
                snapshots[plugin_id] = None
                continue
            snapshot = snapshot_root / plugin_id
            shutil.copytree(target, snapshot, symlinks=True)
            snapshots[plugin_id] = snapshot
        return snapshots

    def _rollback_plugin_files(
        self, snapshots: Dict[str, Path | None]
    ) -> None:
        """恢复插件目录快照并清理本次恢复生成的目录。"""
        for plugin_id, snapshot in snapshots.items():
            target_getter = getattr(self.plugin, "get_data_path", None)
            if callable(target_getter):
                try:
                    target = Path(target_getter(plugin_id=plugin_id))
                except TypeError:
                    target = Path(target_getter(plugin_id))
            else:
                target = Path(self.backup_service.settings.PLUGIN_DATA_PATH) / plugin_id
            if target.is_symlink() or target.is_file():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)
            if snapshot is not None and snapshot.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(snapshot, target)

    @staticmethod
    def _stop_target_plugins(plugin_ids: Iterable[str]) -> Tuple[Any, List[str]]:
        """停止当前运行中的目标插件，并返回管理器与实际停止列表。"""
        from app.sdk.plugin.manager import PluginManager

        manager = PluginManager()
        stopped: List[str] = []
        for plugin_id in plugin_ids:
            if plugin_id not in manager.running_plugins:
                continue
            try:
                manager.stop(plugin_id)
            except Exception as error:
                _, reload_failed = RestoreService._reload_target_plugins(manager, stopped)
                suffix = f"；且插件重载失败：{'、'.join(reload_failed)}" if reload_failed else ""
                raise RestoreServiceError(f"无法停止目标插件：{plugin_id}{suffix}") from error
            if plugin_id in manager.running_plugins:
                _, reload_failed = RestoreService._reload_target_plugins(manager, stopped)
                suffix = f"；且插件重载失败：{'、'.join(reload_failed)}" if reload_failed else ""
                raise RestoreServiceError(f"无法停止目标插件：{plugin_id}{suffix}")
            stopped.append(plugin_id)
        return manager, stopped

    @staticmethod
    def _reload_target_plugins(
        manager: Any, plugin_ids: Iterable[str]
    ) -> Tuple[List[str], List[str]]:
        """重新加载恢复前处于运行态的插件，并分别返回成功与失败列表。"""
        reloaded: List[str] = []
        failed: List[str] = []
        for plugin_id in plugin_ids:
            try:
                manager.reload_plugin(plugin_id)
            except Exception:
                failed.append(plugin_id)
                continue
            if plugin_id in manager.running_plugins:
                reloaded.append(plugin_id)
            else:
                failed.append(plugin_id)
        return reloaded, failed

    def _rollback_restore_state(
        self,
        *,
        system_snapshot: Dict[str, Tuple[bool, Any]],
        config_snapshot: Dict[str, Tuple[bool, Any]],
        data_snapshot: Dict[str, List[Tuple[str, Any]]],
        file_snapshots: Dict[str, Path | None],
    ) -> List[str]:
        """按范围恢复写入前快照，并返回无法回滚的范围。"""
        failures: List[str] = []
        for label, callback, value in (
            ("插件目录", self._rollback_plugin_files, file_snapshots),
            ("PluginData", self._rollback_plugin_data_snapshot, data_snapshot),
            ("插件配置", self._rollback_plugin_configs, config_snapshot),
            ("系统配置", self._rollback_system_settings, system_snapshot),
        ):
            if not value:
                continue
            try:
                callback(value)
            except Exception:
                failures.append(label)
        return failures

    @staticmethod
    def _create_host_database_backup() -> str:
        """请求宿主创建数据库恢复点，只返回不含路径的制品名。"""
        try:
            artifact = create_database_backup()
        except Exception as error:
            raise RestoreServiceError("创建宿主管理的数据库恢复点失败") from error
        name = getattr(artifact, "name", None)
        if not name:
            raise RestoreServiceError("宿主数据库恢复点缺少制品名")
        return str(name)

    def restore_logical(
        self,
        backup_id: Any,
        selection: RestoreSelection,
        plugin_ids: Iterable[Any] | None,
        password: Any = None,
    ) -> Dict[str, Any]:
        """执行在线逻辑恢复，并在写入前创建宿主与插件应急备份。"""
        normalized_backup_id = ManifestService.validate_backup_id(backup_id)
        public_manifest = self.backup_service.read_public_manifest(normalized_backup_id)
        self._verify_compatibility(public_manifest)
        scope = public_manifest.get("scope") or {}
        requested_scope = selection.to_dict()
        unavailable = [
            key for key, enabled in requested_scope.items()
            if enabled and not bool(scope.get(key))
        ]
        if unavailable:
            raise RestoreServiceError("所选内容不在这份备份中")
        selected_plugin_ids = self._resolve_selected_plugin_ids(
            public_manifest.get("selected_plugin_ids") or [], plugin_ids
        )
        own_plugin_id = self.plugin.__class__.__name__
        if own_plugin_id in selected_plugin_ids:
            raise RestoreServiceError("不允许在线恢复备份中心自身的插件数据")
        if (
            selection.plugin_settings
            or selection.plugin_data
            or selection.plugin_files
        ) and not selected_plugin_ids:
            raise RestoreServiceError("至少选择一个需要恢复的插件")
        emergency_scope = BackupScope(
            mp_settings=selection.mp_settings,
            plugin_settings=selection.plugin_settings,
            plugin_data=selection.plugin_data,
            plugin_files=selection.plugin_files,
            app_env=False,
            cookies=False,
        )
        result: Dict[str, Any] = {}
        manager = None
        stopped_plugins: List[str] = []
        system_snapshot: Dict[str, Tuple[bool, Any]] = {}
        config_snapshot: Dict[str, Tuple[bool, Any]] = {}
        data_snapshot: Dict[str, List[Tuple[str, Any]]] = {}
        file_snapshots: Dict[str, Path | None] = {}
        rollback_root: Path | None = None
        try:
            with self._payload_directory(
                normalized_backup_id, public_manifest, password=password
            ) as payload_root:
                private_manifest = ManifestService.read_json(payload_root / "manifest.json")
                self._verify_private_manifest(public_manifest, private_manifest)
                if selection.mp_settings:
                    system_snapshot = self._system_settings_snapshot(payload_root)
                if selection.plugin_settings:
                    config_snapshot = self._plugin_config_snapshot(
                        payload_root, selected_plugin_ids
                    )
                if selection.plugin_data:
                    data_snapshot = self._plugin_data_snapshot(selected_plugin_ids)
                if selection.plugin_files:
                    rollback_root = Path(
                        tempfile.mkdtemp(
                            prefix=".restore-rollback-",
                            dir=self.backup_service.get_backup_root(),
                        )
                    )
                    file_snapshots = self._snapshot_plugin_files(
                        selected_plugin_ids, rollback_root
                    )
                host_database_backup_name = self._create_host_database_backup()
                try:
                    emergency = self.backup_service.create_backup(
                        emergency_scope,
                        selected_plugin_ids,
                        emergency=True,
                        backup_kind="emergency",
                        password=self.plugin.get_backup_password(),
                    )
                except BackupServiceError as error:
                    raise RestoreServiceError(
                        "创建恢复前应急备份失败"
                    ) from error
                except Exception as error:
                    raise RestoreServiceError("创建恢复前应急备份失败") from error
                result = {
                    "emergency_backup_id": emergency["backup_id"],
                    "selection": selection.to_dict(),
                    "restored": {
                        "mp_settings": 0,
                        "plugin_settings": 0,
                        "plugin_data": 0,
                        "plugin_files": [],
                    },
                    "reload_required": [],
                    "reloaded": [],
                    "host_database_backup_name": host_database_backup_name,
                }
                plugin_selection = (
                    selected_plugin_ids
                    if selection.plugin_settings or selection.plugin_data or selection.plugin_files
                    else []
                )
                manager, stopped_plugins = self._stop_target_plugins(plugin_selection)
                if selection.mp_settings:
                    result["restored"]["mp_settings"] = self._restore_system_settings(payload_root)
                if selection.plugin_settings:
                    result["restored"]["plugin_settings"] = self._restore_plugin_settings(
                        payload_root, selected_plugin_ids
                    )
                if selection.plugin_data:
                    result["restored"]["plugin_data"] = self._restore_plugin_data(
                        payload_root, selected_plugin_ids
                    )
                if selection.plugin_files:
                    result["restored"]["plugin_files"] = self._restore_plugin_files(
                        payload_root, selected_plugin_ids
                    )
        except RestoreServiceError as error:
            rollback_failed = self._rollback_restore_state(
                system_snapshot=system_snapshot,
                config_snapshot=config_snapshot,
                data_snapshot=data_snapshot,
                file_snapshots=file_snapshots,
            )
            if rollback_root is not None:
                shutil.rmtree(rollback_root, ignore_errors=True)
            if manager is not None and stopped_plugins:
                _, reload_failed = self._reload_target_plugins(manager, stopped_plugins)
            else:
                reload_failed = []
            failures = [*rollback_failed, *reload_failed]
            if failures:
                failed = "、".join(failures)
                raise RestoreServiceError(f"{error}；且恢复回滚失败：{failed}") from error
            raise
        except Exception as error:
            rollback_failed = self._rollback_restore_state(
                system_snapshot=system_snapshot,
                config_snapshot=config_snapshot,
                data_snapshot=data_snapshot,
                file_snapshots=file_snapshots,
            )
            if rollback_root is not None:
                shutil.rmtree(rollback_root, ignore_errors=True)
            if manager is not None and stopped_plugins:
                _, reload_failed = self._reload_target_plugins(manager, stopped_plugins)
            else:
                reload_failed = []
            failures = [*rollback_failed, *reload_failed]
            if failures:
                failed = "、".join(failures)
                raise RestoreServiceError(
                    f"选择性恢复失败，且恢复回滚失败：{failed}；请使用应急备份回退"
                ) from error
            raise RestoreServiceError("选择性恢复失败，请使用应急备份回退") from error
        finally:
            if rollback_root is not None and rollback_root.exists():
                shutil.rmtree(rollback_root, ignore_errors=True)
        if manager is not None and stopped_plugins:
            reloaded, reload_failed = self._reload_target_plugins(manager, stopped_plugins)
            result["reloaded"] = sorted(reloaded)
            result["reload_required"] = sorted(reload_failed)
        return result
