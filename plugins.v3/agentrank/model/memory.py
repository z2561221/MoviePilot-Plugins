"""已确认偏好记忆、墓碑谱系与版本投影模型。"""

from dataclasses import dataclass, replace
from itertools import groupby
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


PREFERENCE_MEMORY_SCHEMA_VERSION = 1
MEMORY_ITEM_STATUSES = {"active", "archived", "superseded"}
MEMORY_POLARITIES = {"positive", "negative"}


def _text(value: Any) -> str:
    """把可选标量规范为去除首尾空白的文本。"""
    return str(value or "").strip()


def _unique_texts(values: Iterable[Any]) -> Tuple[str, ...]:
    """返回保持顺序的唯一非空文本元组。"""
    result: List[str] = []
    for value in values or ():
        text = _text(value)
        if text and text not in result:
            result.append(text)
    return tuple(result)


@dataclass(frozen=True)
class PreferenceMemoryItem:
    """表示一条已由用户确认的偏好断言或删除墓碑。"""

    item_id: str
    category: str
    value: str
    polarity: str
    strength: float
    certainty: float
    evidence_refs: Tuple[str, ...]
    source_event_sequence: int
    created_at: str
    status: str = "active"
    tombstone: bool = False
    supersedes: Tuple[str, ...] = ()
    schema_version: int = PREFERENCE_MEMORY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范化确认态记忆并校验证据、状态和谱系字段。"""
        for field_name in (
            "item_id",
            "category",
            "value",
            "polarity",
            "created_at",
            "status",
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name)))
        object.__setattr__(self, "strength", float(self.strength))
        object.__setattr__(self, "certainty", float(self.certainty))
        object.__setattr__(
            self, "evidence_refs", _unique_texts(self.evidence_refs)
        )
        object.__setattr__(
            self, "supersedes", _unique_texts(self.supersedes)
        )
        object.__setattr__(
            self, "source_event_sequence", int(self.source_event_sequence)
        )
        object.__setattr__(self, "tombstone", bool(self.tombstone))
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not self.item_id or not self.category or not self.value:
            raise ValueError("preference memory item identity is incomplete")
        if self.polarity not in MEMORY_POLARITIES:
            raise ValueError("preference memory item polarity is invalid")
        if not 0 <= self.strength <= 1 or not 0 <= self.certainty <= 1:
            raise ValueError("preference memory item strength or certainty is invalid")
        if not self.evidence_refs:
            raise ValueError("preference memory item requires confirmed evidence")
        if self.source_event_sequence <= 0:
            raise ValueError("preference memory item source sequence must be positive")
        if not self.created_at:
            raise ValueError("preference memory item created_at is required")
        if self.status not in MEMORY_ITEM_STATUSES:
            raise ValueError("preference memory item status is invalid")
        if self.tombstone and self.status == "active":
            raise ValueError("preference memory tombstone cannot be active")
        if not self.tombstone and self.status == "archived":
            raise ValueError("active preference memory item cannot be archived")
        if self.item_id in self.supersedes:
            raise ValueError("preference memory item cannot supersede itself")
        if self.schema_version != PREFERENCE_MEMORY_SCHEMA_VERSION:
            raise ValueError("preference memory item schema_version is unsupported")

    @property
    def preference_key(self) -> str:
        """返回忽略大小写的类别和值谱系键。"""
        return f"{self.category.casefold()}:{self.value.casefold()}"

    def as_current(self) -> "PreferenceMemoryItem":
        """返回作为当前断言或当前墓碑时应有的状态。"""
        return replace(self, status="archived" if self.tombstone else "active")

    def as_superseded(self) -> "PreferenceMemoryItem":
        """返回保留原内容但标记已被替代的历史版本。"""
        return self if self.status == "superseded" else replace(self, status="superseded")

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化确认态记忆项。"""
        return {
            "item_id": self.item_id,
            "category": self.category,
            "value": self.value,
            "polarity": self.polarity,
            "strength": self.strength,
            "certainty": self.certainty,
            "evidence_refs": list(self.evidence_refs),
            "source_event_sequence": self.source_event_sequence,
            "created_at": self.created_at,
            "status": self.status,
            "tombstone": self.tombstone,
            "supersedes": list(self.supersedes),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PreferenceMemoryItem":
        """从持久化字典恢复确认态记忆项。"""
        if not isinstance(value, Mapping):
            raise ValueError("preference memory item must be a mapping")
        return cls(
            item_id=value.get("item_id"),
            category=value.get("category"),
            value=value.get("value"),
            polarity=value.get("polarity"),
            strength=value.get("strength") or 0,
            certainty=value.get("certainty") or 0,
            evidence_refs=tuple(value.get("evidence_refs") or ()),
            source_event_sequence=value.get("source_event_sequence") or 0,
            created_at=value.get("created_at"),
            status=value.get("status") or "active",
            tombstone=value.get("tombstone") or False,
            supersedes=tuple(value.get("supersedes") or ()),
            schema_version=value.get("schema_version") or 0,
        )


@dataclass(frozen=True)
class PreferenceMemory:
    """保存一个 profile 的全部确认态偏好版本与单调 revision。"""

    profile_id: str
    memory_revision: int = 0
    last_event_sequence: int = 0
    items: Tuple[PreferenceMemoryItem, ...] = ()
    schema_version: int = PREFERENCE_MEMORY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """校验记忆历史顺序、版本计数、谱系引用和当前唯一性。"""
        object.__setattr__(self, "profile_id", _text(self.profile_id))
        object.__setattr__(self, "memory_revision", int(self.memory_revision))
        object.__setattr__(self, "last_event_sequence", int(self.last_event_sequence))
        object.__setattr__(self, "items", tuple(self.items or ()))
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not self.profile_id:
            raise ValueError("preference memory profile_id is required")
        if self.memory_revision < 0 or self.last_event_sequence < 0:
            raise ValueError("preference memory revision is invalid")
        if self.schema_version != PREFERENCE_MEMORY_SCHEMA_VERSION:
            raise ValueError("preference memory schema_version is unsupported")
        if not self.items:
            if self.memory_revision != 0 or self.last_event_sequence != 0:
                raise ValueError("empty preference memory must use revision zero")
            return

        seen_by_id: Dict[str, PreferenceMemoryItem] = {}
        current_keys = set()
        sequences: List[int] = []
        previous_sequence = 0
        for item in self.items:
            if not isinstance(item, PreferenceMemoryItem):
                raise ValueError("preference memory contains an invalid item")
            if item.item_id in seen_by_id:
                raise ValueError("preference memory contains duplicate item ids")
            if item.source_event_sequence < previous_sequence:
                raise ValueError("preference memory items are not sequence ordered")
            if any(parent not in seen_by_id for parent in item.supersedes):
                raise ValueError("preference memory supersedes an unknown item")
            if any(
                seen_by_id[parent].preference_key != item.preference_key
                for parent in item.supersedes
            ):
                raise ValueError("preference memory contains a cross-preference lineage")
            seen_by_id[item.item_id] = item
            sequences.append(item.source_event_sequence)
            previous_sequence = item.source_event_sequence
            if item.status != "superseded":
                if item.preference_key in current_keys:
                    raise ValueError("preference memory has multiple current items")
                current_keys.add(item.preference_key)
        if self.last_event_sequence != max(sequences):
            raise ValueError("preference memory last_event_sequence is inconsistent")
        if self.memory_revision != len(set(sequences)):
            raise ValueError("preference memory revision count is inconsistent")

    @classmethod
    def empty(cls, profile_id: str) -> "PreferenceMemory":
        """创建一个尚无确认偏好的 profile 记忆。"""
        return cls(profile_id=profile_id)

    def latest_item(self, category: str, value: str) -> Optional[PreferenceMemoryItem]:
        """读取指定谱系当前未被替代的断言或墓碑。"""
        key = f"{_text(category).casefold()}:{_text(value).casefold()}"
        for item in reversed(self.items):
            if item.preference_key == key and item.status != "superseded":
                return item
        return None

    def active_items(self) -> Tuple[PreferenceMemoryItem, ...]:
        """返回当前有效且不是墓碑的已确认偏好。"""
        return tuple(
            item
            for item in self.items
            if item.status == "active" and not item.tombstone
        )

    def is_tombstoned(self, category: str, value: str) -> bool:
        """返回指定偏好谱系当前是否由删除墓碑占位。"""
        latest = self.latest_item(category, value)
        return bool(latest and latest.tombstone and latest.status == "archived")

    def project(
        self,
        items: Iterable[PreferenceMemoryItem],
        *,
        expected_revision: int,
        source_event_sequence: int,
    ) -> "MemoryProjectionResult":
        """以 CAS 和事件序号投影一批同事件确认项。"""
        expected = int(expected_revision)
        sequence = int(source_event_sequence)
        if expected != self.memory_revision:
            return MemoryProjectionResult.superseded(
                self,
                sequence,
                expected,
                "memory_revision_conflict",
            )
        if sequence <= self.last_event_sequence:
            return MemoryProjectionResult.superseded(
                self,
                sequence,
                expected,
                "stale_event_sequence",
            )
        proposed = tuple(item.as_current() for item in items or ())
        if not proposed:
            raise ValueError("memory projection requires at least one item")
        if any(item.source_event_sequence != sequence for item in proposed):
            raise ValueError("memory projection item sequence mismatch")
        if len({item.item_id for item in proposed}) != len(proposed):
            raise ValueError("memory projection contains duplicate item ids")
        if len({item.preference_key for item in proposed}) != len(proposed):
            raise ValueError("memory projection contains duplicate preference keys")

        working = list(self.items)
        known_by_id = {item.item_id: item for item in working}
        for proposed_item in proposed:
            if proposed_item.item_id in known_by_id:
                return MemoryProjectionResult.superseded(
                    self,
                    sequence,
                    expected,
                    "duplicate_memory_item",
                )
            latest = next(
                (
                    item
                    for item in reversed(working)
                    if item.preference_key == proposed_item.preference_key
                    and item.status != "superseded"
                ),
                None,
            )
            superseded_ids = set(proposed_item.supersedes)
            if any(parent not in known_by_id for parent in superseded_ids):
                return MemoryProjectionResult.superseded(
                    self,
                    sequence,
                    expected,
                    "unknown_supersedes_target",
                )
            if any(
                known_by_id[parent].preference_key != proposed_item.preference_key
                for parent in superseded_ids
            ):
                return MemoryProjectionResult.superseded(
                    self,
                    sequence,
                    expected,
                    "cross_preference_supersedes",
                )
            if latest is not None and latest.item_id not in superseded_ids:
                return MemoryProjectionResult.superseded(
                    self,
                    sequence,
                    expected,
                    "missing_latest_supersedes",
                )
            if latest is None and superseded_ids:
                return MemoryProjectionResult.superseded(
                    self,
                    sequence,
                    expected,
                    "missing_current_preference",
                )
            if latest is not None:
                working = [
                    item.as_superseded() if item.item_id == latest.item_id else item
                    for item in working
                ]
            working.append(proposed_item)
            known_by_id[proposed_item.item_id] = proposed_item

        memory = PreferenceMemory(
            profile_id=self.profile_id,
            memory_revision=self.memory_revision + 1,
            last_event_sequence=sequence,
            items=tuple(working),
        )
        return MemoryProjectionResult(
            memory=memory,
            applied=True,
            status="applied",
            reason="",
            source_event_sequence=sequence,
            expected_revision=expected,
            actual_revision=memory.memory_revision,
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化偏好记忆。"""
        return {
            "profile_id": self.profile_id,
            "memory_revision": self.memory_revision,
            "last_event_sequence": self.last_event_sequence,
            "items": [item.to_dict() for item in self.items],
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PreferenceMemory":
        """从持久化字典恢复偏好记忆。"""
        if not isinstance(value, Mapping):
            raise ValueError("preference memory must be a mapping")
        return cls(
            profile_id=value.get("profile_id"),
            memory_revision=value.get("memory_revision") or 0,
            last_event_sequence=value.get("last_event_sequence") or 0,
            items=tuple(
                PreferenceMemoryItem.from_dict(item)
                for item in value.get("items") or []
            ),
            schema_version=value.get("schema_version") or 0,
        )

    @classmethod
    def replay(
        cls,
        profile_id: str,
        items: Iterable[PreferenceMemoryItem],
    ) -> "PreferenceMemory":
        """严格按 source_event_sequence 重放完整确认态记忆历史。"""
        ordered = sorted(
            tuple(items or ()),
            key=lambda item: item.source_event_sequence,
        )
        memory = cls.empty(profile_id)
        for sequence, grouped in groupby(
            ordered, key=lambda item: item.source_event_sequence
        ):
            result = memory.project(
                tuple(grouped),
                expected_revision=memory.memory_revision,
                source_event_sequence=sequence,
            )
            if not result.applied:
                raise ValueError(f"preference memory replay failed: {result.reason}")
            memory = result.memory
        return memory


@dataclass(frozen=True)
class MemoryProjectionResult:
    """描述一次记忆投影是否应用或因乱序被标记为 superseded。"""

    memory: PreferenceMemory
    applied: bool
    status: str
    reason: str
    source_event_sequence: int
    expected_revision: int
    actual_revision: int

    def __post_init__(self) -> None:
        """校验投影结果状态与实际 revision 一致。"""
        if not isinstance(self.memory, PreferenceMemory):
            raise ValueError("memory projection result requires PreferenceMemory")
        object.__setattr__(self, "applied", bool(self.applied))
        object.__setattr__(self, "status", _text(self.status))
        object.__setattr__(self, "reason", _text(self.reason))
        object.__setattr__(
            self, "source_event_sequence", int(self.source_event_sequence)
        )
        object.__setattr__(self, "expected_revision", int(self.expected_revision))
        object.__setattr__(self, "actual_revision", int(self.actual_revision))
        if self.status not in {"applied", "superseded"}:
            raise ValueError("memory projection result status is invalid")
        if self.source_event_sequence <= 0:
            raise ValueError("memory projection result source sequence is invalid")
        if self.expected_revision < 0 or self.actual_revision < 0:
            raise ValueError("memory projection result revision is invalid")
        if self.applied != (self.status == "applied"):
            raise ValueError("memory projection result applied flag is inconsistent")
        if self.status == "superseded" and not self.reason:
            raise ValueError("superseded memory projection requires a reason")
        if self.status == "applied" and self.reason:
            raise ValueError("applied memory projection cannot contain a reason")
        if self.actual_revision != self.memory.memory_revision:
            raise ValueError("memory projection result revision is inconsistent")

    @classmethod
    def superseded(
        cls,
        memory: PreferenceMemory,
        source_event_sequence: int,
        expected_revision: int,
        reason: str,
    ) -> "MemoryProjectionResult":
        """创建不改变当前记忆的过期或冲突结果。"""
        return cls(
            memory=memory,
            applied=False,
            status="superseded",
            reason=reason,
            source_event_sequence=source_event_sequence,
            expected_revision=expected_revision,
            actual_revision=memory.memory_revision,
        )
