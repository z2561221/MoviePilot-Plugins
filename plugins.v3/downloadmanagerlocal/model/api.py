"""下载中心 MoviePilot V3 API 请求与业务响应模型。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import JsonData


class ApiBusinessModel(BaseModel):
    """允许领域服务在稳定字段之外附加兼容数据的业务模型。"""

    model_config = ConfigDict(extra="allow")


class ApiRequestModel(BaseModel):
    """拒绝未知字段的插件 API 请求基类。"""

    model_config = ConfigDict(extra="forbid")


class SelectionItem(ApiBusinessModel):
    """下载器或站点选择项。"""

    title: str
    value: str | int
    type: Optional[str] = None


class RenameRecord(ApiBusinessModel):
    """种子重命名或归档记录。"""

    hash: str = ""
    original_name: str = ""
    after_name: str = ""
    success: bool = False
    reason: str = ""
    time: str = ""


class RenamePageResult(ApiBusinessModel):
    """重命名记录分页结果。"""

    total: int = 0
    page: int = 1
    page_size: int = 15
    total_pages: int = 1
    items: list[RenameRecord] = Field(default_factory=list)


class DiagnosticsResult(ApiBusinessModel):
    """插件诊断摘要。"""

    code: int = 0
    time: str = ""
    plugin: dict[str, JsonData] = Field(default_factory=dict)
    downloaders: dict[str, JsonData] = Field(default_factory=dict)
    config: dict[str, JsonData] = Field(default_factory=dict)
    paths: dict[str, JsonData] = Field(default_factory=dict)
    rename_history: dict[str, JsonData] = Field(default_factory=dict)
    rename_archive: dict[str, JsonData] = Field(default_factory=dict)
    checks: list[dict[str, JsonData]] = Field(default_factory=list)


class OverviewResult(ApiBusinessModel):
    """下载中心总览数据。"""

    code: int = 0
    plugin: dict[str, JsonData] = Field(default_factory=dict)
    config: dict[str, JsonData] = Field(default_factory=dict)
    downloaders: dict[str, JsonData] = Field(default_factory=dict)
    rename_history: dict[str, JsonData] = Field(default_factory=dict)
    archive: dict[str, JsonData] = Field(default_factory=dict)
    speed_monitor: dict[str, JsonData] = Field(default_factory=dict)
    upload_limit: dict[str, JsonData] = Field(default_factory=dict)
    cards: dict[str, JsonData] = Field(default_factory=dict)


class ActionResult(ApiBusinessModel):
    """带旧版 code 的操作业务数据。"""

    code: int = 0
    msg: str = ""


class RetryRenamesResult(ActionResult):
    """批量补刀统计。"""

    history: int = 0
    dirty: int = 0
    total: int = 0


class HashActionResult(ActionResult):
    """针对单个种子 hash 的操作结果。"""

    hash: str = ""


class ResetBaselineResult(ActionResult):
    """速度基准重置结果。"""

    success: bool = False
    downloader_id: str = ""


class UploadLimitStatusResult(ActionResult):
    """上传限速运行状态。"""

    service_status: str = ""
    active: bool = False
    managed_torrents: int = 0
    grace_torrents: int = 0
    errors: list[str] = Field(default_factory=list)


class UploadLimitReallocateResult(UploadLimitStatusResult):
    """上传额度重新分配结果。"""


class UploadLimitSiteTagsResult(ActionResult):
    """站点标签扫描结果。"""

    items: list[dict[str, JsonData]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    rules: dict[str, JsonData] = Field(default_factory=dict)


class UploadLimitRulesResult(ActionResult):
    """上传限速站点策略保存结果。"""

    rules: dict[str, JsonData] = Field(default_factory=dict)


class UploadLimitDisableResult(ActionResult):
    """停用上传限速并恢复原值的结果。"""

    errors: list[str] = Field(default_factory=list)


class TagCleanupScanResult(ActionResult):
    """下载器标签扫描结果。"""

    downloaders: list[dict[str, JsonData]] = Field(default_factory=list)
    auto_removed: list[dict[str, JsonData]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class TagCleanupExecuteResult(ActionResult):
    """下载器标签清理执行结果。"""

    removed: list[dict[str, JsonData]] = Field(default_factory=list)
    failed: list[dict[str, JsonData]] = Field(default_factory=list)


class EmptyRequest(ApiRequestModel):
    """没有业务字段的显式 JSON 请求体。"""


class ResetBaselineRequest(ApiRequestModel):
    """速度基准重置请求。"""

    downloader_id: str = Field(min_length=1, max_length=128)


class UploadLimitSiteRule(ApiRequestModel):
    """单站点上传限速策略。"""

    limit_kib: int = Field(default=0, ge=0)


class UploadLimitSiteTagsRequest(ApiRequestModel):
    """上传限速站点标签扫描请求。"""

    downloaders: list[str] = Field(default_factory=list)
    rules: dict[str, UploadLimitSiteRule] = Field(default_factory=dict)


class UploadLimitRulesRequest(ApiRequestModel):
    """上传限速站点策略保存请求。"""

    rules: dict[str, UploadLimitSiteRule] = Field(default_factory=dict)


class TagCleanupScanRequest(ApiRequestModel):
    """下载器标签扫描请求。"""

    downloaders: list[str] = Field(default_factory=list)


class TagCleanupRemoval(ApiRequestModel):
    """待清理标签快照。"""

    downloader: str = Field(min_length=1, max_length=128)
    tag: str = Field(min_length=1, max_length=256)
    hashes: list[str] = Field(default_factory=list)


class TagCleanupExecuteRequest(ApiRequestModel):
    """按扫描快照执行标签清理的请求。"""

    removals: list[TagCleanupRemoval] = Field(default_factory=list)
