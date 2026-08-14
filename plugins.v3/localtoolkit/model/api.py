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
    last_error: Optional[str] = None
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
    deleted: Optional[int] = None
    total: Optional[int] = None
    before: Optional[ToolkitCacheSnapshot] = None
    after: Optional[ToolkitCacheSnapshot] = None
    missing_total: Optional[int] = None
    items: Optional[list[ToolkitMissingItem]] = None
