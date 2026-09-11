"""DoubanCenter V3 API 业务响应模型。"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel


class FlexibleRecord(BaseModel):
    """保留插件记录扩展字段的基础模型。"""

    model_config = ConfigDict(extra="allow")


class MediaRecord(FlexibleRecord):
    """描述榜单、订阅和归档中的媒体记录。"""

    title: str = ""
    name: str = ""
    year: Union[str, int, None] = ""
    media_source: Optional[str] = None
    media_id: Optional[str] = None
    media_type: str = ""
    type: str = ""
    tmdb_id: Union[str, int, None] = None
    tmdbid: Union[str, int, None] = None
    douban_id: Union[str, int, None] = None
    doubanid: Union[str, int, None] = None
    bangumi_id: Union[str, int, None] = None
    bangumiid: Union[str, int, None] = None
    time: str = ""
    unique: str = ""


class PageData(FlexibleRecord):
    """描述插件详情页的通用分页数据。"""

    items: List[FlexibleRecord] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


class StatsPayload(FlexibleRecord):
    """描述订阅统计数据。"""

    total: int = 0
    rank_dist: Dict[str, int] = Field(default_factory=dict)
    rank_stats: List[FlexibleRecord] = Field(default_factory=list)
    type_dist: Dict[str, int] = Field(default_factory=dict)
    month_new: int = 0


class OverviewPayload(FlexibleRecord):
    """描述设置页运行总览。"""

    code: int = 0
    cards: Dict[str, FlexibleRecord] = Field(default_factory=dict)
    attention: Dict[str, Union[str, int, bool]] = Field(default_factory=dict)
    governance: Dict[str, Union[str, int, bool]] = Field(default_factory=dict)
    stats: StatsPayload = Field(default_factory=StatsPayload)
    flows: List[FlexibleRecord] = Field(default_factory=list)


class ConfigPayload(FlexibleRecord):
    """描述联邦 UI 运行配置。"""

    dashboard_rank_keys: List[str] = Field(default_factory=list)
    rank_options: List[FlexibleRecord] = Field(default_factory=list)
    custom_ranks: List[FlexibleRecord] = Field(default_factory=list)
    blacklist_keywords: str = ""
    observe_days: int = 0
    observe_rank_keys: List[str] = Field(default_factory=list)
    wish_status: FlexibleRecord = Field(default_factory=FlexibleRecord)


class OperationPayload(FlexibleRecord):
    """描述删除、恢复和订阅操作的可选结果数据。"""

    archive_id: str = ""


class RepairFolioPostersPayload(FlexibleRecord):
    """描述豆瓣时间线历史海报修复结果。"""

    updated: int = 0


class FolioRepairTarget(BaseModel):
    """待核验的旧记录与实际播放身份，不接收未经核验的目标豆瓣 ID。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: str = Field(min_length=1, max_length=500)
    media_source: str = Field(min_length=1, max_length=64)
    media_id: str = Field(min_length=1, max_length=200)
    season: int = Field(ge=0, le=9999)
    episode_group: str = Field(default="", max_length=128)


class FolioRepairPreviewRequest(BaseModel):
    """限制每次修复为可审阅的一小批明确目标。"""

    model_config = ConfigDict(extra="forbid")
    items: list[FolioRepairTarget] = Field(min_length=1, max_length=20)
    refresh_posters: bool = False


class FolioRepairApplyRequest(BaseModel):
    """仅接受当前实例生成的短期修复预览。"""

    model_config = ConfigDict(extra="forbid")
    plan_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class FolioRepairItem(BaseModel):
    """一条历史记录修正前后的完整对照。"""

    key: str
    status: Literal["ready", "unchanged", "unresolved"]
    changed: bool
    reason: str = ""
    before: FlexibleRecord | None = None
    after: FlexibleRecord | None = None
    evidence: FlexibleRecord = Field(default_factory=FlexibleRecord)


class FolioRepairPreviewData(BaseModel):
    """历史身份修复的只读预览结果。"""

    plan_id: str
    ready: bool
    items: list[FolioRepairItem]
    changed: int
    raw_count: int
    timeline_before: int
    timeline_after: int
    expires_in: int


class FolioRepairApplyData(BaseModel):
    """修复回执及备份位置。"""

    updated: int
    backup_path: str
    already_applied: bool
    raw_count: int
    timeline_count: int


class FolioData(RootModel[Dict[str, Union[FlexibleRecord, List[FlexibleRecord], str, int, bool, None]]]):
    """豆瓣时间数据响应。"""


class OverviewData(RootModel[OverviewPayload]):
    """运行总览响应。"""


class ConfigData(RootModel[ConfigPayload]):
    """前端配置响应。"""


class RankHistoryData(RootModel[Dict[str, List[MediaRecord]]]):
    """榜单历史响应。"""


class ResolveMediaData(RootModel[MediaRecord]):
    """媒体识别响应。"""


class SubscribeData(RootModel[OperationPayload]):
    """订阅操作响应。"""


class RefreshRssData(RootModel[Dict[str, List[MediaRecord]]]):
    """RSS 刷新响应。"""


class StatsData(RootModel[StatsPayload]):
    """订阅统计响应。"""


class SubscribeHistoryData(RootModel[PageData]):
    """订阅历史分页响应。"""


class PendingObservationsData(RootModel[List[MediaRecord]]):
    """观察期条目响应。"""


class AntiCheatLogsData(RootModel[List[FlexibleRecord]]):
    """观察日志响应。"""


class DeleteSubscribeHistoryData(RootModel[OperationPayload]):
    """订阅历史删除响应。"""


class DeleteObservationData(RootModel[OperationPayload]):
    """观察条目删除响应。"""


class DeleteAntiCheatLogData(RootModel[OperationPayload]):
    """观察日志删除响应。"""


class ArchiveRecordsData(RootModel[PageData]):
    """归档分页响应。"""


class RestoreArchiveData(RootModel[OperationPayload]):
    """归档恢复响应。"""


class DeleteArchiveData(RootModel[OperationPayload]):
    """归档删除响应。"""


class RepairFolioPostersData(RootModel[RepairFolioPostersPayload]):
    """豆瓣时间线海报修复响应。"""


API_RESPONSE_MODELS = {
    "/folio_data": FolioData,
    "/overview": OverviewData,
    "/config": ConfigData,
    "/rank_history": RankHistoryData,
    "/resolve_media": ResolveMediaData,
    "/subscribe": SubscribeData,
    "/refresh_rss": RefreshRssData,
    "/stats": StatsData,
    "/subscribe_history": SubscribeHistoryData,
    "/pending_observations": PendingObservationsData,
    "/anti_cheat_logs": AntiCheatLogsData,
    "/delete_subscribe_history": DeleteSubscribeHistoryData,
    "/delete_observation": DeleteObservationData,
    "/delete_anti_cheat_log": DeleteAntiCheatLogData,
    "/archive_records": ArchiveRecordsData,
    "/restore_archive": RestoreArchiveData,
    "/delete_archive": DeleteArchiveData,
    "/repair_folio_posters": RepairFolioPostersData,
    "/folio_repair/preview": FolioRepairPreviewData,
    "/folio_repair/apply": FolioRepairApplyData,
}
