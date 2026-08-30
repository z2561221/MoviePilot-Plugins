"""AgentRank V3 API 的端点专属业务响应模型。"""

from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, ConfigDict, create_model


class AgentRankApiData(BaseModel):
    """允许稳定顶层字段之外的受控业务扩展。"""

    model_config = ConfigDict(extra="allow")


class StatusData(AgentRankApiData):
    """插件状态与启用条件。"""

    enabled: bool
    state: str
    plugin_version: str
    validation_errors: List[Any]


class ConfigOptionsData(AgentRankApiData):
    """配置页运行选项。"""

    config: Dict[str, Any]
    defaults: Dict[str, Any]
    emby_identities: List[Dict[str, Any]]


class ProfileScopedData(AgentRankApiData):
    """绑定一个 Emby 画像身份的响应。"""

    profile_id: str


class BoardData(ProfileScopedData):
    """当前推荐榜单。"""

    status: str
    recommendations: List[Dict[str, Any]]


class RunProgressData(ProfileScopedData):
    """一次榜单任务的实时进度。"""

    status: str


class HistoryData(ProfileScopedData):
    """分页运行或榜单历史。"""

    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class CandidateActionData(AgentRankApiData):
    """针对当前榜单候选的状态变更。"""

    candidate_id: str


class FeedbackData(CandidateActionData):
    """幂等反馈写入结果。"""

    created: bool


class AnalysisData(ProfileScopedData):
    """结构化推荐分析。"""

    analysis_id: str
    candidate_id: str


class AnalysisCommentData(AgentRankApiData):
    """分析评论入账与修订队列状态。"""

    created: bool


class ConversationSnapshotData(AgentRankApiData):
    """有界对话线程快照。"""

    thread: Optional[Dict[str, Any]]
    messages: List[Dict[str, Any]]
    commands: List[Dict[str, Any]]


class CommandResultData(AgentRankApiData):
    """待确认 Agent 命令的处理结果。"""

    command: Dict[str, Any]


class PendingActionData(AgentRankApiData):
    """统一待办项目的状态变更。"""

    action: str


class ProfileTagData(AgentRankApiData):
    """人工画像标签变更。"""

    changed: bool
    profile: Dict[str, Any]


class ConsumptionData(AgentRankApiData):
    """榜单曝光或消费事实。"""

    consumption: Dict[str, Any]


class FullResetPrepareData(ProfileScopedData):
    """彻底重置的一次性确认信息。"""

    confirmation_token: str
    expires_at: str


class SubscriptionData(AgentRankApiData):
    """手动订阅执行结果。"""

    success: bool
    changed: bool
    code: str
    message: str


def _model(name: str, base: Type[AgentRankApiData]) -> Type[AgentRankApiData]:
    """基于明确字段基类创建端点专属 OpenAPI 名称。"""
    return create_model(name, __base__=base)


_MODEL_SPECS: Dict[str, tuple[str, Type[AgentRankApiData]]] = {
    "/status": ("AgentRankStatusData", StatusData),
    "/overview": ("AgentRankOverviewData", ProfileScopedData),
    "/config/options": ("AgentRankConfigOptionsData", ConfigOptionsData),
    "/board": ("AgentRankBoardData", BoardData),
    "/profile": ("AgentRankProfileData", ProfileScopedData),
    "/run-progress": ("AgentRankRunProgressData", RunProgressData),
    "/refresh": ("AgentRankRefreshData", ProfileScopedData),
    "/playback/sync": ("AgentRankPlaybackSyncData", ProfileScopedData),
    "/attribution": ("AgentRankAttributionData", ProfileScopedData),
    "/attribution/native-drawer-opened": (
        "AgentRankNativeDrawerOpenedData",
        ProfileScopedData,
    ),
    "/attribution/verify": ("AgentRankAttributionVerifyData", ProfileScopedData),
    "/archive": ("AgentRankArchiveData", FeedbackData),
    "/feedback": ("AgentRankFeedbackData", FeedbackData),
    "/analysis": ("AgentRankAnalysisData", AnalysisData),
    "/analysis/comment": ("AgentRankAnalysisCommentData", AnalysisCommentData),
    "/conversation": ("AgentRankConversationData", ConversationSnapshotData),
    "/conversation/status": ("AgentRankConversationStatusData", ProfileScopedData),
    "/conversation/messages": (
        "AgentRankConversationMessageData",
        ConversationSnapshotData,
    ),
    "/conversation/messages/retry": (
        "AgentRankConversationRetryData",
        ConversationSnapshotData,
    ),
    "/conversation/commands/respond": (
        "AgentRankConversationCommandData",
        CommandResultData,
    ),
    "/pending": ("AgentRankPendingData", ProfileScopedData),
    "/pending/interview/start": ("AgentRankPendingInterviewData", ProfileScopedData),
    "/pending/respond": ("AgentRankPendingRespondData", PendingActionData),
    "/restore": ("AgentRankRestoreData", CandidateActionData),
    "/archive/delete": ("AgentRankArchiveDeleteData", CandidateActionData),
    "/profile/clear": ("AgentRankProfileClearData", CandidateActionData),
    "/profile/tags": ("AgentRankProfileTagsData", ProfileTagData),
    "/run-history": ("AgentRankRunHistoryData", HistoryData),
    "/board-history": ("AgentRankBoardHistoryData", HistoryData),
    "/learning-health": ("AgentRankLearningHealthData", ProfileScopedData),
    "/consumption/exposure": ("AgentRankExposureData", ConsumptionData),
    "/consumption/detail-opened": ("AgentRankDetailOpenedData", ConsumptionData),
    "/consumption/interaction": ("AgentRankConsumptionData", ConsumptionData),
    "/data/export": ("AgentRankDataExportData", ProfileScopedData),
    "/data/reset/learning": ("AgentRankLearningResetData", ProfileScopedData),
    "/data/reset/full/prepare": ("AgentRankFullResetPrepareData", FullResetPrepareData),
    "/data/reset/full": ("AgentRankFullResetData", ProfileScopedData),
    "/subscribe": ("AgentRankSubscribeData", SubscriptionData),
}

API_RESPONSE_MODELS: Dict[str, Type[AgentRankApiData]] = {
    path: _model(name, base) for path, (name, base) in _MODEL_SPECS.items()
}
