"""推荐运行历史领域对象。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping


@dataclass
class RecommendationRun:
    """表示一次按用户隔离的榜单生成运行。"""

    username: str
    run_id: str
    status: str = "idle"
    started_at: str = ""
    finished_at: str = ""
    message: str = ""
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RecommendationRun":
        """从持久化字典恢复运行记录。"""
        if not isinstance(value, Mapping):
            raise ValueError("run must be a mapping")
        username = str(value.get("username") or "").strip()
        run_id = str(value.get("run_id") or "").strip()
        if not username or not run_id:
            raise ValueError("run username and run_id are required")
        return cls(
            username=username,
            run_id=run_id,
            status=str(value.get("status") or "idle"),
            started_at=str(value.get("started_at") or ""),
            finished_at=str(value.get("finished_at") or ""),
            message=str(value.get("message") or ""),
            errors=[str(item) for item in value.get("errors") or []],
            metrics=dict(value.get("metrics") or {}),
            schema_version=int(value.get("schema_version") or 1),
        )
