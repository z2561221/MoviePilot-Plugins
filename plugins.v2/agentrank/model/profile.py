"""用户画像领域对象。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping


@dataclass
class UserProfile:
    """表示某个 MoviePilot 用户的当前推荐画像。"""

    username: str
    summary: str = ""
    tags: List[str] = field(default_factory=list)
    negative_tags: List[str] = field(default_factory=list)
    subscription_count: int = 0
    run_id: str = ""
    generated_at: str = ""
    schema_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "UserProfile":
        """从持久化字典恢复用户画像。"""
        if not isinstance(value, Mapping):
            raise ValueError("profile must be a mapping")
        username = str(value.get("username") or "").strip()
        if not username:
            raise ValueError("profile username is required")
        return cls(
            username=username,
            summary=str(value.get("summary") or ""),
            tags=[str(item) for item in value.get("tags") or []],
            negative_tags=[str(item) for item in value.get("negative_tags") or []],
            subscription_count=max(0, int(value.get("subscription_count") or 0)),
            run_id=str(value.get("run_id") or ""),
            generated_at=str(value.get("generated_at") or ""),
            schema_version=int(value.get("schema_version") or 1),
        )
