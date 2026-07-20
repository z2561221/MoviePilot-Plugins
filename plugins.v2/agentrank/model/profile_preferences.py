"""用户人工画像标签偏好领域对象。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping


@dataclass
class ProfilePreferences:
    """保存人工标签及对 Agent 标签的显式屏蔽规则。"""

    profile_id: str
    username: str = ""
    custom_tags: List[str] = field(default_factory=list)
    custom_negative_tags: List[str] = field(default_factory=list)
    suppressed_tags: List[str] = field(default_factory=list)
    suppressed_negative_tags: List[str] = field(default_factory=list)
    schema_version: int = 2

    def __post_init__(self) -> None:
        """规范化偏好归属并拒绝空 profile_id。"""
        self.profile_id = str(self.profile_id or "").strip()
        self.username = str(self.username or "").strip()
        if not self.profile_id:
            raise ValueError("profile preferences profile_id is required")

    @staticmethod
    def _unique(values: Iterable[Any]) -> List[str]:
        """返回保持原顺序的唯一非空标签。"""
        result: List[str] = []
        for value in values or []:
            text = str(value or "").strip()
            if text and text not in result:
                result.append(text)
        return result

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProfilePreferences":
        """从持久化字典恢复人工偏好。"""
        if not isinstance(value, Mapping):
            raise ValueError("profile preferences must be a mapping")
        profile_id = str(value.get("profile_id") or "").strip()
        if not profile_id:
            raise ValueError("profile preferences profile_id is required")
        return cls(
            profile_id=profile_id,
            username=str(value.get("username") or "").strip(),
            custom_tags=cls._unique(value.get("custom_tags") or []),
            custom_negative_tags=cls._unique(
                value.get("custom_negative_tags") or []
            ),
            suppressed_tags=cls._unique(value.get("suppressed_tags") or []),
            suppressed_negative_tags=cls._unique(
                value.get("suppressed_negative_tags") or []
            ),
            schema_version=int(value.get("schema_version") or 2),
        )

    @staticmethod
    def _effective(
        agent_tags: Iterable[Any], custom_tags: Iterable[Any], suppressed_tags: Iterable[Any]
    ) -> List[str]:
        """合并 Agent 标签与人工标签，并应用删除屏蔽。"""
        suppressed = set(ProfilePreferences._unique(suppressed_tags))
        return ProfilePreferences._unique(
            [tag for tag in ProfilePreferences._unique(agent_tags) if tag not in suppressed]
            + ProfilePreferences._unique(custom_tags)
        )

    def effective_tags(self, agent_tags: Iterable[Any]) -> List[str]:
        """返回最终可见偏好标签。"""
        return self._effective(agent_tags, self.custom_tags, self.suppressed_tags)

    def effective_negative_tags(self, agent_tags: Iterable[Any]) -> List[str]:
        """返回最终可见避雷标签。"""
        return self._effective(
            agent_tags,
            self.custom_negative_tags,
            self.suppressed_negative_tags,
        )
