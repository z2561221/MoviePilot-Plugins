"""推荐运行历史领域对象。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping


@dataclass
class RecommendationRun:
    """表示一次按稳定 Emby 画像身份隔离的榜单生成运行。"""

    profile_id: str
    run_id: str
    username: str = ""
    status: str = "idle"
    started_at: str = ""
    finished_at: str = ""
    message: str = ""
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = 2

    def __post_init__(self) -> None:
        """规范化运行归属并拒绝空 profile_id。"""
        self.profile_id = str(self.profile_id or "").strip()
        self.username = str(self.username or "").strip()
        if not self.profile_id:
            raise ValueError("run profile_id is required")

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RecommendationRun":
        """从持久化字典恢复运行记录。"""
        if not isinstance(value, Mapping):
            raise ValueError("run must be a mapping")
        profile_id = str(value.get("profile_id") or "").strip()
        run_id = str(value.get("run_id") or "").strip()
        if not profile_id or not run_id:
            raise ValueError("run profile_id and run_id are required")
        return cls(
            profile_id=profile_id,
            run_id=run_id,
            username=str(value.get("username") or "").strip(),
            status=str(value.get("status") or "idle"),
            started_at=str(value.get("started_at") or ""),
            finished_at=str(value.get("finished_at") or ""),
            message=str(value.get("message") or ""),
            errors=[str(item) for item in value.get("errors") or []],
            metrics=dict(value.get("metrics") or {}),
            schema_version=int(value.get("schema_version") or 2),
        )
