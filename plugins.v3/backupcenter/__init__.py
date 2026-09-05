"""备份中心插件入口。"""

import re
from threading import RLock
from typing import Any, Dict, List, Tuple

from app.plugins import _PluginBase

from .controller.api import build_api_routes
from .service.backup_service import BackupService
from .service.operation_log_service import OperationLogService
from .service.restore_service import RestoreService
from .service.scheduler import build_services
from .service.secret_service import SecretService


class BackupCenter(_PluginBase):
    """为 MoviePilot 提供插件逻辑备份与选择性恢复。"""

    plugin_name = "备份中心"
    plugin_desc = "备份插件设置与数据，调用 MoviePilot 主程序保护数据库。"
    plugin_icon = "backup.png"
    plugin_color = "#00897B"
    plugin_version = "3.0.3"
    plugin_label = "系统工具,数据安全"
    plugin_author = "Kurisu"
    author_url = "https://github.com/z2561221"
    plugin_config_prefix = "backupcenter_"
    plugin_order = 35
    auth_level = 1

    _enabled = True
    _default_config = {
        "enabled": True,
        "auto_backup_enabled": False,
        "auto_backup_cron": "0 3 * * 6",
        "retention_count": 5,
        "auto_backup_scope": {
            "mp_settings": False,
            "plugin_settings": True,
            "plugin_data": True,
            "plugin_files": True,
            "app_env": False,
            "cookies": False,
        },
    }
    _config: Dict[str, Any] = {}
    _backup_service: BackupService
    _operation_log_service: OperationLogService
    _restore_service: RestoreService
    _secret_service: SecretService

    def init_plugin(self, config: dict = None) -> None:
        """初始化备份服务和当前配置。"""
        if not hasattr(self, "_operation_lock"):
            self._operation_lock = RLock()
        self._config = self._normalize_config(config)
        self._enabled = bool(self._config.get("enabled", True))
        self._secret_service = SecretService(self)
        self._backup_service = BackupService(self)
        self._operation_log_service = OperationLogService(self)
        self._restore_service = RestoreService(self, self._backup_service)

    @classmethod
    def _normalize_config(cls, config: dict | None) -> Dict[str, Any]:
        """归一化备份中心配置并限制自动清理范围。"""
        supplied = dict(config or {})
        raw = {**cls._default_config, **supplied}
        cron_value = str(supplied.get("auto_backup_cron") or "").strip()
        if not cron_value:
            legacy_time = str(supplied.get("auto_backup_time") or "03:00").strip()
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", legacy_time):
                legacy_time = "03:00"
            hour, minute = legacy_time.split(":")
            cron_value = f"{int(minute)} {int(hour)} * * 6"
        if len(cron_value.split()) != 5:
            cron_value = cls._default_config["auto_backup_cron"]
        try:
            retention_count = max(1, min(200, int(raw.get("retention_count", 5))))
        except (TypeError, ValueError):
            retention_count = 5
        default_scope = dict(cls._default_config["auto_backup_scope"])
        supplied_scope = raw.get("auto_backup_scope")
        legacy_database_scope = isinstance(supplied_scope, dict) and bool(
            supplied_scope.get("database")
        )
        if isinstance(supplied_scope, dict):
            auto_backup_scope = {
                key: bool(supplied_scope.get(key, default_value))
                for key, default_value in default_scope.items()
            }
        else:
            auto_backup_scope = default_scope
        if legacy_database_scope:
            for key in ("mp_settings", "app_env", "cookies"):
                auto_backup_scope[key] = False
        if not any(auto_backup_scope.values()):
            auto_backup_scope = default_scope
        return {
            "enabled": bool(raw.get("enabled", True)),
            "auto_backup_enabled": bool(raw.get("auto_backup_enabled", False)),
            "auto_backup_cron": cron_value,
            "retention_count": retention_count,
            "auto_backup_scope": auto_backup_scope,
        }

    def get_state(self) -> bool:
        """返回插件当前启用状态。"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """返回插件远程命令列表。"""
        return []

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明插件使用 Vue 联邦组件渲染。"""
        return "vue", "dist/assets"

    def get_api(self) -> List[Dict[str, Any]]:
        """返回供联邦界面调用的 Bearer API 路由。"""
        return build_api_routes(self)

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """返回 Vue 配置组件的初始配置。"""
        model = dict(self._config or self._default_config)
        model["encryption_configured"] = self._secret_service.has_password()
        return [], model

    def get_page(self) -> List[dict]:
        """返回 Vue 详情组件占位页面。"""
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        """返回每周自动备份服务。"""
        return build_services(self)

    def run_automatic_backup(self) -> Dict[str, Any]:
        """按配置范围执行一次自动备份并按数量清理旧自动备份。"""
        return self._operation_log_service.execute(
            "automatic_backup",
            self._run_automatic_backup,
        )

    def _run_automatic_backup(self) -> Dict[str, Any]:
        """执行一次不重复记录日志的自动备份核心流程。"""
        from .controller.api import BackupCenterApiController
        from .model.backup import BackupScope

        with self._operation_lock:
            plugin_ids = self._backup_service.available_plugin_ids()
            manifest = self._backup_service.create_backup(
                BackupScope.from_payload(self._config.get("auto_backup_scope")),
                plugin_ids=plugin_ids,
                backup_kind="automatic",
                password=self.get_backup_password(),
                plugin_names=BackupCenterApiController._plugin_name_map(plugin_ids),
            )
            deleted = self._backup_service.prune_automatic_backups(
                self._config["retention_count"],
                preserve_backup_ids=[manifest["backup_id"]],
            )
            return {"backup": manifest, "deleted_backup_ids": deleted}

    def get_backup_password(self) -> str:
        """返回当前已保存的备份口令，未设置时生成明文备份。"""
        return self._secret_service.get_password()

    def get_stored_backup_password(self) -> str:
        """返回已保存口令，供历史加密备份恢复使用。"""
        return self._secret_service.get_password()

    def stop_service(self) -> None:
        """停止插件后台服务。"""
        return None
