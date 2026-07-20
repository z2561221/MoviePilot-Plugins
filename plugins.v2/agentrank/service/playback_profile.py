"""播放画像数据源优先级、降级与快照服务。"""

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from ..model.config import configured_identities
from ..model.playback import PlaybackSnapshot


class PlaybackProfileService:
    """统一调度 Playback Reporting、Emby 原生与订阅兜底。"""

    def __init__(self, repository: Any, reporting_adapter: Any, native_adapter: Any):
        """绑定快照仓库和两个按优先级排列的数据源。"""
        self._repository = repository
        self._reporting = reporting_adapter
        self._native = native_adapter

    @staticmethod
    def _identity_username(profile_id: str, config: Mapping[str, Any]) -> str:
        """从受控配置解析 profile_id 对应的 Emby 显示名。"""
        for identity in configured_identities(config):
            if identity.profile_id == profile_id:
                return identity.username
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

    def collect(self, profile_id: str, config: Mapping[str, Any]) -> PlaybackSnapshot:
        """按配置执行数据源探测、快照回退和订阅兜底。"""
        target = str(profile_id or "").strip()
        if not target:
            raise ValueError("profile_id is required")
        source_username = self._identity_username(target, config)
        if not bool(config.get("playback_enabled", True)):
            snapshot = PlaybackSnapshot(
                target,
                "unavailable",
                "low",
                "disabled",
                username=source_username,
                message="播放画像已关闭",
            )
            self._repository.save_playback_snapshot(snapshot)
            return snapshot
        mode = str(config.get("playback_source_mode") or "auto")
        options = {
            "recent_days": int(config.get("playback_recent_days") or 180),
            "completion_threshold": float(config.get("playback_completion_threshold") or 0.85),
            "abandon_minutes": int(config.get("playback_abandon_minutes") or 20),
        }
        previous = self._repository.load_playback_snapshot(target)
        failures = []
        reporting_result = None
        if mode in {"auto", "playback_reporting"}:
            reporting_result = self._reporting.collect(source_username, **options)
            reporting_result.profile_id = target
            reporting_result.username = source_username
            if reporting_result.status == "ready" and (
                reporting_result.sample_count > 0 or mode == "playback_reporting"
            ):
                self._repository.save_playback_snapshot(reporting_result)
                return reporting_result
            if reporting_result.status == "ready":
                failures.append("playback_reporting:empty")
            else:
                failures.append(f"playback_reporting:{reporting_result.status}")
            if reporting_result.status == "transient_error" and self._fresh(
                previous, int(config.get("playback_cache_days") or 7)
            ):
                cached = PlaybackSnapshot.from_dict(previous.to_dict())
                cached.status = "cached"
                cached.message = "Playback Reporting 暂时不可用，已使用最近成功快照"
                cached.fallback_from = failures
                return cached
            if mode == "playback_reporting":
                reporting_result.fallback_from = failures
                self._repository.save_playback_snapshot(reporting_result)
                return reporting_result
        if mode in {"auto", "emby_native"}:
            native_result = self._native.collect(source_username, **options)
            native_result.profile_id = target
            native_result.username = source_username
            if native_result.status == "ready":
                native_result.fallback_from = failures
                if failures:
                    native_result.message += "；Playback Reporting 不可用时已自动降级"
                self._repository.save_playback_snapshot(native_result)
                return native_result
            failures.append(f"emby_native:{native_result.status}")
            if mode == "emby_native":
                native_result.fallback_from = failures
                self._repository.save_playback_snapshot(native_result)
                return native_result
        snapshot = PlaybackSnapshot(
            target,
            "unavailable",
            "low",
            "fallback",
            username=source_username,
            message="播放记录不可用，未生成新的画像证据",
            fallback_from=failures,
        )
        self._repository.save_playback_snapshot(snapshot)
        return snapshot
