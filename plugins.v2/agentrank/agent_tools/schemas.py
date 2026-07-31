"""AgentRank 终结型提交工具的严格 Pydantic schema。"""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


CandidateId = str
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


class _StrictSubmissionModel(BaseModel):
    """拒绝额外字段、隐式类型转换和无界字符串。"""

    model_config = ConfigDict(extra="forbid", strict=True)


class ProfileBody(_StrictSubmissionModel):
    """画像主体。"""

    summary: str = Field(min_length=1, max_length=200)
    tags: List[str] = Field(default_factory=list, max_length=20)
    negative_tags: List[str] = Field(default_factory=list, max_length=20)
    playback_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_tags(self):
        """标签必须有界、非空且不重复。"""
        for field_name in ("tags", "negative_tags"):
            values = getattr(self, field_name)
            if any(not 1 <= len(item.strip()) <= 20 for item in values):
                raise ValueError(f"{field_name} items must contain 1 to 20 characters")
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} contains duplicate items")
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
    filters: ProfileFilters
    ranking_tags: List[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_ranking_tags(self):
        """自由语义标签同样必须短小且唯一。"""
        if any(not 1 <= len(item.strip()) <= 40 for item in self.ranking_tags):
            raise ValueError("ranking_tags items must contain 1 to 40 characters")
        if len(self.ranking_tags) != len(set(self.ranking_tags)):
            raise ValueError("ranking_tags contains duplicate items")
        return self


class EvidenceClaim(_StrictSubmissionModel):
    """用户证据与候选事实之间的可验证对应关系。"""

    dimension: EvidenceDimension
    user_value: str = Field(min_length=1, max_length=80)
    candidate_value: str = Field(min_length=1, max_length=80)


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
    reason: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=100)
    match_tags: List[str] = Field(min_length=1, max_length=10)
    positive_evidence: List[EvidenceClaim] = Field(min_length=2, max_length=8)
    counter_evidence: List[EvidenceClaim] = Field(default_factory=list, max_length=8)

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
