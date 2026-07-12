"""忽略归档与恢复领域对象。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping


@dataclass
class ArchiveEntry:
    """表示用户忽略的一条推荐及其原排名。"""

    candidate_id: str
    original_rank: int
    archived_at: str = ""
    reason: str = "ignored"
    recommendation: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ArchiveEntry":
        """从持久化字典恢复归档条目。"""
        if not isinstance(value, Mapping):
            raise ValueError("archive entry must be a mapping")
        candidate_id = str(value.get("candidate_id") or "").strip()
        if not candidate_id:
            raise ValueError("archive candidate_id is required")
        return cls(
            candidate_id=candidate_id,
            original_rank=max(1, int(value.get("original_rank") or 1)),
            archived_at=str(value.get("archived_at") or ""),
            reason=str(value.get("reason") or "ignored"),
            recommendation=dict(value.get("recommendation") or {}),
        )


@dataclass
class ArchiveFeedback:
    """表示按用户名隔离的完整归档反馈。"""

    username: str
    entries: List[ArchiveEntry] = field(default_factory=list)
    schema_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ArchiveFeedback":
        """从持久化字典恢复归档反馈。"""
        if not isinstance(value, Mapping):
            raise ValueError("archive must be a mapping")
        username = str(value.get("username") or "").strip()
        if not username:
            raise ValueError("archive username is required")
        return cls(
            username=username,
            entries=[ArchiveEntry.from_dict(item) for item in value.get("entries") or []],
            schema_version=int(value.get("schema_version") or 1),
        )
