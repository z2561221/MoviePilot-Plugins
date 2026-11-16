"""备份目录、公开摘要、索引与自动保留管理。"""

import shutil
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from ..model.backup import BackupServiceError, ScopeError
from .manifest_service import ManifestError, ManifestService


class BackupCatalog:
    """管理已完成的包；保留查询无需遍历包内文件计算体积。"""

    def __init__(self, plugin: Any, normalize_manifest: Callable) -> None:
        self.plugin = plugin
        self.normalize_manifest = normalize_manifest

    def root(self) -> Path:
        root = self.plugin.get_data_path() / "backups"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def path(self, backup_id: Any) -> Path:
        value = ManifestService.validate_backup_id(backup_id)
        path = self.root() / value
        if not path.is_dir():
            raise BackupServiceError("备份不存在")
        return path

    def read_manifest(self, backup_id: Any) -> dict[str, Any]:
        return self.normalize_manifest(
            ManifestService.read_json(self.path(backup_id) / "manifest.public.json")
        )

    def list_backups(self, *, include_size: bool = True) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for child in self.root().iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            manifest_path = child / "manifest.public.json"
            if not manifest_path.is_file():
                continue
            try:
                manifest = self.normalize_manifest(ManifestService.read_json(manifest_path))
                if include_size:
                    manifest["package_size"] = sum(
                        item.stat().st_size for item in child.rglob("*") if item.is_file()
                    )
                records.append(manifest)
            except (ManifestError, ScopeError, TypeError, ValueError, OSError):
                continue
        return sorted(records, key=lambda item: str(item.get("created_at", "")), reverse=True)

    def append_index(self, manifest: dict[str, Any]) -> None:
        existing = self.plugin.get_data("backup_index") or []
        records = [
            item for item in existing
            if isinstance(item, dict) and item.get("backup_id") != manifest.get("backup_id")
        ]
        records.insert(0, manifest)
        self.plugin.save_data("backup_index", records[:200])

    def _remove_index(self, backup_ids: Iterable[str]) -> None:
        removed = set(backup_ids)
        existing = self.plugin.get_data("backup_index") or []
        self.plugin.save_data(
            "backup_index",
            [item for item in existing if isinstance(item, dict) and item.get("backup_id") not in removed],
        )

    def prune_automatic(
        self, retention_count: int, preserve_backup_ids: Iterable[Any] | None = None
    ) -> list[str]:
        limit = max(1, min(200, int(retention_count)))
        preserved = {str(value) for value in preserve_backup_ids or []}
        automatic = [item for item in self.list_backups(include_size=False) if item.get("backup_kind") == "automatic"]
        deleted: list[str] = []
        for item in automatic[limit:]:
            backup_id = str(item.get("backup_id") or "")
            if not backup_id or backup_id in preserved:
                continue
            shutil.rmtree(self.path(backup_id))
            deleted.append(backup_id)
        if deleted:
            self._remove_index(deleted)
        return deleted

    def delete(self, backup_id: Any) -> dict[str, Any]:
        normalized = ManifestService.validate_backup_id(backup_id)
        shutil.rmtree(self.path(normalized))
        self._remove_index([normalized])
        return {"backup_id": normalized, "deleted": True}
