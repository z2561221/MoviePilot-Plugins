"""播放画像数据源优先级、降级与快照服务。"""

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from ..model.config import configured_identities
from ..model.identity import EmbyIdentity
from ..model.playback import PlaybackCapability, PlaybackSnapshot


class PlaybackProfileService:
    """使用稳定 Emby identity 调度 Playback Reporting 与快照回退。"""

    def __init__(self, repository: Any, reporting_adapter: Any):
        """绑定快照仓库和 Playback Reporting 适配器。"""
        self._repository = repository
        self._reporting = reporting_adapter

    @staticmethod
    def _identity(profile_id: str, config: Mapping[str, Any]) -> EmbyIdentity:
        """从受控配置解析完整且稳定的 Emby identity。"""
        for identity in configured_identities(config):
            if identity.profile_id == profile_id:
                return identity
        raise ValueError("profile_id is not configured")

    @staticmethod
    def _fresh(snapshot: Optional[PlaybackSnapshot], cache_days: int) -> bool:
        """判断上一次成功播放快照是否仍在允许回退窗口。"""
        if snapshot is None or snapshot.status not in {"ready", "cached"}:
            return False
        try:
            synced_at = datetime.fromisoformat(snapshot.synced_at.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return False
        synced_at = synced_at.replace(tzinfo=synced_at.tzinfo or timezone.utc)
        return synced_at >= datetime.now(timezone.utc) - timedelta(days=max(1, cache_days))

    def status(self, profile_id: str) -> PlaybackSnapshot:
        """读取当前用户最后一次播放画像状态，不触发外部请求。"""
        return self._repository.load_playback_snapshot(profile_id) or PlaybackSnapshot(
            profile_id=profile_id,
            username=profile_id,
            source="unavailable",
            confidence="low",
            status="idle",
            message="尚未同步播放画像",
        )

    def probe(
        self, profile_id: str, config: Mapping[str, Any]
    ) -> PlaybackCapability:
        """探测受控 identity 的 Playback Reporting 当前能力状态。"""
        target = str(profile_id or "").strip()
        if not target:
            raise ValueError("profile_id is required")
        return self._reporting.probe(self._identity(target, config))

    def collect(self, profile_id: str, config: Mapping[str, Any]) -> PlaybackSnapshot:
        """按配置采集 Playback Reporting，并执行瞬时故障快照回退。"""
        target = str(profile_id or "").strip()
        if not target:
            raise ValueError("profile_id is required")
        identity = self._identity(target, config)
        if not bool(config.get("playback_enabled", True)):
            snapshot = PlaybackSnapshot(
                target,
                "unavailable",
                "low",
                "disabled",
                username=identity.username,
                message="播放画像已关闭",
            )
            self._repository.save_playback_snapshot(snapshot)
            return snapshot
        options = {
            "recent_days": int(config.get("playback_recent_days") or 60),
            "completion_threshold": float(config.get("playback_completion_threshold") or 0.85),
            "abandon_minutes": int(config.get("playback_abandon_minutes") or 20),
        }
        library_map = config.get("emby_library_ids")
        options["library_ids"] = (
            list(library_map.get(target) or [])
            if isinstance(library_map, Mapping) and target in library_map
            else None
        )
        previous = self._repository.load_playback_snapshot(target)
        result = self._reporting.collect(identity, **options)
        result.profile_id = target
        result.username = identity.username
        if result.status == "transient_error" and self._fresh(
            previous, int(config.get("playback_cache_days") or 7)
        ):
            cached = PlaybackSnapshot.from_dict(previous.to_dict())
            cached.status = "cached"
            cached.message = "Playback Reporting 暂时不可用，已使用最近成功快照"
            cached.fallback_from = ["playback_reporting:transient_error"]
            return cached
        self._repository.save_playback_snapshot(result)
        return result
