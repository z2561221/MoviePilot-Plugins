"""工具中心 V3 API 业务响应模型。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ToolkitModuleStatus(BaseModel):
    """工具中心单个模块的统一状态。"""

    success: Optional[bool] = None
    module_name: Optional[str] = None
    error: Optional[str] = None
    run_mode: Optional[str] = None
    enabled: Optional[bool] = None
    auto_delete: Optional[bool] = None
    cron: Optional[str] = None
    scan_enabled: bool | None = None
    scan_cron: str | None = None
    scan_notify: bool | None = None
    cleanup_enabled: bool | None = None
    cleanup_cron: str | None = None
    cleanup_notify: bool | None = None
    scan_error: str | None = None
    cleanup_error: str | None = None
    last_error: Optional[str] = None
    plan_count: Optional[int] = None
    last_scan_at: Optional[str] = None
    last_cycle_at: Optional[str] = None
    next_cycle_at: Optional[str] = None
    cooldown_minutes: Optional[int] = None
    cycle_batch_size: Optional[int] = None
    paths: Optional[int] = None
    last_count: Optional[int] = None
    keys: Optional[int] = None
    size_kb: Optional[float] = None


class ToolkitModulesStatus(BaseModel):
    """工具中心全部模块的状态集合。"""

    library_cleanup: ToolkitModuleStatus
    check_missing: ToolkitModuleStatus
    tmdb_cache: ToolkitModuleStatus


class ToolkitStatusData(BaseModel):
    """工具中心状态接口的业务数据。"""

    enabled: bool
    modules: ToolkitModulesStatus


class ToolkitHistoryItem(BaseModel):
    """工具中心单条运行历史。"""

    time: str = ""
    module: str = ""
    module_name: str = ""
    status: str = ""
    summary: str = ""
    duration: float = 0


class ToolkitHistoryData(BaseModel):
    """工具中心运行历史分页数据。"""

    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[ToolkitHistoryItem] = Field(default_factory=list)


class ToolkitOptionItem(BaseModel):
    """工具中心下拉选项。"""

    title: str
    value: str


class ToolkitLibraryCleanupOptions(BaseModel):
    """清理库存需要的媒体服务器选项。"""

    servers: list[ToolkitOptionItem] = Field(default_factory=list)
    libraries: list[ToolkitOptionItem] = Field(default_factory=list)
    users: list[ToolkitOptionItem] = Field(default_factory=list)
    error: Optional[str] = None


class ToolkitOptionsData(BaseModel):
    """工具中心配置选项接口的业务数据。"""

    library_cleanup: ToolkitLibraryCleanupOptions


class ToolkitCleanupPlanItem(BaseModel):
    """清理计划中的单个媒体快照。"""

    queue_key: str = ""
    movie_id: str = ""
    code: str = ""
    title: str = ""
    server: str = ""
    library_id: str = ""
    library_name: str = ""
    date_created: str = ""
    age_days: Optional[int] = None
    played: Optional[bool] = None
    favorite: Optional[bool] = None
    queued_at: str = ""
    attempts: int = 0
    last_attempt_at: str = ""
    last_error: str = ""


class ToolkitCleanupPlanData(BaseModel):
    """清理计划分页数据与周期状态。"""

    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[ToolkitCleanupPlanItem] = Field(default_factory=list)
    last_scan_at: str = ""
    last_cycle_at: str = ""
    last_cycle: dict = Field(default_factory=dict)
    last_scan: dict = Field(default_factory=dict)
    next_cycle_at: str = ""
    cooldown_minutes: int = 0
    batch_size: int = 10


class ToolkitCacheSnapshot(BaseModel):
    """TMDB 缓存清理前后的状态快照。"""

    keys: int = 0
    size_kb: float = 0
    error: Optional[str] = None


class ToolkitMissingItem(BaseModel):
    """扫描缺集接口返回的单个结果。"""

    path: str = ""
    status: Optional[str] = None
    title: Optional[str] = None
    season: Optional[int] = None
    missing: list[int] = Field(default_factory=list)


class ToolkitRunData(BaseModel):
    """工具模块运行接口的统一业务数据。"""

    summary: Optional[str] = None
    operation: str | None = None
    busy: bool | None = None
    deleted: Optional[int] = None
    total: Optional[int] = None
    before: Optional[ToolkitCacheSnapshot] = None
    after: Optional[ToolkitCacheSnapshot] = None
    missing_total: Optional[int] = None
    items: Optional[list[ToolkitMissingItem]] = None
    scanned_count: Optional[int] = None
    queued_added: Optional[int] = None
    queued_removed: int | None = None
    qualified_count: int | None = None
    queue_count: Optional[int] = None
    processed_count: Optional[int] = None
    success_count: Optional[int] = None
    fail_count: Optional[int] = None
    remaining_count: int | None = None
    unknown_count: int | None = None
    skipped_count: int | None = None
    already_absent_count: int | None = None
    cleared_count: Optional[int] = None
    cooldown: Optional[bool] = None
