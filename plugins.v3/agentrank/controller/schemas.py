"""AgentRank V3 API 输出模型注册表。"""

from typing import Dict, Type

from pydantic import BaseModel, ConfigDict, create_model


class AgentRankApiData(BaseModel):
    """保留既有业务字段，并让每个 endpoint 拥有独立 OpenAPI 模型。"""

    model_config = ConfigDict(extra="allow")


def _data_model(name: str) -> Type[AgentRankApiData]:
    """创建命名明确的端点业务模型。"""
    return create_model(name, __base__=AgentRankApiData)


API_RESPONSE_MODELS: Dict[str, Type[AgentRankApiData]] = {
    "/status": _data_model("AgentRankStatusData"),
    "/overview": _data_model("AgentRankOverviewData"),
    "/config/options": _data_model("AgentRankConfigOptionsData"),
    "/board": _data_model("AgentRankBoardData"),
    "/profile": _data_model("AgentRankProfileData"),
    "/run-progress": _data_model("AgentRankRunProgressData"),
    "/refresh": _data_model("AgentRankRefreshData"),
    "/playback/sync": _data_model("AgentRankPlaybackSyncData"),
    "/attribution": _data_model("AgentRankAttributionData"),
    "/attribution/native-drawer-opened": _data_model(
        "AgentRankNativeDrawerOpenedData"
    ),
    "/attribution/verify": _data_model("AgentRankAttributionVerifyData"),
    "/archive": _data_model("AgentRankArchiveData"),
    "/feedback": _data_model("AgentRankFeedbackData"),
    "/analysis": _data_model("AgentRankAnalysisData"),
    "/analysis/comment": _data_model("AgentRankAnalysisCommentData"),
    "/conversation": _data_model("AgentRankConversationData"),
    "/conversation/status": _data_model("AgentRankConversationStatusData"),
    "/conversation/messages": _data_model("AgentRankConversationMessageData"),
    "/conversation/messages/retry": _data_model(
        "AgentRankConversationRetryData"
    ),
    "/conversation/commands/respond": _data_model(
        "AgentRankConversationCommandData"
    ),
    "/pending": _data_model("AgentRankPendingData"),
    "/pending/interview/start": _data_model("AgentRankPendingInterviewData"),
    "/pending/respond": _data_model("AgentRankPendingRespondData"),
    "/restore": _data_model("AgentRankRestoreData"),
    "/archive/delete": _data_model("AgentRankArchiveDeleteData"),
    "/profile/clear": _data_model("AgentRankProfileClearData"),
    "/profile/tags": _data_model("AgentRankProfileTagsData"),
    "/run-history": _data_model("AgentRankRunHistoryData"),
    "/board-history": _data_model("AgentRankBoardHistoryData"),
    "/learning-health": _data_model("AgentRankLearningHealthData"),
    "/consumption/exposure": _data_model("AgentRankExposureData"),
    "/consumption/detail-opened": _data_model("AgentRankDetailOpenedData"),
    "/consumption/interaction": _data_model("AgentRankConsumptionData"),
    "/data/export": _data_model("AgentRankDataExportData"),
    "/data/reset/learning": _data_model("AgentRankLearningResetData"),
    "/data/reset/full/prepare": _data_model("AgentRankFullResetPrepareData"),
    "/data/reset/full": _data_model("AgentRankFullResetData"),
    "/subscribe": _data_model("AgentRankSubscribeData"),
}
