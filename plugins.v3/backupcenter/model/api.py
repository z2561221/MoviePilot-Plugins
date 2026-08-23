"""备份中心 V3 API 请求与业务响应模型。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BackupScopeData(BaseModel):
    """描述备份包包含的数据范围。"""

    model_config = ConfigDict(extra="forbid")

    mp_settings: bool = False
    plugin_settings: bool = False
    plugin_data: bool = False
    plugin_files: bool = False
    app_env: bool = False
    cookies: bool = False
    database: bool = False


class RestoreSelectionData(BaseModel):
    """描述运行中允许恢复的数据范围。"""

    model_config = ConfigDict(extra="forbid")

    mp_settings: bool = False
    plugin_settings: bool = False
    plugin_data: bool = False
    plugin_files: bool = False


class ManualBackupSelectionData(BaseModel):
    """描述 MoviePilot 或单插件手动备份的显式选择。"""

    model_config = ConfigDict(extra="forbid")

    configuration: bool = False
    data: bool = False
    mp_settings: bool = False
    plugin_settings: bool = False
    plugin_data: bool = False
    plugin_files: bool = False
    app_env: bool = False
    cookies: bool = False
    database: bool = False


class CreateBackupRequest(BaseModel):
    """创建手动备份的请求体。"""

    model_config = ConfigDict(extra="forbid")

    target: Literal["moviepilot", "plugin"] = "plugin"
    selection: ManualBackupSelectionData = Field(
        default_factory=ManualBackupSelectionData
    )
    plugin_ids: list[str] = Field(default_factory=list)


class EncryptionSecretRequest(BaseModel):
    """设置或清除备份口令的请求体。"""

    model_config = ConfigDict(extra="forbid")

    action: Literal["set", "clear"] = "set"
    password: str | None = None


class RestoreLogicalRequest(BaseModel):
    """执行在线选择性恢复的请求体。"""

    model_config = ConfigDict(extra="forbid")

    backup_id: str
    selection: RestoreSelectionData = Field(default_factory=RestoreSelectionData)
    plugin_ids: list[str] | None = None
    password: str | None = None


class PluginOptionData(BaseModel):
    """描述一个可选择的插件。"""

    model_config = ConfigDict(extra="forbid")

    title: str
    value: str


class SelectedPluginData(BaseModel):
    """描述备份包内记录的插件。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str


class BackupContentCountsData(BaseModel):
    """描述备份包内各类内容的数量。"""

    model_config = ConfigDict(extra="forbid")

    mp_settings: int = 0
    plugin_settings: int = 0
    plugin_data: int = 0
    plugin_files: int = 0
    cookies: int = 0


class DatabaseSnapshotData(BaseModel):
    """描述完整数据库快照的类型和文件。"""

    model_config = ConfigDict(extra="allow")

    type: str = "none"
    included: bool = False
    file: str | None = None


class ScryptParametersData(BaseModel):
    """描述加密负载使用的 scrypt 参数。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    n: int
    r: int
    p: int
    salt: str


class EncryptionMetadataData(BaseModel):
    """描述备份负载的公开加密参数。"""

    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    format: str | None = None
    cipher: str | None = None
    kdf: ScryptParametersData | None = None
    nonce: str | None = None
    tag: str | None = None


class BackupManifestData(BaseModel):
    """描述一份可公开展示和校验的备份清单。"""

    model_config = ConfigDict(extra="allow")

    format_version: int
    backup_id: str
    display_name: str
    created_at: str
    source_mp_version: str
    database: DatabaseSnapshotData
    scope: BackupScopeData
    selected_plugin_ids: list[str] = Field(default_factory=list)
    selected_plugins: list[SelectedPluginData] = Field(default_factory=list)
    content_counts: BackupContentCountsData
    emergency: bool = False
    backup_kind: str
    manual_target: str | None = None
    encryption: EncryptionMetadataData
    encrypted: bool = False
    offline_database_restore_required: bool = False
    package_size: int | None = None


class BackupOverviewData(BaseModel):
    """描述备份中心首页概览。"""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    backup_root: str
    backup_count: int
    backups: list[BackupManifestData] = Field(default_factory=list)
    database_type: str
    encryption_configured: bool
    encryption_active: bool
    installed_plugin_ids: list[str] = Field(default_factory=list)
    plugin_options: list[PluginOptionData] = Field(default_factory=list)
    online_restore: str
    database_restore: str


class BackupConfigData(BaseModel):
    """描述配置页需要的已保存配置。"""

    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    auto_backup_enabled: bool = False
    auto_backup_cron: str = "0 3 * * 6"
    retention_count: int = 5
    auto_backup_scope: BackupScopeData = Field(default_factory=BackupScopeData)
    encryption_configured: bool = False


class AutomaticBackupData(BaseModel):
    """描述一次立即自动备份及其清理结果。"""

    model_config = ConfigDict(extra="forbid")

    backup: BackupManifestData
    deleted_backup_ids: list[str] = Field(default_factory=list)


class EncryptionStatusData(BaseModel):
    """描述备份口令是否已保存。"""

    model_config = ConfigDict(extra="forbid")

    configured: bool


class BackupVerificationData(BaseModel):
    """描述备份校验结果。"""

    model_config = ConfigDict(extra="forbid")

    manifest: BackupManifestData
    verified_files: list[str] = Field(default_factory=list)


class BackupDeleteData(BaseModel):
    """描述备份删除结果。"""

    model_config = ConfigDict(extra="forbid")

    backup_id: str
    deleted: bool


class BackupOperationLogData(BaseModel):
    """描述一条可公开展示的备份中心运行记录。"""

    model_config = ConfigDict(extra="forbid")

    log_id: str
    operation: str
    status: Literal["success", "failure"]
    started_at: str
    finished_at: str
    duration_ms: int = 0
    backup_id: str | None = None
    message: str


class BackupLogsData(BaseModel):
    """描述最近的备份中心运行日志集合。"""

    model_config = ConfigDict(extra="forbid")

    logs: list[BackupOperationLogData] = Field(default_factory=list)
    total: int = 0


class RestorePreviewData(BaseModel):
    """描述在线恢复前的公开预检结果。"""

    model_config = ConfigDict(extra="forbid")

    manifest: BackupManifestData
    verified_files: list[str] = Field(default_factory=list)
    online_restore_allowed: bool
    database_restore_mode: str
    encrypted: bool


class RecoveryGuideData(BaseModel):
    """描述离线恢复教程和核对清单。"""

    model_config = ConfigDict(extra="forbid")

    guide: str
    checklist: str


class RestoredContentData(BaseModel):
    """描述在线恢复实际写入的内容数量。"""

    model_config = ConfigDict(extra="forbid")

    mp_settings: int = 0
    plugin_settings: int = 0
    plugin_data: int = 0
    plugin_files: list[str] = Field(default_factory=list)


class RestoreLogicalData(BaseModel):
    """描述在线选择性恢复结果。"""

    model_config = ConfigDict(extra="forbid")

    emergency_backup_id: str
    selection: RestoreSelectionData
    restored: RestoredContentData
    reload_required: list[str] = Field(default_factory=list)
    reloaded: list[str] = Field(default_factory=list)
    database_message: str
