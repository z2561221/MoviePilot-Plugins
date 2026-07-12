"""推荐榜单领域对象。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass
class RecommendationItem:
    """表示榜单中的一条安全推荐。"""

    candidate_id: str
    rank: int
    summary: str = ""
    confidence: float = 0.0
    title: str = ""
    media_type: str = "unknown"
    source_ids: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RecommendationItem":
        """从持久化字典恢复推荐条目。"""
        if not isinstance(value, Mapping):
            raise ValueError("recommendation item must be a mapping")
        candidate_id = str(value.get("candidate_id") or "").strip()
        if not candidate_id:
            raise ValueError("recommendation candidate_id is required")
        return cls(
            candidate_id=candidate_id,
            rank=max(1, int(value.get("rank") or 1)),
            summary=str(value.get("summary") or ""),
            confidence=float(value.get("confidence") or 0.0),
            title=str(value.get("title") or ""),
            media_type=str(value.get("media_type") or "unknown"),
            source_ids=dict(value.get("source_ids") or {}),
        )


@dataclass
class RecommendationBoard:
    """表示某个用户当前可见的推荐榜单。"""

    username: str
    run_id: str
    status: str = "idle"
    recommendations: List[RecommendationItem] = field(default_factory=list)
    generated_at: str = ""
    message: str = ""
    previous_run_id: Optional[str] = None
    schema_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RecommendationBoard":
        """从持久化字典恢复榜单。"""
        if not isinstance(value, Mapping):
            raise ValueError("board must be a mapping")
        username = str(value.get("username") or "").strip()
        if not username:
            raise ValueError("board username is required")
        return cls(
            username=username,
            run_id=str(value.get("run_id") or ""),
            status=str(value.get("status") or "idle"),
            recommendations=[
                RecommendationItem.from_dict(item)
                for item in value.get("recommendations") or []
            ],
            generated_at=str(value.get("generated_at") or ""),
            message=str(value.get("message") or ""),
            previous_run_id=(
                str(value.get("previous_run_id"))
                if value.get("previous_run_id") is not None
                else None
            ),
            schema_version=int(value.get("schema_version") or 1),
        )
