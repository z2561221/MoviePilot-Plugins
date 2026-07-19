"""AgentRank 播放画像领域对象。"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping


@dataclass
class PlaybackSample:
    """表示一条已映射到媒体身份的用户播放证据。"""

    stable_id: str
    title: str
    media_type: str
    tmdb_id: str = ""
    completed: bool = False
    play_count: int = 0
    watch_minutes: int = 0
    last_played_at: str = ""
    abandoned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """返回不含设备、地址和凭据的 Agent 安全字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PlaybackSample":
        """从快照字典恢复播放证据。"""
        if not isinstance(value, Mapping):
            raise ValueError("playback sample must be a mapping")
        stable_id = str(value.get("stable_id") or "").strip()
        title = str(value.get("title") or "").strip()
        if not stable_id or not title:
            raise ValueError("playback sample requires stable_id and title")
        return cls(
            stable_id=stable_id,
            title=title,
            media_type=str(value.get("media_type") or "unknown"),
            tmdb_id=str(value.get("tmdb_id") or ""),
            completed=bool(value.get("completed", False)),
            play_count=max(0, int(value.get("play_count") or 0)),
            watch_minutes=max(0, int(value.get("watch_minutes") or 0)),
            last_played_at=str(value.get("last_played_at") or ""),
            abandoned=bool(value.get("abandoned", False)),
        )


@dataclass
class PlaybackSnapshot:
    """表示一次按用户隔离的播放画像采集结果。"""

    username: str
    source: str = "subscription"
    confidence: str = "low"
    status: str = "fallback"
    samples: List[PlaybackSample] = field(default_factory=list)
    mapped_count: int = 0
    unmapped_count: int = 0
    synced_at: str = ""
    message: str = ""
    fallback_from: List[str] = field(default_factory=list)
    schema_version: int = 1

    def __post_init__(self) -> None:
        """为新采集结果补充稳定时间和映射计数。"""
        if not self.synced_at:
            self.synced_at = datetime.now(timezone.utc).isoformat()
        if not self.mapped_count:
            self.mapped_count = len(self.samples)

    @property
    def sample_count(self) -> int:
        """返回可交给 Agent 的播放证据数量。"""
        return len(self.samples)

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化且不包含敏感字段的播放快照。"""
        return {
            "username": self.username,
            "source": self.source,
            "confidence": self.confidence,
            "status": self.status,
            "samples": [sample.to_dict() for sample in self.samples],
            "sample_count": self.sample_count,
            "mapped_count": self.mapped_count,
            "unmapped_count": self.unmapped_count,
            "synced_at": self.synced_at,
            "message": self.message,
            "fallback_from": list(self.fallback_from),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PlaybackSnapshot":
        """从持久化字典恢复播放画像快照。"""
        if not isinstance(value, Mapping):
            raise ValueError("playback snapshot must be a mapping")
        username = str(value.get("username") or "").strip()
        if not username:
            raise ValueError("playback snapshot username is required")
        return cls(
            username=username,
            source=str(value.get("source") or "subscription"),
            confidence=str(value.get("confidence") or "low"),
            status=str(value.get("status") or "fallback"),
            samples=[PlaybackSample.from_dict(item) for item in value.get("samples") or []],
            mapped_count=max(0, int(value.get("mapped_count") or 0)),
            unmapped_count=max(0, int(value.get("unmapped_count") or 0)),
            synced_at=str(value.get("synced_at") or ""),
            message=str(value.get("message") or ""),
            fallback_from=[str(item) for item in value.get("fallback_from") or []],
            schema_version=int(value.get("schema_version") or 1),
        )
