"""统一待确认中心的安全展示与通知模型。"""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple


PENDING_ITEM_TYPES = frozenset({"proposal", "question", "command"})


def _text(value: Any, limit: int) -> str:
    """把任意标量规范为有界单行文本。"""
    return " ".join(str(value or "").split()).strip()[: max(1, int(limit))]


@dataclass(frozen=True)
class PendingCenterItem:
    """表示待确认中心可展示且不含内部身份的统一项目。"""

    item_type: str
    item_id: str
    profile_id: str
    title: str
    summary: str
    created_at: str
    status: str
    candidate_id: str = ""
    expires_at: str = ""
    detail_lines: Tuple[str, ...] = ()
    options: Tuple[Mapping[str, str], ...] = ()
    allow_custom_answer: bool = False
    requires_superuser: bool = False
    selected_option_id: str = ""
    answer_text: str = ""
    resolved_at: str = ""
    result_code: str = ""
    result_message: str = ""
    editable: bool = False
    reversible: bool = False

    def __post_init__(self) -> None:
        """规范化安全展示字段并拒绝未知项目类型。"""
        for field_name, limit in (
            ("item_type", 24),
            ("item_id", 160),
            ("profile_id", 240),
            ("title", 80),
            ("summary", 240),
            ("created_at", 64),
            ("status", 32),
            ("candidate_id", 160),
            ("expires_at", 64),
            ("selected_option_id", 64),
            ("answer_text", 1000),
            ("resolved_at", 64),
            ("result_code", 64),
            ("result_message", 240),
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), limit))
        object.__setattr__(
            self,
            "detail_lines",
            tuple(
                dict.fromkeys(
                    _text(item, 240)
                    for item in self.detail_lines or ()
                    if _text(item, 240)
                )
            )[:8],
        )
        normalized_options = []
        for value in self.options or ():
            raw = dict(value) if isinstance(value, Mapping) else {}
            option_id = _text(raw.get("option_id"), 64)
            label = _text(raw.get("label"), 120)
            if option_id and label:
                normalized_options.append({"option_id": option_id, "label": label})
            if len(normalized_options) >= 5:
                break
        object.__setattr__(self, "options", tuple(normalized_options))
        object.__setattr__(self, "allow_custom_answer", bool(self.allow_custom_answer))
        object.__setattr__(self, "requires_superuser", bool(self.requires_superuser))
        object.__setattr__(self, "editable", bool(self.editable))
        object.__setattr__(self, "reversible", bool(self.reversible))
        if self.item_type not in PENDING_ITEM_TYPES:
            raise ValueError("pending center item_type is invalid")
        if not all((self.item_id, self.profile_id, self.title, self.summary, self.created_at)):
            raise ValueError("pending center item identity is incomplete")

    def to_dict(self) -> Dict[str, Any]:
        """返回前端与通知层可安全消费的字段。"""
        return {
            "item_type": self.item_type,
            "item_id": self.item_id,
            "profile_id": self.profile_id,
            "title": self.title,
            "summary": self.summary,
            "created_at": self.created_at,
            "status": self.status,
            "candidate_id": self.candidate_id,
            "expires_at": self.expires_at,
            "detail_lines": list(self.detail_lines),
            "options": [dict(item) for item in self.options],
            "allow_custom_answer": self.allow_custom_answer,
            "requires_superuser": self.requires_superuser,
            "selected_option_id": self.selected_option_id,
            "answer_text": self.answer_text,
            "resolved_at": self.resolved_at,
            "result_code": self.result_code,
            "result_message": self.result_message,
            "editable": self.editable,
            "reversible": self.reversible,
        }


@dataclass(frozen=True)
class PendingNotice:
    """表示通知层可发送的安全项目及仅供回调审计的操作身份。"""

    item: PendingCenterItem
    actor_id: str = ""

    def __post_init__(self) -> None:
        """限制内部操作身份长度且不把它并入公开项目。"""
        if not isinstance(self.item, PendingCenterItem):
            raise TypeError("pending notice item must be PendingCenterItem")
        object.__setattr__(self, "actor_id", _text(self.actor_id, 128))

    def to_public_dict(self) -> Dict[str, Any]:
        """返回不含操作身份的通知预览。"""
        return self.item.to_dict()
