"""AgentRank 播放画像领域对象。"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping


PLAYBACK_CAPABILITY_STATUSES = frozenset(
    {
        "ready",
        "not_installed",
        "permission_error",
        "transient_error",
        "emby_unavailable",
    }
)


@dataclass
class PlaybackCapability:
    """表示指定 Emby identity 的 Playback Reporting 当前可用性。"""

    profile_id: str
    status: str
    message: str = ""
    checked_at: str = ""
    source: str = "playback_reporting"
    schema_version: int = 1

    def __post_init__(self) -> None:
        """规范化能力状态并拒绝未知分类。"""
        self.profile_id = str(self.profile_id or "").strip()
        self.status = str(self.status or "").strip()
        self.message = str(self.message or "").strip()
        self.source = str(self.source or "playback_reporting").strip()
        self.schema_version = int(self.schema_version)
        if not self.profile_id:
            raise ValueError("playback capability profile_id is required")
        if self.status not in PLAYBACK_CAPABILITY_STATUSES:
            raise ValueError("unknown playback capability status")
        if self.source != "playback_reporting":
            raise ValueError("playback capability source must be playback_reporting")
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        if not self.checked_at:
            self.checked_at = datetime.now(timezone.utc).isoformat()

    @property
    def ready(self) -> bool:
        """返回 Playback Reporting 是否可供当前 identity 使用。"""
        return self.status == "ready"

    def to_dict(self) -> Dict[str, Any]:
        """返回不包含地址、凭据或用户显示名的安全能力字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PlaybackCapability":
        """从安全字典恢复 Playback Reporting 能力状态。"""
        if not isinstance(value, Mapping):
            raise ValueError("playback capability must be a mapping")
        return cls(
            profile_id=value.get("profile_id"),
            status=value.get("status"),
            message=value.get("message") or "",
            checked_at=value.get("checked_at") or "",
            source=value.get("source") or "playback_reporting",
            schema_version=value.get("schema_version") or 1,
        )


@dataclass
class PlaybackSample:
    """表示一条已映射到媒体身份的用户播放证据。"""

    stable_id: str
    title: str
    media_type: str
    tmdb_id: str = ""
    overview: str = ""
    genres: List[str] = field(default_factory=list)
    completed: bool = False
    # 兼容旧快照字段；对电视剧它表示播放事件数，不是整剧完成次数。
    play_count: int = 0
    watched_episode_count: int = 0
    completed_episode_count: int = 0
    total_episode_count: int = 0
    watch_minutes: int = 0
    last_played_at: str = ""
    abandoned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """返回不含设备、地址和凭据的 Agent 安全字典。"""
        data = asdict(self)
        # 给新提示协议提供无歧义名称，同时保留 play_count 供旧快照和旧调用方读取。
        data["play_event_count"] = data["play_count"]
        return data

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
            overview=str(value.get("overview") or "")[:240],
            genres=[
                str(item).strip()[:20]
                for item in value.get("genres") or []
                if str(item).strip()
            ][:8],
            completed=bool(value.get("completed", False)),
            play_count=max(
                0,
                int(value.get("play_event_count") or value.get("play_count") or 0),
            ),
            watched_episode_count=max(0, int(value.get("watched_episode_count") or 0)),
            completed_episode_count=max(
                0, int(value.get("completed_episode_count") or 0)
            ),
            total_episode_count=max(0, int(value.get("total_episode_count") or 0)),
            watch_minutes=max(0, int(value.get("watch_minutes") or 0)),
            last_played_at=str(value.get("last_played_at") or ""),
            abandoned=bool(value.get("abandoned", False)),
        )


@dataclass
class PlaybackSnapshot:
    """表示一次按稳定 Emby 画像身份隔离的播放事实快照。"""

    profile_id: str
    source: str = "unavailable"
    confidence: str = "low"
    status: str = "fallback"
    username: str = ""
    samples: List[PlaybackSample] = field(default_factory=list)
    mapped_count: int = 0
    unmapped_count: int = 0
    synced_at: str = ""
    message: str = ""
    fallback_from: List[str] = field(default_factory=list)
    schema_version: int = 2

    def __post_init__(self) -> None:
        """为新采集结果补充稳定时间和映射计数。"""
        self.profile_id = str(self.profile_id or "").strip()
        self.username = str(self.username or "").strip()
        if not self.profile_id:
            raise ValueError("playback snapshot profile_id is required")
        if not self.synced_at:
            self.synced_at = datetime.now(timezone.utc).isoformat()
        if not self.mapped_count:
            self.mapped_count = len(self.samples)

    @property
    def sample_count(self) -> int:
        """返回可交给 Agent 的播放证据数量。"""
        return len(self.samples)

    def fingerprint(self) -> str:
        """返回排除同步时间和故障文案后的确定性播放事实指纹。"""
        facts = {
            "profile_id": self.profile_id,
            "source": self.source,
            "samples": [sample.to_dict() for sample in self.samples],
            "mapped_count": self.mapped_count,
            "unmapped_count": self.unmapped_count,
        }
        payload = json.dumps(
            facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化且不包含敏感字段的播放快照。"""
        return {
            "profile_id": self.profile_id,
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
        profile_id = str(value.get("profile_id") or "").strip()
        if not profile_id:
            raise ValueError("playback snapshot profile_id is required")
        return cls(
            profile_id=profile_id,
            source=str(value.get("source") or "unavailable"),
            confidence=str(value.get("confidence") or "low"),
            status=str(value.get("status") or "fallback"),
            username=str(value.get("username") or "").strip(),
            samples=[PlaybackSample.from_dict(item) for item in value.get("samples") or []],
            mapped_count=max(0, int(value.get("mapped_count") or 0)),
            unmapped_count=max(0, int(value.get("unmapped_count") or 0)),
            synced_at=str(value.get("synced_at") or ""),
            message=str(value.get("message") or ""),
            fallback_from=[str(item) for item in value.get("fallback_from") or []],
            schema_version=int(value.get("schema_version") or 2),
        )
