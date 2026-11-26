"""下载中心 MoviePilot V3 API 请求与业务响应模型。"""

from __future__ import annotations

from typing import Literal

from app.schemas.common import JsonData
from pydantic import BaseModel, ConfigDict, Field

from .auto_delete import Status as AutoDeleteStatus


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
    type: str | None = None


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


class ModuleRuntime(BaseModel):
    """每项实际能力的生效门禁、运行阶段和可解释统计。"""

    key: str
    title: str
    enabled: bool
    state: str
    detail: str
    metrics: dict[str, JsonData] = Field(default_factory=dict)
    pending: int = 0
    error: str = ""


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
    modules: list[ModuleRuntime] = Field(default_factory=list)
    auto_delete: AutoDeleteStatus = Field(default_factory=AutoDeleteStatus)


class ActionResult(ApiBusinessModel):
    """带旧版 code 的操作业务数据。"""

    code: int = 0
    msg: str = ""


class RetryRenamesResult(ActionResult):
    """批量补刀统计。"""

    history: int = 0
    dirty: int = 0
    total: int = 0
    attempted: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


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
    skipped: list[dict[str, JsonData]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class TagCleanupExecuteResult(ActionResult):
    """下载器标签清理执行结果。"""

    removed: list[dict[str, JsonData]] = Field(default_factory=list)
    skipped: list[dict[str, JsonData]] = Field(default_factory=list)
    failed: list[dict[str, JsonData]] = Field(default_factory=list)


class TagCompletionScanResult(ActionResult):
    """下载器标签补全扫描结果。"""

    downloaders: list[dict[str, JsonData]] = Field(default_factory=list)
    errors: list[dict[str, JsonData]] = Field(default_factory=list)


class TagCompletionExecuteResult(ActionResult):
    """下载器标签补全执行结果。"""

    added: list[dict[str, JsonData]] = Field(default_factory=list)
    skipped: list[dict[str, JsonData]] = Field(default_factory=list)
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


class TagCompletionScanRequest(ApiRequestModel):
    """下载器标签补全扫描请求。"""

    request_id: str = Field(min_length=1, max_length=128, description="本次扫描请求的幂等标识")
    downloaders: list[str] = Field(default_factory=list, description="要扫描的下载器名称")
    torrent_hashes: list[str] = Field(default_factory=list, max_length=100, description="仅扫描指定 hash，留空扫描全部任务")


class TagCompletionSelection(ApiRequestModel):
    """用户确认的单类标签组标识。"""

    downloader: str = Field(min_length=1, max_length=128, description="扫描结果中的下载器名称")
    kind: Literal["site", "transfer", "iyuu", "official"] = Field(description="扫描结果中的标签类别")
    tag: str = Field(min_length=1, max_length=256, description="扫描结果中的标签名称")


class TagCompletionExecuteRequest(ApiRequestModel):
    """按服务端扫描快照登记标签补全任务。"""

    request_id: str = Field(min_length=1, max_length=128, description="本次执行请求的幂等标识")
    scan_task_id: str = Field(min_length=1, max_length=128, description="待确认的扫描任务标识")
    repairs: list[TagCompletionSelection] = Field(
        default_factory=list,
        max_length=1000,
        description="用户确认的标签组标识",
    )


class TagCompletionCancelRequest(ApiRequestModel):
    """停止指定的标签补全后台任务。"""

    task_id: str = Field(min_length=1, max_length=128, description="要停止的任务标识")


class TagCompletionTaskResult(ActionResult):
    """标签补全后台任务的轻量状态。"""

    found: bool = Field(default=False, description="任务是否存在")
    task_id: str = Field(default="", description="任务标识")
    request_id: str = Field(default="", description="提交请求的幂等标识")
    operation: str = Field(default="", description="任务类型：扫描或执行")
    status: str = Field(default="", description="任务状态")
    phase: str = Field(default="", description="当前处理阶段")
    current: int = Field(default=0, description="当前处理数量")
    total: int = Field(default=0, description="待处理总数")
    progress: int = Field(default=0, description="完成百分比")
    can_cancel: bool = Field(default=False, description="当前任务是否可取消")
    result_available: bool = Field(default=False, description="任务结果是否可读取")


class TagCompletionResultResponse(ActionResult):
    """标签补全后台任务的完整扫描或执行结果。"""

    result: dict[str, JsonData] = Field(default_factory=dict, description="当前分页的扫描或执行结果")
    offset: int = Field(default=0, description="本页起始游标")
    next_offset: int = Field(default=0, description="下一页起始游标")
    total: int = Field(default=0, description="全部结果项数量")
    complete: bool = Field(default=True, description="是否已读取所有分页")
