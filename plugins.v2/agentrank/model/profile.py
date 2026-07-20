"""用户画像领域对象。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping


@dataclass
class UserProfile:
    """表示某个稳定 Emby 画像身份的当前推荐画像。"""

    profile_id: str
    username: str = ""
    summary: str = ""
    tags: List[str] = field(default_factory=list)
    negative_tags: List[str] = field(default_factory=list)
    playback_count: int = 0
    playback_fingerprint: str = ""
    run_id: str = ""
    generated_at: str = ""
    schema_version: int = 3

    def __post_init__(self) -> None:
        """规范化画像归属并拒绝空 profile_id。"""
        self.profile_id = str(self.profile_id or "").strip()
        self.username = str(self.username or "").strip()
        if not self.profile_id:
            raise ValueError("profile profile_id is required")

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "UserProfile":
        """从持久化字典恢复用户画像。"""
        if not isinstance(value, Mapping):
            raise ValueError("profile must be a mapping")
        profile_id = str(value.get("profile_id") or "").strip()
        if not profile_id:
            raise ValueError("profile profile_id is required")
        return cls(
            profile_id=profile_id,
            username=str(value.get("username") or "").strip(),
            summary=str(value.get("summary") or ""),
            tags=[str(item) for item in value.get("tags") or []],
            negative_tags=[str(item) for item in value.get("negative_tags") or []],
            playback_count=max(0, int(value.get("playback_count") or 0)),
            playback_fingerprint=str(value.get("playback_fingerprint") or ""),
            run_id=str(value.get("run_id") or ""),
            generated_at=str(value.get("generated_at") or ""),
            schema_version=int(value.get("schema_version") or 3),
        )
