"""备份中心 Bearer API 路由与稳定响应契约。"""

from pathlib import Path
from typing import Any, Callable, Dict, List, TypeVar

from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.core.config import settings
from app.core.plugin import PluginManager
from app.core.security import verify_token
from ..model.api import (
    AutomaticBackupData,
    BackupConfigData,
    BackupDeleteData,
    BackupManifestData,
    BackupOverviewData,
    BackupVerificationData,
    CreateBackupRequest,
    EncryptionSecretRequest,
    EncryptionStatusData,
    RecoveryGuideData,
    RestoreLogicalData,
    RestoreLogicalRequest,
    RestorePreviewData,
)
from ..model.backup import ManualBackupSelection, RestoreSelection, ScopeError, normalize_plugin_ids
from ..service.backup_service import BackupServiceError
from ..service.crypto_service import BackupCryptoError
from ..service.manifest_service import ManifestError
from ..service.restore_service import RestoreServiceError
from ..service.secret_service import SecretServiceError


ResultT = TypeVar("ResultT")


class BackupCenterApiError(Exception):
    """表示可以映射为稳定 HTTP 错误的 API 异常。"""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        """保存状态码、机器码和用户可读消息。"""
        self.status_code = int(status_code)
        self.code = str(code)
        self.message = str(message)
        super().__init__(self.message)

class BackupCenterApiController:
    """协调备份服务、恢复服务和 Bearer 权限边界。"""

    def __init__(self, plugin: Any) -> None:
        """绑定已初始化的备份中心插件实例。"""
        self.plugin = plugin

    @staticmethod
    def _require_superuser(token_payload: Any) -> None:
        """要求登录用户为超级用户，避免普通用户操作敏感备份。"""
        if bool(getattr(token_payload, "super_user", False)):
            return
        error = BackupCenterApiError(403, "superuser_required", "需要超级用户权限")
        raise HTTPException(status_code=error.status_code, detail=error.message)

    @staticmethod
    def _translate_error(error: Exception) -> BackupCenterApiError:
        """将内部错误映射为不泄露敏感路径和凭据的稳定错误。"""
        if isinstance(error, BackupCenterApiError):
            return error
        if isinstance(error, (ScopeError, ManifestError, BackupCryptoError, SecretServiceError)):
            return BackupCenterApiError(422, "invalid_request", str(error))
        if isinstance(error, RestoreServiceError):
            return BackupCenterApiError(409, "restore_blocked", str(error))
        if isinstance(error, BackupServiceError):
            return BackupCenterApiError(409, "backup_failed", str(error))
        return BackupCenterApiError(500, "backupcenter_error", "备份中心操作失败")

    def _run(
        self,
        callback: Callable[..., ResultT],
        *args: Any,
        **kwargs: Any,
    ) -> ResultT:
        """执行业务回调并把已知错误交给 V3 统一错误响应处理。"""
        try:
            return callback(*args, **kwargs)
        except Exception as error:
            mapped = self._translate_error(error)
            raise HTTPException(
                status_code=mapped.status_code,
                detail=mapped.message,
            ) from error

    @staticmethod
    def _plugin_options(plugin_ids: List[str]) -> List[Dict[str, str]]:
        """返回按中文插件名排序、以插件 ID 为值的选择项。"""
        manager = PluginManager()
        options = []
        for plugin_id in plugin_ids:
            plugin_name = manager.get_plugin_attr(plugin_id, "plugin_name")
            if not plugin_name:
                plugin_class = manager.plugins.get(plugin_id)
                plugin_name = getattr(plugin_class, "plugin_name", None)
            options.append(
                {"title": str(plugin_name or plugin_id), "value": plugin_id}
            )
        return sorted(options, key=lambda item: item["title"].casefold())

    @classmethod
    def _plugin_name_map(cls, plugin_ids: List[str]) -> Dict[str, str]:
        """返回插件 ID 到当前中文名称的映射。"""
        return {
            str(item["value"]): str(item["title"])
            for item in cls._plugin_options(plugin_ids)
        }

    def overview(self) -> Dict[str, Any]:
        """返回备份中心概览、加密状态与备份摘要。"""
        backups = self.plugin._backup_service.list_backups()
        installed = self.plugin._backup_service.available_plugin_ids()
        encryption_configured = self.plugin._secret_service.has_password()
        return {
            "enabled": self.plugin.get_state(),
            "backup_root": "插件数据目录/BackupCenter/backups",
            "backup_count": len(backups),
            "backups": backups,
            "database_type": str(settings.DB_TYPE or "sqlite").lower(),
            "encryption_configured": encryption_configured,
            "encryption_active": encryption_configured,
            "installed_plugin_ids": installed,
            "plugin_options": self._plugin_options(installed),
            "online_restore": "仅设置、PluginData 与插件标准数据目录",
            "database_restore": "完整数据库必须停机后按离线教程执行",
        }

    def config(self) -> Dict[str, Any]:
        """返回配置页所需的已保存配置和口令状态。"""
        result = dict(self.plugin._config or {})
        result["encryption_configured"] = self.plugin._secret_service.has_password()
        return result

    def run_automatic_backup(self) -> Dict[str, Any]:
        """按当前周期备份配置立即执行一次自动备份。"""
        with self.plugin._operation_lock:
            return self.plugin.run_automatic_backup()

    def create_backup(self, payload: CreateBackupRequest) -> Dict[str, Any]:
        """创建 MoviePilot 范围或单插件范围的手动备份包。"""
        target = payload.target
        selection = ManualBackupSelection.from_payload(
            payload.selection.model_dump(),
            target,
        )
        scope = selection.to_backup_scope()
        if target == "plugin":
            plugin_ids = normalize_plugin_ids(payload.plugin_ids)
            if len(plugin_ids) != 1:
                raise BackupCenterApiError(
                    422, "single_plugin_required", "插件备份必须选择一个插件"
                )
        else:
            plugin_ids = (
                self.plugin._backup_service.available_plugin_ids()
                if scope.plugin_settings or scope.plugin_data or scope.plugin_files
                else []
            )
        with self.plugin._operation_lock:
            return self.plugin._backup_service.create_backup(
                scope,
                plugin_ids=plugin_ids,
                password=self.plugin.get_backup_password(),
                plugin_names=self._plugin_name_map(plugin_ids),
                manual_target=target,
            )

    def encryption_status(self) -> Dict[str, Any]:
        """返回备份口令是否已经密文保存。"""
        return {"configured": self.plugin._secret_service.has_password()}

    def update_encryption_secret(
        self,
        payload: EncryptionSecretRequest,
    ) -> Dict[str, Any]:
        """设置或清除密文保存的备份口令。"""
        action = payload.action
        if action == "clear":
            self.plugin._secret_service.clear_password()
        elif action == "set":
            self.plugin._secret_service.set_password(payload.password)
        else:
            raise BackupCenterApiError(422, "invalid_secret_action", "口令操作无效")
        return {"configured": self.plugin._secret_service.has_password()}

    def verify_backup(self, backup_id: str) -> Dict[str, Any]:
        """验证备份外层文件的 SHA-256 清单。"""
        return self.plugin._backup_service.verify_backup(backup_id)

    def delete_backup(self, backup_id: str) -> Dict[str, Any]:
        """删除指定备份目录和索引记录。"""
        return self.plugin._backup_service.delete_backup(backup_id)

    def preview_restore(self, backup_id: str) -> Dict[str, Any]:
        """返回无需解密负载的恢复预检信息。"""
        return self.plugin._restore_service.preview(backup_id)

    def restore_logical(self, payload: RestoreLogicalRequest) -> Dict[str, Any]:
        """执行受限的在线选择性恢复。"""
        selection = RestoreSelection.from_payload(payload.selection.model_dump())
        with self.plugin._operation_lock:
            return self.plugin._restore_service.restore_logical(
                backup_id=payload.backup_id,
                selection=selection,
                plugin_ids=payload.plugin_ids,
                password=payload.password,
            )

    def read_guide(self, backup_id: str) -> Dict[str, Any]:
        """读取公开离线恢复教程。"""
        backup_path: Path = self.plugin._backup_service.get_backup_path(backup_id)
        guide = backup_path / "RECOVERY-GUIDE.md"
        checklist = backup_path / "RECOVERY-CHECKLIST.txt"
        if not guide.is_file() or not checklist.is_file():
            raise BackupServiceError("备份缺少离线恢复教程")
        return {
            "guide": guide.read_text(encoding="utf-8"),
            "checklist": checklist.read_text(encoding="utf-8"),
        }

    def export_backup(self, backup_id: str) -> FileResponse:
        """导出包含教程、工具、公开摘要和备份负载的完整 ZIP。"""
        archive_path, download_name = self.plugin._backup_service.create_export_archive(
            backup_id
        )
        return FileResponse(
            path=archive_path,
            filename=download_name,
            media_type="application/zip",
            background=BackgroundTask(archive_path.unlink, missing_ok=True),
        )

    def endpoint_overview(
        self, token_payload: Any = Depends(verify_token)
    ) -> BackupOverviewData:
        """FastAPI 备份概览入口。"""
        self._require_superuser(token_payload)
        return self._run(self.overview)

    def endpoint_create_backup(
        self,
        payload: CreateBackupRequest,
        token_payload: Any = Depends(verify_token),
    ) -> BackupManifestData:
        """FastAPI 创建备份入口。"""
        self._require_superuser(token_payload)
        return self._run(self.create_backup, payload)

    def endpoint_config(
        self, token_payload: Any = Depends(verify_token)
    ) -> BackupConfigData:
        """FastAPI 配置页读取入口。"""
        self._require_superuser(token_payload)
        return self._run(self.config)

    def endpoint_run_automatic_backup(
        self, token_payload: Any = Depends(verify_token)
    ) -> AutomaticBackupData:
        """FastAPI 立即执行自动备份入口。"""
        self._require_superuser(token_payload)
        return self._run(self.run_automatic_backup)

    def endpoint_encryption_status(
        self, token_payload: Any = Depends(verify_token)
    ) -> EncryptionStatusData:
        """FastAPI 备份口令状态入口。"""
        self._require_superuser(token_payload)
        return self._run(self.encryption_status)

    def endpoint_update_encryption_secret(
        self,
        payload: EncryptionSecretRequest,
        token_payload: Any = Depends(verify_token),
    ) -> EncryptionStatusData:
        """FastAPI 设置或清除备份口令入口。"""
        self._require_superuser(token_payload)
        return self._run(self.update_encryption_secret, payload)

    def endpoint_verify_backup(
        self, backup_id: str, token_payload: Any = Depends(verify_token)
    ) -> BackupVerificationData:
        """FastAPI 校验备份入口。"""
        self._require_superuser(token_payload)
        return self._run(self.verify_backup, backup_id)

    def endpoint_delete_backup(
        self, backup_id: str, token_payload: Any = Depends(verify_token)
    ) -> BackupDeleteData:
        """FastAPI 删除备份入口。"""
        self._require_superuser(token_payload)
        return self._run(self.delete_backup, backup_id)

    def endpoint_preview_restore(
        self, backup_id: str, token_payload: Any = Depends(verify_token)
    ) -> RestorePreviewData:
        """FastAPI 恢复预检入口。"""
        self._require_superuser(token_payload)
        return self._run(self.preview_restore, backup_id)

    def endpoint_restore_logical(
        self,
        payload: RestoreLogicalRequest,
        token_payload: Any = Depends(verify_token),
    ) -> RestoreLogicalData:
        """FastAPI 在线选择性恢复入口。"""
        self._require_superuser(token_payload)
        return self._run(self.restore_logical, payload)

    def endpoint_read_guide(
        self, backup_id: str, token_payload: Any = Depends(verify_token)
    ) -> RecoveryGuideData:
        """FastAPI 读取离线教程入口。"""
        self._require_superuser(token_payload)
        return self._run(self.read_guide, backup_id)

    def endpoint_export_backup(
        self, backup_id: str, token_payload: Any = Depends(verify_token)
    ) -> FileResponse:
        """FastAPI 完整备份包导出入口。"""
        self._require_superuser(token_payload)
        try:
            return self.export_backup(backup_id)
        except Exception as error:
            mapped = self._translate_error(error)
            raise HTTPException(
                status_code=mapped.status_code,
                detail=mapped.message,
            ) from error


def build_api_routes(plugin: Any) -> List[Dict[str, Any]]:
    """构建供联邦 UI 使用的 Bearer API 路由。"""
    controller = BackupCenterApiController(plugin)
    plugin._api_controller = controller
    specs = [
        ("/overview", controller.endpoint_overview, ["GET"], "获取备份中心概览", BackupOverviewData),
        ("/config", controller.endpoint_config, ["GET"], "读取备份中心配置", BackupConfigData),
        ("/run", controller.endpoint_run_automatic_backup, ["POST"], "立即执行一次自动备份", AutomaticBackupData),
        ("/backups", controller.endpoint_create_backup, ["POST"], "创建可选加密备份", BackupManifestData),
        ("/encryption/status", controller.endpoint_encryption_status, ["GET"], "读取备份口令状态", EncryptionStatusData),
        ("/encryption/secret", controller.endpoint_update_encryption_secret, ["POST"], "设置备份加密口令", EncryptionStatusData),
        ("/backups/{backup_id}/verify", controller.endpoint_verify_backup, ["GET"], "校验备份", BackupVerificationData),
        ("/backups/{backup_id}/delete", controller.endpoint_delete_backup, ["POST"], "删除备份", BackupDeleteData),
        ("/backups/{backup_id}/preview", controller.endpoint_preview_restore, ["GET"], "预检恢复", RestorePreviewData),
        ("/backups/{backup_id}/guide", controller.endpoint_read_guide, ["GET"], "读取离线恢复教程", RecoveryGuideData),
        ("/backups/{backup_id}/export", controller.endpoint_export_backup, ["GET"], "导出完整离线恢复包", None),
        ("/restore/logical", controller.endpoint_restore_logical, ["POST"], "执行选择性恢复", RestoreLogicalData),
    ]
    routes: List[Dict[str, Any]] = []
    for path, endpoint, methods, summary, response_model in specs:
        route: Dict[str, Any] = {
            "path": path,
            "endpoint": endpoint,
            "methods": methods,
            "auth": "bear",
            "summary": summary,
            "response_model": response_model,
        }
        if response_model is None:
            route["response_class"] = FileResponse
            route["responses"] = {
                200: {
                    "description": "完整离线恢复包",
                    "content": {"application/zip": {}},
                }
            }
        routes.append(route)
    return routes
