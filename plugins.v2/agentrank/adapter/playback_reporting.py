"""Emby Playback Reporting 高精度播放记录适配器。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from .emby import EmbyServiceAccess, media_type, merge_playback_samples
from ..model.identity import EmbyIdentity
from ..model.playback import PlaybackSample, PlaybackSnapshot


class PlaybackReportingAdapter:
    """通过 Playback Reporting 只读查询读取聚合播放会话。"""

    source = "playback_reporting"

    def __init__(self, access: EmbyServiceAccess):
        """绑定共享的 Emby 服务访问器。"""
        self._access = access

    @staticmethod
    def _query(recent_days: int) -> str:
        """构建仅含固定字段和有界天数的只读聚合 SQL。"""
        days = max(1, min(int(recent_days), 3650))
        return (
            "SELECT UserId, ItemId, ItemType, ItemName, COUNT(1) AS PlayCount, "
            "SUM(PlayDuration) AS WatchSeconds, MAX(DateCreated) AS LastPlayedAt "
            "FROM PlaybackActivity "
            f"WHERE DateCreated >= datetime('now','-{days} days') "
            "AND PlayDuration > 0 AND ItemType IN ('Movie','Episode','Series') "
            "GROUP BY UserId, ItemId, ItemType, ItemName "
            "ORDER BY LastPlayedAt DESC LIMIT 500"
        )

    @staticmethod
    def _rows(payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
        """把插件特有的 colums/results 响应转换为字典列表。"""
        columns = [str(item) for item in payload.get("colums") or payload.get("columns") or []]
        rows: List[Dict[str, Any]] = []
        for raw in payload.get("results") or []:
            if isinstance(raw, (list, tuple)) and len(raw) == len(columns):
                rows.append(dict(zip(columns, raw)))
        return rows

    def _fetch_details(
        self,
        server_name: str,
        host: str,
        api_key: str,
        user_id: str,
        item_ids: Iterable[str],
    ) -> Dict[str, Dict[str, Any]]:
        """批量读取播放条目及其剧集父级的 TMDB 身份与时长。"""
        ids = [str(item) for item in item_ids if str(item or "").strip()][:500]
        if not ids:
            return {}
        response = self._access.request().get_res(
            f"{host}emby/Users/{user_id}/Items",
            params={
                "api_key": api_key,
                "Ids": ",".join(ids),
                "Fields": "ProviderIds,RunTimeTicks,SeriesId,SeriesName,ProductionYear",
                "Limit": len(ids),
            },
        )
        if response is None or response.status_code != 200:
            return {}
        details = {
            str(item.get("Id")): item
            for item in (response.json() or {}).get("Items") or []
            if item.get("Id")
        }
        for item_id in ids:
            synced = self._access.synced_item(server_name, item_id)
            if synced and item_id in details:
                details[item_id].setdefault("ProviderIds", {})
                if synced.get("tmdbid") and not details[item_id]["ProviderIds"].get("Tmdb"):
                    details[item_id]["ProviderIds"]["Tmdb"] = str(synced["tmdbid"])
                if synced.get("title") and not details[item_id].get("Name"):
                    details[item_id]["Name"] = synced["title"]
        series_ids = {
            str(item.get("SeriesId"))
            for item in details.values()
            if item.get("SeriesId")
        }
        missing_series = [item for item in series_ids if item not in details]
        if missing_series:
            parent_response = self._access.request().get_res(
                f"{host}emby/Users/{user_id}/Items",
                params={
                    "api_key": api_key,
                    "Ids": ",".join(missing_series),
                    "Fields": "ProviderIds,RunTimeTicks,ProductionYear",
                    "Limit": len(missing_series),
                },
            )
            if parent_response is not None and parent_response.status_code == 200:
                details.update(
                    {
                        str(item.get("Id")): item
                        for item in (parent_response.json() or {}).get("Items") or []
                        if item.get("Id")
                    }
                )
                for series_id in missing_series:
                    synced = self._access.synced_item(server_name, series_id)
                    if synced and series_id in details:
                        details[series_id].setdefault("ProviderIds", {})
                        if synced.get("tmdbid") and not details[series_id]["ProviderIds"].get("Tmdb"):
                            details[series_id]["ProviderIds"]["Tmdb"] = str(synced["tmdbid"])
        return details

    def collect(
        self,
        identity: EmbyIdentity,
        recent_days: int = 180,
        completion_threshold: float = 0.85,
        abandon_minutes: int = 20,
    ) -> PlaybackSnapshot:
        """读取 Playback Reporting，并将会话映射为 TMDB 级播放证据。"""
        if not isinstance(identity, EmbyIdentity):
            raise TypeError("identity must be EmbyIdentity")
        target = identity.profile_id
        configured_server_name, service = self._access.resolve_service(
            identity.server_name
        )
        if service is None:
            return PlaybackSnapshot(
                target,
                self.source,
                "high",
                "unavailable",
                username=identity.username,
                message="指定 Emby 服务不可用",
            )
        collected: List[PlaybackSample] = []
        unmapped = 0
        detected = False
        permission_error = False
        transient_error = False
        mapped_user = False
        for server_name, service in ((configured_server_name, service),):
            host, api_key, _instance = self._access.credentials(service)
            user_id = identity.user_id
            if not host or not api_key or not user_id:
                continue
            mapped_user = True
            response = None
            for path in ("user_usage_stats/submit_custom_query", "emby/user_usage_stats/submit_custom_query"):
                response = self._access.request().post_res(
                    f"{host}{path}",
                    params={"api_key": api_key},
                    json={"CustomQueryString": self._query(recent_days), "ReplaceUserId": True},
                )
                if response is None or response.status_code != 404:
                    break
            if response is None:
                transient_error = True
                continue
            if response.status_code == 404:
                continue
            if response.status_code in {401, 403}:
                permission_error = True
                continue
            if response.status_code >= 500:
                transient_error = True
                continue
            if response.status_code != 200:
                continue
            detected = True
            payload = response.json() or {}
            if str(payload.get("message") or "").strip():
                transient_error = True
                continue
            rows = [
                row
                for row in self._rows(payload)
                if {
                    str(row.get("UserId") or "").strip(),
                    str(row.get("UserName") or "").strip(),
                }
                & {identity.user_id, identity.username}
            ]
            details = self._fetch_details(server_name, host, api_key, user_id, [row.get("ItemId") for row in rows])
            for row in rows:
                item_id = str(row.get("ItemId") or "")
                detail = details.get(item_id) or {}
                parent = details.get(str(detail.get("SeriesId") or "")) or {}
                media_identity = (
                    parent
                    if media_type(row.get("ItemType")) == "tv" and parent
                    else detail
                )
                tmdb_id = str(
                    (media_identity.get("ProviderIds") or {}).get("Tmdb") or ""
                )
                if not tmdb_id:
                    unmapped += 1
                    continue
                try:
                    watch_seconds = max(0, int(float(row.get("WatchSeconds") or 0)))
                    play_count = max(0, int(row.get("PlayCount") or 0))
                    runtime_seconds = max(0, int(float(detail.get("RunTimeTicks") or 0) / 10_000_000))
                except (TypeError, ValueError):
                    unmapped += 1
                    continue
                completed = bool(runtime_seconds and watch_seconds >= runtime_seconds * completion_threshold)
                item_media_type = media_type(row.get("ItemType"))
                collected.append(
                    PlaybackSample(
                        stable_id=f"tmdb:{item_media_type}:{tmdb_id}",
                        title=str(
                            media_identity.get("Name")
                            or detail.get("SeriesName")
                            or row.get("ItemName")
                            or "未知媒体"
                        ),
                        media_type=item_media_type,
                        tmdb_id=tmdb_id,
                        completed=completed,
                        play_count=play_count,
                        watch_minutes=watch_seconds // 60,
                        last_played_at=str(row.get("LastPlayedAt") or ""),
                        abandoned=not completed and watch_seconds >= max(1, int(abandon_minutes)) * 60,
                    )
                )
        if not mapped_user:
            return PlaybackSnapshot(
                target,
                self.source,
                "high",
                "user_unmapped",
                username=identity.username,
                message="Emby 用户身份不可用",
            )
        if not detected:
            if permission_error:
                return PlaybackSnapshot(
                    target,
                    self.source,
                    "high",
                    "permission_error",
                    username=identity.username,
                    message="Playback Reporting 读取权限不足",
                )
            if transient_error:
                return PlaybackSnapshot(
                    target,
                    self.source,
                    "high",
                    "transient_error",
                    username=identity.username,
                    message="Playback Reporting 暂时不可用",
                )
            return PlaybackSnapshot(
                target,
                self.source,
                "high",
                "not_installed",
                username=identity.username,
                message="未安装 Playback Reporting",
            )
        merged = merge_playback_samples(collected)
        return PlaybackSnapshot(
            target,
            self.source,
            "high",
            "ready",
            username=identity.username,
            samples=merged,
            mapped_count=len(merged),
            unmapped_count=unmapped,
            message="已使用 Playback Reporting 播放记录",
        )
