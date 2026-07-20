"""AgentRank 稳定 Emby 用户身份领域对象。"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping


def _clean_required(value: Any, field_name: str) -> str:
    """清理必填文本并拒绝空值。"""
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _validate_scope_component(value: str, field_name: str) -> str:
    """校验可安全进入持久化键与会话作用域的身份片段。"""
    if not all(character.isalnum() or character in "._-" for character in value):
        raise ValueError(f"{field_name} contains unsafe scope characters")
    return value


def _validate_display_name(value: str) -> str:
    """拒绝包含控制字符的 Emby 用户显示名。"""
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("username contains control characters")
    return value


@dataclass(frozen=True)
class EmbyIdentity:
    """表示由 Emby 服务器与用户 ID 共同确定的不可变画像身份。"""

    server_name: str
    user_id: str
    username: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        """规范化字段并验证稳定身份作用域。"""
        server_name = _validate_scope_component(
            _clean_required(self.server_name, "server_name"), "server_name"
        )
        user_id = _validate_scope_component(
            _clean_required(self.user_id, "user_id"), "user_id"
        )
        username = _validate_display_name(
            _clean_required(self.username, "username")
        )
        schema_version = int(self.schema_version)
        if schema_version < 1:
            raise ValueError("schema_version must be positive")
        object.__setattr__(self, "server_name", server_name)
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "username", username)
        object.__setattr__(self, "schema_version", schema_version)

    @property
    def profile_id(self) -> str:
        """返回稳定且与显示名无关的画像作用域 ID。"""
        return f"emby:{self.server_name}:{self.user_id}"

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化且不包含 Emby 凭据的身份字典。"""
        value = asdict(self)
        value["profile_id"] = self.profile_id
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EmbyIdentity":
        """从持久化字典恢复身份并校验可选 profile_id。"""
        if not isinstance(value, Mapping):
            raise ValueError("emby identity must be a mapping")
        schema_version = value.get("schema_version")
        identity = cls(
            server_name=value.get("server_name"),
            user_id=value.get("user_id"),
            username=value.get("username"),
            schema_version=1 if schema_version is None else schema_version,
        )
        stored_profile_id = str(value.get("profile_id") or "").strip()
        if stored_profile_id and stored_profile_id != identity.profile_id:
            raise ValueError("profile_id does not match Emby identity")
        return identity
