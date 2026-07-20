"""共享 Emby 服务访问、用户枚举与媒体身份辅助能力。"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Mapping, Tuple

from ..model.identity import EmbyIdentity
from ..model.playback import PlaybackSample


class EmbyServiceAccess:
    """封装 MoviePilot 在线 Emby 实例、用户枚举及安全 HTTP 访问。"""

    def __init__(self, helper: Any = None, request_factory: Any = None):
        """允许测试注入媒体服务器帮助器和请求工厂。"""
        if helper is None:
            from app.helper.mediaserver import MediaServerHelper

            helper = MediaServerHelper()
        self._helper = helper
        self._request_factory = request_factory

    def services(self) -> Dict[str, Any]:
        """返回全部在线 Emby 服务，不返回其他媒体服务器或离线实例。"""
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

    def resolve_service(self, server_name: str) -> Tuple[str, Any]:
        """按稳定服务器作用域解析当前在线服务及其 MoviePilot 配置名。"""
        target = str(server_name or "").strip()
        for configured_name, service in self.services().items():
            instance = getattr(service, "instance", None)
            if self._identity_server_name(configured_name, instance) == target:
                return configured_name, service
        return "", None

    @staticmethod
    def _identity_server_name(configured_name: str, instance: Any) -> str:
        """为不安全的服务显示名选择稳定且可持久化的服务器作用域。"""
        name = str(configured_name or "").strip()
        try:
            return EmbyIdentity(name, "probe", "probe").server_name
        except ValueError:
            server_id = str(getattr(instance, "serverid", "") or "").strip()
            try:
                return EmbyIdentity(server_id, "probe", "probe").server_name
            except ValueError:
                digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
                return f"server-{digest}"

    @staticmethod
    def _user_rows(payload: Any) -> List[Mapping[str, Any]]:
        """兼容 Emby Users 列表与 Query 风格响应。"""
        values = payload.get("Items") if isinstance(payload, Mapping) else payload
        if not isinstance(values, list):
            return []
        return [item for item in values if isinstance(item, Mapping)]

    def enumerate_identities(self) -> List[EmbyIdentity]:
        """枚举全部在线 Emby 用户并返回去重后的稳定身份。"""
        identities: List[EmbyIdentity] = []
        seen = set()
        for configured_name, service in self.services().items():
            host, api_key, instance = self.credentials(service)
            if not host or not api_key:
                continue
            response = None
            for path in ("Users", "emby/Users"):
                try:
                    response = self.request().get_res(
                        f"{host}{path}", params={"api_key": api_key}
                    )
                except Exception:
                    response = None
                if response is None or response.status_code != 404:
                    break
            if response is None or response.status_code != 200:
                continue
            server_name = self._identity_server_name(configured_name, instance)
            for row in self._user_rows(response.json() or []):
                policy = row.get("Policy")
                if isinstance(policy, Mapping) and bool(policy.get("IsDisabled")):
                    continue
                try:
                    identity = EmbyIdentity(
                        server_name=server_name,
                        user_id=row.get("Id"),
                        username=row.get("Name"),
                    )
                except (TypeError, ValueError):
                    continue
                if identity.profile_id in seen:
                    continue
                seen.add(identity.profile_id)
                identities.append(identity)
        return identities

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


def media_type(item_type: Any) -> str:
    """将 Emby ItemType 规范化为 AgentRank 媒体类型。"""
    value = str(item_type or "").lower()
    if value == "movie":
        return "movie"
    if value in {"series", "episode"}:
        return "tv"
    return "unknown"


def merge_playback_samples(samples: Iterable[PlaybackSample]) -> List[PlaybackSample]:
    """按 TMDB 身份合并多条播放证据。"""
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
