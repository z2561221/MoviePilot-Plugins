"""用户人工画像标签偏好领域对象。"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping


@dataclass
class ProfilePreferences:
    """保存人工标签及用户明确归档的标签。"""

    profile_id: str
    username: str = ""
    custom_tags: List[str] = field(default_factory=list)
    custom_negative_tags: List[str] = field(default_factory=list)
    archived_tags: List[str] = field(default_factory=list)
    archived_negative_tags: List[str] = field(default_factory=list)
    schema_version: int = 3

    def __post_init__(self) -> None:
        """规范化偏好归属并拒绝空 profile_id。"""
        self.profile_id = str(self.profile_id or "").strip()
        self.username = str(self.username or "").strip()
        if not self.profile_id:
            raise ValueError("profile preferences profile_id is required")
        self.custom_tags = self._unique(self.custom_tags)
        self.custom_negative_tags = self._unique(self.custom_negative_tags)
        self.archived_tags = self._unique(self.archived_tags)
        self.archived_negative_tags = self._unique(self.archived_negative_tags)

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
        custom_tags = cls._unique(value.get("custom_tags") or [])
        custom_negative_tags = cls._unique(
            value.get("custom_negative_tags") or []
        )
        archived_tags = cls._unique(value.get("archived_tags") or [])
        archived_negative_tags = cls._unique(
            value.get("archived_negative_tags") or []
        )
        if not archived_tags and "archived_tags" not in value:
            archived_tags = [
                tag
                for tag in cls._unique(value.get("suppressed_tags") or [])
                if tag not in custom_negative_tags
            ]
        if not archived_negative_tags and "archived_negative_tags" not in value:
            archived_negative_tags = [
                tag
                for tag in cls._unique(
                    value.get("suppressed_negative_tags") or []
                )
                if tag not in custom_tags
            ]
        return cls(
            profile_id=profile_id,
            username=str(value.get("username") or "").strip(),
            custom_tags=custom_tags,
            custom_negative_tags=custom_negative_tags,
            archived_tags=archived_tags,
            archived_negative_tags=archived_negative_tags,
            schema_version=max(3, int(value.get("schema_version") or 3)),
        )

    def fingerprint(self) -> str:
        """返回会影响画像生成的稳定偏好指纹。"""
        payload = {
            "custom_tags": self._unique(self.custom_tags),
            "custom_negative_tags": self._unique(self.custom_negative_tags),
            "archived_tags": self._unique(self.archived_tags),
            "archived_negative_tags": self._unique(self.archived_negative_tags),
        }
        raw = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def archived_entries(self) -> List[Dict[str, str]]:
        """返回保留原类别的归档标签条目。"""
        return [
            {"kind": "positive", "tag": tag}
            for tag in self._unique(self.archived_tags)
        ] + [
            {"kind": "negative", "tag": tag}
            for tag in self._unique(self.archived_negative_tags)
        ]

    def _archived_set(self) -> set[str]:
        """返回跨类别生效的归档标签集合。"""
        return set(self._unique(self.archived_tags + self.archived_negative_tags))

    def active_agent_tags(self, agent_tags: Iterable[Any]) -> List[str]:
        """过滤 Agent 标签中的归档项和人工避雷项。"""
        archived = self._archived_set()
        negative = set(self._unique(self.custom_negative_tags))
        return [
            tag
            for tag in self._unique(agent_tags)
            if tag not in archived and tag not in negative
        ]

    def active_agent_negative_tags(self, agent_tags: Iterable[Any]) -> List[str]:
        """过滤 Agent 避雷标签中的归档项和人工偏好项。"""
        archived = self._archived_set()
        positive = set(self._unique(self.custom_tags))
        return [
            tag
            for tag in self._unique(agent_tags)
            if tag not in archived and tag not in positive
        ]

    def effective_ranking_tags(self, agent_tags: Iterable[Any]) -> List[str]:
        """返回用于检索与排序的有效自由标签。"""
        archived = self._archived_set()
        negative = set(self._unique(self.custom_negative_tags))
        return self._unique(
            [
                tag
                for tag in self._unique(agent_tags)
                if tag not in archived and tag not in negative
            ]
            + self._unique(self.custom_tags)
        )

    def effective_tags(self, agent_tags: Iterable[Any]) -> List[str]:
        """返回最终可见偏好标签。"""
        return self._unique(
            self.active_agent_tags(agent_tags) + self._unique(self.custom_tags)
        )

    def effective_negative_tags(self, agent_tags: Iterable[Any]) -> List[str]:
        """返回最终可见避雷标签。"""
        return self._unique(
            self.active_agent_negative_tags(agent_tags)
            + self._unique(self.custom_negative_tags)
        )
