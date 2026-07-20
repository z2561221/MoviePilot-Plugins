"""人工画像标签校验与更新服务。"""

import re
from dataclasses import dataclass

from ..model.profile_preferences import ProfilePreferences
from ..storage.repository import AgentRankRepository


TAG_PATTERN = re.compile(r"^[^\x00-\x1f\x7f]{1,20}$")


@dataclass
class ProfilePreferenceActionResult:
    """表示一次人工标签变更结果。"""

    changed: bool
    action: str
    kind: str
    tag: str
    preferences: ProfilePreferences


class ProfilePreferenceService:
    """维护人工标签与 Agent 标签屏蔽规则。"""

    max_tags_per_kind = 20

    def __init__(self, repository: AgentRankRepository):
        """绑定 AgentRank 持久化仓库。"""
        self._repository = repository

    @staticmethod
    def _tag(value: object) -> str:
        """规范化并校验单个标签。"""
        tag = str(value or "").strip()
        if not TAG_PATTERN.fullmatch(tag):
            raise ValueError("标签长度必须为一至二十字且不能包含换行或控制字符")
        return tag

    @staticmethod
    def _fields(kind: str) -> tuple[str, str, str, str]:
        """返回目标类别及相反类别的人工和屏蔽字段名。"""
        if kind == "positive":
            return (
                "custom_tags",
                "suppressed_tags",
                "custom_negative_tags",
                "suppressed_negative_tags",
            )
        if kind == "negative":
            return (
                "custom_negative_tags",
                "suppressed_negative_tags",
                "custom_tags",
                "suppressed_tags",
            )
        raise ValueError("标签类别必须是 positive 或 negative")

    def update(
        self, profile_id: str, kind: str, action: str, raw_tag: object
    ) -> ProfilePreferenceActionResult:
        """添加或删除人工标签，并持久化稳定覆盖规则。"""
        tag = self._tag(raw_tag)
        custom_field, suppressed_field, opposite_custom, opposite_suppressed = (
            self._fields(str(kind or "").strip())
        )
        if action not in {"add", "remove"}:
            raise ValueError("标签操作必须是 add 或 remove")
        preferences = self._repository.load_profile_preferences(profile_id)
        before = preferences.to_dict()
        custom = getattr(preferences, custom_field)
        suppressed = getattr(preferences, suppressed_field)
        opposite = getattr(preferences, opposite_custom)
        opposite_hidden = getattr(preferences, opposite_suppressed)
        if action == "add":
            if tag not in custom and len(custom) >= self.max_tags_per_kind:
                raise ValueError("每类人工标签最多二十个")
            if tag not in custom:
                custom.append(tag)
            if tag in suppressed:
                suppressed.remove(tag)
            if tag in opposite:
                opposite.remove(tag)
            if tag not in opposite_hidden:
                opposite_hidden.append(tag)
        else:
            if tag in custom:
                custom.remove(tag)
            if tag not in suppressed:
                suppressed.append(tag)
        changed = before != preferences.to_dict()
        if changed:
            self._repository.save_profile_preferences(preferences)
        return ProfilePreferenceActionResult(
            changed=changed,
            action=action,
            kind=kind,
            tag=tag,
            preferences=preferences,
        )
