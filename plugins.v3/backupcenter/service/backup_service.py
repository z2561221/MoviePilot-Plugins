"""创建 MoviePilot 逻辑备份包。"""

import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

from app.schemas.types import SystemConfigKey
from app.sdk.config import settings
from version import APP_VERSION

from ..model.backup import BackupScope, ScopeError, normalize_plugin_ids
from .crypto_service import CryptoService
from .manifest_service import ManifestError, ManifestService
from .offline_guide_service import OfflineGuideService


class BackupServiceError(RuntimeError):
    """表示备份创建或包校验失败。"""


class BackupService:
    """从宿主配置、插件数据和标准目录构造可选加密备份包。"""

    _format_version = 3
    _backup_kind_labels = {
        "manual": "手动备份",
        "automatic": "自动备份",
        "emergency": "恢复前应急备份",
    }

    def __init__(self, plugin: Any, settings_obj: Any = None) -> None:
        """绑定运行中的插件与可注入的宿主配置。"""
        self.plugin = plugin
        self.settings = settings_obj or settings

    def get_backup_root(self) -> Path:
        """返回备份中心自有数据目录中的备份根目录。"""
        root = self.plugin.get_data_path() / "backups"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def get_backup_path(self, backup_id: Any) -> Path:
        """返回经过安全校验的备份目录。"""
        value = ManifestService.validate_backup_id(backup_id)
        path = self.get_backup_root() / value
        if not path.is_dir():
            raise BackupServiceError("备份不存在")
        return path

    def _installed_plugin_ids(self, config: Dict[str, Any]) -> List[str]:
        """从宿主配置读取可备份插件 ID，并排除备份中心自身。"""
        raw = config.get(SystemConfigKey.UserInstalledPlugins.value, [])
        if not isinstance(raw, list):
            return []
        own_plugin_id = self.plugin.__class__.__name__
        return [plugin_id for plugin_id in normalize_plugin_ids(raw) if plugin_id != own_plugin_id]

    def available_plugin_ids(self) -> List[str]:
        """返回当前允许纳入逻辑备份的已安装插件 ID。"""
        return self._installed_plugin_ids(self.plugin.systemconfig.all())

    @staticmethod
    def _select_plugin_ids(
        installed_ids: Iterable[str], requested_ids: Iterable[Any] | None
    ) -> List[str]:
        """选择需要包含的已安装插件，并拒绝未知插件。"""
        installed = list(installed_ids)
        if requested_ids is None:
            return installed
        requested = normalize_plugin_ids(requested_ids)
        unknown = sorted(set(requested).difference(installed))
        if unknown:
            raise BackupServiceError(f"请求了未安装的插件：{', '.join(unknown)}")
        return requested

    @staticmethod
    def _write_payload_json(path: Path, value: Any) -> None:
        """写入备份负载内的结构化 JSON 数据。"""
        ManifestService.write_json(path, value)

    @staticmethod
    def _copy_tree(source: Path, destination: Path) -> int:
        """复制普通文件目录并拒绝符号链接，返回复制文件数量。"""
        if not source.exists():
            return 0
        if source.is_symlink():
            raise BackupServiceError("不允许备份符号链接目录")
        count = 0
        for item in source.rglob("*"):
            if item.is_symlink():
                raise BackupServiceError(f"不允许备份符号链接：{item.name}")
            relative = item.relative_to(source)
            target = destination / relative
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif item.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
                count += 1
        return count

    @staticmethod
    def _zip_payload(payload_root: Path, destination: Path) -> None:
        """将已准备的负载目录压缩为临时 ZIP，不暴露到最终备份包。"""
        with zipfile.ZipFile(
            destination,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for source in sorted(payload_root.rglob("*")):
                if source.is_file():
                    archive.write(source, source.relative_to(payload_root.parent).as_posix())

    def _append_index(self, public_manifest: Dict[str, Any]) -> None:
        """将不含秘密的备份摘要保存到备份中心自身数据中。"""
        existing = self.plugin.get_data("backup_index") or []
        records = [item for item in existing if isinstance(item, dict)]
        records = [
            item
            for item in records
            if item.get("backup_id") != public_manifest.get("backup_id")
        ]
        records.insert(0, public_manifest)
        self.plugin.save_data("backup_index", records[:200])

    @classmethod
    def _normalize_display_name(
        cls,
        value: Any,
        backup_kind: str,
        created_at: datetime,
        scope: BackupScope | None = None,
        selected_plugin_ids: Iterable[str] | None = None,
        plugin_names: Mapping[str, str] | None = None,
        manual_target: str = "plugin",
    ) -> str:
        """清洗可读名称，留空时按备份类型、内容和本地时间生成。"""
        normalized = re.sub(r'[\x00-\x1f<>:"/\\|?*]+', " ", str(value or ""))
        normalized = re.sub(r"\s+", " ", normalized).strip(" .")[:60].strip(" .")
        if normalized:
            return normalized
        local_time = created_at.astimezone().strftime("%Y%m%d-%H%M%S")
        if backup_kind != "manual":
            return f"{cls._backup_kind_labels[backup_kind]}-{local_time}"
        selected_ids = list(selected_plugin_ids or [])
        if manual_target == "moviepilot":
            subject_name = "MoviePilot"
        else:
            plugin_id = selected_ids[0] if selected_ids else "未命名插件"
            subject_name = str((plugin_names or {}).get(plugin_id) or plugin_id).strip()
        has_configuration = bool(
            scope
            and (
                scope.mp_settings
                or scope.plugin_settings
                or scope.app_env
                or scope.cookies
            )
        )
        has_data = bool(scope and (scope.plugin_data or scope.plugin_files))
        if has_configuration and has_data:
            content_label = "配置和数据"
        elif has_configuration:
            content_label = "配置"
        else:
            content_label = "数据"
        return f"{subject_name}-{content_label}-{local_time}"

    @classmethod
    def _normalize_public_manifest(
        cls,
        manifest: Dict[str, Any],
    ) -> Dict[str, Any]:
        """为旧公开清单补齐只影响展示的兼容字段。"""
        normalized = dict(manifest or {})
        backup_kind = str(normalized.get("backup_kind") or "manual")
        if backup_kind not in cls._backup_kind_labels:
            backup_kind = "manual"
        try:
            created_at = datetime.fromisoformat(
                str(normalized.get("created_at") or "")
            )
        except ValueError:
            created_at = datetime.now(timezone.utc)
        try:
            scope = BackupScope.from_payload(normalized.get("scope"))
        except ScopeError:
            scope = None
        selected_plugin_ids = normalize_plugin_ids(
            normalized.get("selected_plugin_ids")
        )
        selected_plugins = normalized.get("selected_plugins") or []
        plugin_names = {
            str(item.get("id")): str(item.get("name") or item.get("id"))
            for item in selected_plugins
            if isinstance(item, dict) and item.get("id")
        }
        manual_target = str(
            normalized.get("manual_target")
            or ("plugin" if selected_plugin_ids else "moviepilot")
        )
        normalized["display_name"] = cls._normalize_display_name(
            normalized.get("display_name"),
            backup_kind,
            created_at,
            scope=scope,
            selected_plugin_ids=selected_plugin_ids,
            plugin_names=plugin_names,
            manual_target=manual_target,
        )
        return normalized

    def create_backup(
        self,
        scope: BackupScope,
        plugin_ids: Iterable[Any] | None = None,
        emergency: bool = False,
        backup_kind: str = "manual",
        password: Any = None,
        display_name: Any = None,
        plugin_names: Mapping[str, str] | None = None,
        manual_target: str = "plugin",
    ) -> Dict[str, Any]:
        """创建明文或加密校验备份包并返回公开 manifest。"""
        if backup_kind not in {"manual", "automatic", "emergency"}:
            raise BackupServiceError("备份类型无效")
        if scope.database:
            raise BackupServiceError("完整数据库备份由 MoviePilot 主程序管理")
        if emergency:
            backup_kind = "emergency"
        config = self.plugin.systemconfig.all()
        installed_ids = self._installed_plugin_ids(config)
        selected_ids = self._select_plugin_ids(installed_ids, plugin_ids)
        normalized_manual_target = str(manual_target or "").strip().lower()
        if normalized_manual_target not in {"moviepilot", "plugin"}:
            raise BackupServiceError("手动备份对象无效")
        if (
            backup_kind == "manual"
            and normalized_manual_target == "plugin"
            and len(selected_ids) != 1
        ):
            raise BackupServiceError("插件备份必须选择一个插件")
        created_at = datetime.now(timezone.utc)
        normalized_display_name = self._normalize_display_name(
            display_name,
            backup_kind,
            created_at,
            scope=scope,
            selected_plugin_ids=selected_ids,
            plugin_names=plugin_names,
            manual_target=normalized_manual_target,
        )
        selected_plugins = [
            {
                "id": plugin_id,
                "name": str((plugin_names or {}).get(plugin_id) or plugin_id),
            }
            for plugin_id in selected_ids
        ]
        backup_id = f"backup-{created_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        backup_root = self.get_backup_root()
        backup_path = backup_root / backup_id
        if backup_path.exists():
            raise BackupServiceError("备份目录已存在")
        backup_path.mkdir(parents=True)
        content_counts: Dict[str, int] = {
            "mp_settings": 0,
            "plugin_settings": 0,
            "plugin_data": 0,
            "plugin_files": 0,
            "cookies": 0,
        }
        try:
            with tempfile.TemporaryDirectory(prefix=".payload-", dir=backup_root) as temporary:
                temporary_root = Path(temporary)
                payload_root = temporary_root / "payload"
                payload_root.mkdir()
                normalized_password = CryptoService.validate_password(password)
                private_manifest: Dict[str, Any] = {
                    "format_version": self._format_version,
                    "backup_id": backup_id,
                    "display_name": normalized_display_name,
                    "created_at": created_at.isoformat(),
                    "source_mp_version": APP_VERSION,
                    "scope": scope.to_dict(),
                    "selected_plugin_ids": selected_ids,
                    "selected_plugins": selected_plugins,
                    "emergency": bool(emergency),
                    "backup_kind": backup_kind,
                    "manual_target": normalized_manual_target if backup_kind == "manual" else None,
                    "encrypted": bool(normalized_password),
                    "encryption": {"enabled": bool(normalized_password)},
                }
                if scope.mp_settings:
                    mp_settings = {
                        key: value
                        for key, value in config.items()
                        if not str(key).startswith("plugin.")
                    }
                    self._write_payload_json(payload_root / "system_config.json", mp_settings)
                    content_counts["mp_settings"] = len(mp_settings)
                if scope.plugin_settings:
                    plugin_settings = {
                        plugin_id: config.get(f"plugin.{plugin_id}")
                        for plugin_id in selected_ids
                        if f"plugin.{plugin_id}" in config
                    }
                    self._write_payload_json(payload_root / "plugin_configs.json", plugin_settings)
                    content_counts["plugin_settings"] = len(plugin_settings)
                if scope.plugin_data:
                    plugin_data: Dict[str, List[Dict[str, Any]]] = {}
                    for plugin_id in selected_ids:
                        rows = self.plugin.plugindata.get_data_all(plugin_id) or []
                        plugin_data[plugin_id] = [
                            {"key": row.key, "value": row.value} for row in rows
                        ]
                        content_counts["plugin_data"] += len(plugin_data[plugin_id])
                    self._write_payload_json(payload_root / "plugin_data.json", plugin_data)
                if scope.app_env:
                    source_app_env = Path(self.settings.CONFIG_PATH) / "app.env"
                    if source_app_env.is_file():
                        destination_app_env = payload_root / "files" / "app.env"
                        destination_app_env.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_app_env, destination_app_env)
                if scope.plugin_files:
                    for plugin_id in selected_ids:
                        source_directory = Path(self.settings.PLUGIN_DATA_PATH) / plugin_id
                        destination_directory = payload_root / "files" / "plugins" / plugin_id
                        content_counts["plugin_files"] += self._copy_tree(
                            source_directory, destination_directory
                        )
                if scope.cookies:
                    content_counts["cookies"] = self._copy_tree(
                        Path(self.settings.COOKIE_PATH), payload_root / "files" / "cookies"
                    )
                private_manifest["content_counts"] = content_counts
                self._write_payload_json(payload_root / "manifest.json", private_manifest)
                guide = OfflineGuideService.build_guide(private_manifest)
                checklist = OfflineGuideService.build_checklist(private_manifest)
                docs_root = payload_root / "docs"
                docs_root.mkdir(parents=True, exist_ok=True)
                (docs_root / "RECOVERY-GUIDE.md").write_text(guide, encoding="utf-8")
                (docs_root / "RECOVERY-CHECKLIST.txt").write_text(
                    checklist, encoding="utf-8"
                )
                temporary_zip = temporary_root / "payload.zip"
                self._zip_payload(payload_root, temporary_zip)
                if normalized_password:
                    encryption = CryptoService.encrypt_file(
                        temporary_zip, backup_path / "payload.enc", normalized_password
                    )
                    payload_name = "payload.enc"
                else:
                    shutil.copy2(temporary_zip, backup_path / "payload.zip")
                    encryption = {"enabled": False, "format": "none"}
                    payload_name = "payload.zip"
            public_manifest = {
                "format_version": self._format_version,
                "backup_id": backup_id,
                "display_name": normalized_display_name,
                "created_at": created_at.isoformat(),
                "source_mp_version": APP_VERSION,
                "scope": scope.to_dict(),
                "selected_plugin_ids": selected_ids,
                "selected_plugins": selected_plugins,
                "content_counts": content_counts,
                "emergency": bool(emergency),
                "backup_kind": backup_kind,
                "manual_target": normalized_manual_target if backup_kind == "manual" else None,
                "encryption": encryption,
                "encrypted": bool(normalized_password),
            }
            ManifestService.write_json(backup_path / "manifest.public.json", public_manifest)
            (backup_path / "RECOVERY-GUIDE.md").write_text(
                guide, encoding="utf-8"
            )
            (backup_path / "RECOVERY-CHECKLIST.txt").write_text(
                checklist, encoding="utf-8"
            )
            copied_tools = OfflineGuideService.copy_tools(backup_path / "tools")
            checksum_paths = [
                Path(payload_name),
                Path("manifest.public.json"),
                Path("RECOVERY-GUIDE.md"),
                Path("RECOVERY-CHECKLIST.txt"),
            ] + [tool.relative_to(backup_path) for tool in copied_tools]
            ManifestService.write_checksums(backup_path, checksum_paths)
            self._append_index(public_manifest)
            return public_manifest
        except Exception:
            shutil.rmtree(backup_path, ignore_errors=True)
            raise

    def list_backups(self) -> List[Dict[str, Any]]:
        """读取本地备份目录中的公开摘要。"""
        backups: List[Dict[str, Any]] = []
        for child in self.get_backup_root().iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            manifest_path = child / "manifest.public.json"
            if not manifest_path.is_file():
                continue
            try:
                manifest = self._normalize_public_manifest(
                    ManifestService.read_json(manifest_path)
                )
                manifest["package_size"] = sum(
                    item.stat().st_size for item in child.rglob("*") if item.is_file()
                )
                backups.append(manifest)
            except (ManifestError, OSError):
                continue
        return sorted(backups, key=lambda item: str(item.get("created_at", "")), reverse=True)

    def prune_automatic_backups(
        self, retention_count: int, preserve_backup_ids: Iterable[Any] | None = None
    ) -> List[str]:
        """按数量删除最旧的自动备份，并保留应急和手动备份。"""
        limit = max(1, min(200, int(retention_count)))
        preserved = {str(value) for value in preserve_backup_ids or []}
        automatic = [
            item for item in self.list_backups()
            if item.get("backup_kind") == "automatic"
        ]
        deleted: List[str] = []
        for item in automatic[limit:]:
            backup_id = str(item.get("backup_id") or "")
            if not backup_id or backup_id in preserved:
                continue
            path = self.get_backup_path(backup_id)
            shutil.rmtree(path)
            deleted.append(backup_id)
        if deleted:
            existing = self.plugin.get_data("backup_index") or []
            self.plugin.save_data(
                "backup_index",
                [
                    item for item in existing
                    if isinstance(item, dict) and item.get("backup_id") not in deleted
                ],
            )
        return deleted

    def delete_backup(self, backup_id: Any) -> Dict[str, Any]:
        """删除指定备份并从本地索引移除。"""
        normalized = ManifestService.validate_backup_id(backup_id)
        path = self.get_backup_path(normalized)
        shutil.rmtree(path)
        existing = self.plugin.get_data("backup_index") or []
        self.plugin.save_data(
            "backup_index",
            [
                item for item in existing
                if isinstance(item, dict) and item.get("backup_id") != normalized
            ],
        )
        return {"backup_id": normalized, "deleted": True}

    def read_public_manifest(self, backup_id: Any) -> Dict[str, Any]:
        """读取指定备份的公开 manifest。"""
        return self._normalize_public_manifest(
            ManifestService.read_json(
                self.get_backup_path(backup_id) / "manifest.public.json"
            )
        )

    def verify_backup(self, backup_id: Any) -> Dict[str, Any]:
        """校验备份外层文件并返回公开摘要。"""
        backup_path = self.get_backup_path(backup_id)
        verified_files = ManifestService.verify_checksums(backup_path)
        manifest = self._normalize_public_manifest(
            ManifestService.read_json(backup_path / "manifest.public.json")
        )
        return {"manifest": manifest, "verified_files": verified_files}

    def create_export_archive(self, backup_id: Any) -> Tuple[Path, str]:
        """将完整备份目录打包为临时 ZIP，并返回路径和下载文件名。"""
        backup_path = self.get_backup_path(backup_id)
        ManifestService.verify_checksums(backup_path)
        temporary = tempfile.NamedTemporaryFile(
            prefix=".backupcenter-export-",
            suffix=".zip",
            dir=self.get_backup_root(),
            delete=False,
        )
        temporary_path = Path(temporary.name)
        temporary.close()
        manifest = ManifestService.read_json(backup_path / "manifest.public.json")
        try:
            created_at = datetime.fromisoformat(str(manifest.get("created_at") or ""))
        except ValueError:
            created_at = datetime.now(timezone.utc)
        backup_kind = str(manifest.get("backup_kind") or "manual")
        if backup_kind not in self._backup_kind_labels:
            backup_kind = "manual"
        display_name = self._normalize_display_name(
            manifest.get("display_name"), backup_kind, created_at
        )
        archive_root = display_name
        try:
            with zipfile.ZipFile(
                temporary_path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as archive:
                for source in sorted(backup_path.rglob("*")):
                    if source.is_file():
                        relative = source.relative_to(backup_path).as_posix()
                        archive.write(source, f"{archive_root}/{relative}")
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        return temporary_path, f"{display_name}.zip"
