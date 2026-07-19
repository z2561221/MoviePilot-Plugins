"""Emby 服务访问与原生 UserData 播放画像适配器。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from ..model.playback import PlaybackSample, PlaybackSnapshot


class EmbyServiceAccess:
    """封装 MoviePilot 已配置 Emby 实例及安全 HTTP 访问。"""

    def __init__(self, helper: Any = None, request_factory: Any = None):
        """允许测试注入媒体服务器帮助器和请求工厂。"""
        if helper is None:
            from app.helper.mediaserver import MediaServerHelper

            helper = MediaServerHelper()
        self._helper = helper
        self._request_factory = request_factory

    def services(self) -> Dict[str, Any]:
        """返回全部在线 Emby 服务，不返回 Jellyfin 或其他媒体服务器。"""
        services = self._helper.get_services() or {}
        return {
            str(name): service
            for name, service in services.items()
            if getattr(service, "type", "") == "emby"
            and getattr(service, "instance", None) is not None
            and not self._inactive(getattr(service, "instance", None))
        }

    def credentials(self, service: Any) -> Tuple[str, str, Any]:
        """从宿主服务实例读取仅供请求期使用的地址、令牌和实例。"""
        instance = getattr(service, "instance", None)
        host = str(getattr(instance, "_host", "") or "").rstrip("/") + "/"
        api_key = str(getattr(instance, "_apikey", "") or "")
        return host if host != "/" else "", api_key, instance

    def resolve_user(self, instance: Any, username: str) -> str:
        """将 Emby 用户名解析为服务器用户 ID。"""
        if instance is None or not hasattr(instance, "get_user"):
            return ""
        try:
            return str(instance.get_user(username) or "")
        except Exception:
            return ""

    @staticmethod
    def synced_item(server: str, item_id: str) -> Dict[str, Any]:
        """读取 MP 媒体库同步表中的条目身份，不触碰播放状态。"""
        if not server or not item_id:
            return {}
        try:
            from app.db.models.mediaserver import MediaServerItem

            item = MediaServerItem.get_by_server_itemid(server, str(item_id))
            if not item:
                return {}
            return {
                "tmdbid": getattr(item, "tmdbid", None),
                "title": getattr(item, "title", ""),
                "item_type": getattr(item, "item_type", ""),
                "year": getattr(item, "year", None),
            }
        except Exception:
            return {}

    def request(self, timeout: int = 8) -> Any:
        """创建带短超时的宿主 HTTP 客户端。"""
        if self._request_factory is not None:
            return self._request_factory(timeout=timeout)
        from app.utils.http import RequestUtils

        return RequestUtils(timeout=timeout, content_type="application/json")

    @staticmethod
    def _inactive(instance: Any) -> bool:
        """容错判断媒体服务器连接状态。"""
        try:
            return bool(hasattr(instance, "is_inactive") and instance.is_inactive())
        except Exception:
            return True


def _media_type(item_type: Any) -> str:
    """将 Emby ItemType 规范化为 AgentRank 媒体类型。"""
    value = str(item_type or "").lower()
    if value == "movie":
        return "movie"
    if value in {"series", "episode"}:
        return "tv"
    return "unknown"


def _ticks_to_minutes(value: Any) -> int:
    """把 Emby 一百纳秒 ticks 转为向下取整分钟。"""
    try:
        return max(0, int(float(value or 0) / 600_000_000))
    except (TypeError, ValueError):
        return 0


def merge_playback_samples(samples: Iterable[PlaybackSample]) -> List[PlaybackSample]:
    """按 TMDB 身份合并多服务器和多集播放证据。"""
    merged: Dict[str, PlaybackSample] = {}
    for sample in samples:
        current = merged.get(sample.stable_id)
        if current is None:
            merged[sample.stable_id] = PlaybackSample.from_dict(sample.to_dict())
            continue
        current.completed = current.completed or sample.completed
        current.play_count += sample.play_count
        current.watch_minutes += sample.watch_minutes
        current.abandoned = (current.abandoned or sample.abandoned) and not current.completed
        if sample.last_played_at > current.last_played_at:
            current.last_played_at = sample.last_played_at
        if len(sample.title) > len(current.title):
            current.title = sample.title
    return sorted(
        merged.values(),
        key=lambda item: (item.last_played_at, item.watch_minutes, item.play_count),
        reverse=True,
    )


class EmbyPlaybackAdapter:
    """从 Emby 原生 UserData 读取完成、次数、进度和最近播放。"""

    source = "emby_native"

    def __init__(self, access: EmbyServiceAccess):
        """绑定共享的 Emby 服务访问器。"""
        self._access = access

    def collect(
        self,
        username: str,
        recent_days: int = 180,
        completion_threshold: float = 0.85,
        abandon_minutes: int = 20,
    ) -> PlaybackSnapshot:
        """按用户读取全部在线 Emby 的原生播放状态。"""
        target = str(username or "").strip()
        services = self._access.services()
        if not services:
            return PlaybackSnapshot(target, self.source, "medium", "unavailable", message="未发现可用 Emby 服务")
        samples: List[PlaybackSample] = []
        unmapped = 0
        permission_error = False
        transient_error = False
        mapped_user = False
        for server_name, service in services.items():
            host, api_key, instance = self._access.credentials(service)
            user_id = self._access.resolve_user(instance, target)
            if not host or not api_key or not user_id:
                continue
            mapped_user = True
            response = self._access.request().get_res(
                f"{host}emby/Users/{user_id}/Items",
                params={
                    "api_key": api_key,
                    "Recursive": "true",
                    "IncludeItemTypes": "Movie,Series",
                    "Fields": "ProviderIds,UserData,RunTimeTicks,ProductionYear",
                    "SortBy": "DatePlayed",
                    "SortOrder": "Descending",
                    "Limit": 500,
                },
            )
            if response is None:
                transient_error = True
                continue
            if response.status_code in {401, 403}:
                permission_error = True
                continue
            if response.status_code >= 500:
                transient_error = True
                continue
            if response.status_code != 200:
                continue
            for item in (response.json() or {}).get("Items") or []:
                user_data = item.get("UserData") or {}
                played = bool(user_data.get("Played"))
                play_count = max(0, int(user_data.get("PlayCount") or 0))
                percentage = float(user_data.get("PlayedPercentage") or 0)
                if not played and play_count <= 0 and percentage <= 0:
                    continue
                synced = self._access.synced_item(server_name, str(item.get("Id") or ""))
                tmdb_id = str(
                    (item.get("ProviderIds") or {}).get("Tmdb")
                    or synced.get("tmdbid")
                    or ""
                )
                if not tmdb_id:
                    unmapped += 1
                    continue
                runtime_minutes = _ticks_to_minutes(item.get("RunTimeTicks"))
                watch_minutes = int(runtime_minutes * min(max(percentage, 0), 100) / 100)
                completed = played or percentage >= completion_threshold * 100
                samples.append(
                    PlaybackSample(
                        stable_id=f"tmdb:{_media_type(item.get('Type'))}:{tmdb_id}",
                        title=str(item.get("Name") or synced.get("title") or "未知媒体"),
                        media_type=_media_type(item.get("Type")),
                        tmdb_id=tmdb_id,
                        completed=completed,
                        play_count=play_count,
                        watch_minutes=watch_minutes,
                        last_played_at=str(user_data.get("LastPlayedDate") or ""),
                        abandoned=not completed and watch_minutes >= max(1, int(abandon_minutes)),
                    )
                )
        if not mapped_user:
            return PlaybackSnapshot(target, self.source, "medium", "user_unmapped", message="未找到对应的 Emby 用户")
        if not samples and permission_error:
            return PlaybackSnapshot(target, self.source, "medium", "permission_error", message="Emby 播放状态读取权限不足")
        if not samples and transient_error:
            return PlaybackSnapshot(target, self.source, "medium", "transient_error", message="Emby 播放状态暂时不可用")
        merged = merge_playback_samples(samples)
        return PlaybackSnapshot(
            target,
            self.source,
            "medium",
            "ready",
            samples=merged,
            mapped_count=len(merged),
            unmapped_count=unmapped,
            message="已使用 Emby 原生播放状态",
        )
