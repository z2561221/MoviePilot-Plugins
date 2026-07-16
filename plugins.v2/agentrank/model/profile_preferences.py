"""用户人工画像标签偏好领域对象。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping


@dataclass
class ProfilePreferences:
    """保存人工标签及对 Agent 标签的显式屏蔽规则。"""

    username: str
    custom_tags: List[str] = field(default_factory=list)
    custom_negative_tags: List[str] = field(default_factory=list)
    suppressed_tags: List[str] = field(default_factory=list)
    suppressed_negative_tags: List[str] = field(default_factory=list)
    schema_version: int = 1

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
        username = str(value.get("username") or "").strip()
        if not username:
            raise ValueError("profile preferences username is required")
        return cls(
            username=username,
            custom_tags=cls._unique(value.get("custom_tags") or []),
            custom_negative_tags=cls._unique(
                value.get("custom_negative_tags") or []
            ),
            suppressed_tags=cls._unique(value.get("suppressed_tags") or []),
            suppressed_negative_tags=cls._unique(
                value.get("suppressed_negative_tags") or []
            ),
            schema_version=int(value.get("schema_version") or 1),
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
