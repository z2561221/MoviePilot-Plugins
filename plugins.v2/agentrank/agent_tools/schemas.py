"""AgentRank 终结型提交工具的严格 Pydantic schema。"""

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


CandidateId = str
EXPLICIT_NEGATIVE_SUMMARY_PATTERN = re.compile(
    r"(?<!不)(?:明确|已)?(?:排除|避雷)|(?:明确|已)?(?:不喜欢|拒绝|不看|不想看|不考虑)"
)
EvidenceDimension = Literal[
    "type",
    "theme",
    "actor",
    "director",
    "region",
    "year",
    "rating",
    "heat",
    "freshness",
    "similarity",
]
RetrievalTool = Literal["douban", "tmdb_movies", "tmdb_tv", "bangumi", "anilist"]
RetrievalPurpose = Literal[
    "related", "trend", "new_release", "adjacent", "directed_search"
]


class _StrictSubmissionModel(BaseModel):
    """拒绝额外字段、隐式类型转换和无界字符串。"""

    model_config = ConfigDict(extra="forbid", strict=True)


class ProfileBody(_StrictSubmissionModel):
    """画像主体。"""

    summary: str = Field(min_length=1, max_length=200)
    tags: List[str] = Field(default_factory=list, max_length=20)
    negative_tags: List[str] = Field(default_factory=list, max_length=20)
    playback_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_tags(self):
        """标签必须有界、非空且不重复。"""
        for field_name in ("tags", "negative_tags"):
            values = getattr(self, field_name)
            if any(not 1 <= len(item.strip()) <= 20 for item in values):
                raise ValueError(f"{field_name} items must contain 1 to 20 characters")
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} contains duplicate items")
        if (
            EXPLICIT_NEGATIVE_SUMMARY_PATTERN.search(self.summary)
            and not self.negative_tags
        ):
            raise ValueError(
                "profile.summary contains an explicit negative preference without negative_tags"
            )
        return self


class ProfileFilters(_StrictSubmissionModel):
    """画像生成的受控检索条件。"""

    media_types: List[Literal["movie", "tv", "anime"]] = Field(
        default_factory=list, max_length=3
    )
    genre_ids: List[int] = Field(default_factory=list, max_length=20)
    keyword_ids: List[int] = Field(default_factory=list, max_length=20)
    original_languages: List[str] = Field(default_factory=list, max_length=10)
    year_min: Optional[int] = Field(default=None, ge=1870, le=2100)
    year_max: Optional[int] = Field(default=None, ge=1870, le=2100)
    rating_min: Optional[float] = Field(default=None, ge=0, le=10)
    vote_count_min: Optional[int] = Field(
        default=None, ge=0, le=2_000_000_000
    )
    sort_by: Literal[
        "popularity.desc",
        "vote_average.desc",
        "vote_count.desc",
        "release_date.desc",
    ] = "popularity.desc"

    @model_validator(mode="after")
    def validate_filters(self):
        """拒绝重复枚举、重复 ID 和反向年份范围。"""
        for field_name in (
            "media_types",
            "genre_ids",
            "keyword_ids",
            "original_languages",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} contains duplicate items")
        if any(item <= 0 for item in (*self.genre_ids, *self.keyword_ids)):
            raise ValueError("genre_ids and keyword_ids must be positive")
        if any(
            len(item) != 2 or not item.isalpha() or not item.islower()
            for item in self.original_languages
        ):
            raise ValueError("original_languages must contain ISO-like lowercase codes")
        if (
            self.year_min is not None
            and self.year_max is not None
            and self.year_min > self.year_max
        ):
            raise ValueError("year_min must not exceed year_max")
        return self


class SubmitProfileResultInput(_StrictSubmissionModel):
    """画像角色唯一允许提交的结果。"""

    profile: ProfileBody


class RetrievalActionInput(_StrictSubmissionModel):
    """一项由宿主执行的受控媒体检索动作。"""

    tool: RetrievalTool
    purpose: RetrievalPurpose


class SubmitRetrievalPlanInput(_StrictSubmissionModel):
    """检索策划角色唯一允许提交的单轮计划。"""

    goal: str = Field(min_length=1, max_length=200)
    actions: List[RetrievalActionInput] = Field(min_length=1, max_length=5)
    filters: ProfileFilters
    ranking_tags: List[str] = Field(default_factory=list, max_length=20)
    hard_constraints: List[str] = Field(default_factory=list, max_length=10)
    soft_signals: List[str] = Field(default_factory=list, max_length=20)
    relaxation_order: List[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_plan_text(self):
        """计划文本必须短小唯一，工具动作也不得重复。"""
        for field_name, item_limit in (
            ("ranking_tags", 40),
            ("hard_constraints", 80),
            ("soft_signals", 80),
            ("relaxation_order", 80),
        ):
            values = getattr(self, field_name)
            if any(not 1 <= len(item.strip()) <= item_limit for item in values):
                raise ValueError(f"{field_name} items are invalid")
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} contains duplicate items")
        action_keys = [(item.tool, item.purpose) for item in self.actions]
        if len(action_keys) != len(set(action_keys)):
            raise ValueError("actions contains duplicate items")
        return self


class EvidenceClaim(_StrictSubmissionModel):
    """用户证据与候选事实之间的可验证对应关系。"""

    dimension: EvidenceDimension
    user_value: str = Field(min_length=1, max_length=80)
    candidate_value: str = Field(min_length=1, max_length=80)


class EvidenceReference(_StrictSubmissionModel):
    """引用决赛上下文中已验证的证据选项。"""

    evidence_ref: str = Field(
        min_length=2,
        max_length=4,
        pattern=r"^[pc][1-8]$",
    )


EvidenceSelection = EvidenceClaim | EvidenceReference


class BatchJudgment(_StrictSubmissionModel):
    """一条初赛判断卡。"""

    candidate_id: CandidateId = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9:_-]+$"
    )
    fit_score: int = Field(ge=0, le=100)
    positive_evidence: List[EvidenceClaim] = Field(min_length=2, max_length=2)
    counter_evidence: Optional[EvidenceClaim] = None
    advance: bool


class SubmitBatchResultInput(_StrictSubmissionModel):
    """初赛角色唯一允许提交的整批结果。"""

    judgments: List[BatchJudgment] = Field(min_length=1, max_length=5)


class FinalRecommendation(_StrictSubmissionModel):
    """决赛榜单中的一条完整推荐。"""

    candidate_id: CandidateId = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9:_-]+$"
    )
    fit_score: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1, max_length=30)
    summary: str = Field(min_length=1, max_length=30)
    match_tags: List[str] = Field(min_length=1, max_length=10)
    positive_evidence: List[EvidenceSelection] = Field(default_factory=list, max_length=8)
    counter_evidence: List[EvidenceSelection] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_match_tags(self):
        """匹配标签必须短小且唯一。"""
        if any(not 1 <= len(item.strip()) <= 20 for item in self.match_tags):
            raise ValueError("match_tags items must contain 1 to 20 characters")
        if len(self.match_tags) != len(set(self.match_tags)):
            raise ValueError("match_tags contains duplicate items")
        return self


class SubmitFinalBoardInput(_StrictSubmissionModel):
    """决赛角色唯一允许提交的 Top 5。"""

    recommendations: List[FinalRecommendation] = Field(min_length=1, max_length=5)
