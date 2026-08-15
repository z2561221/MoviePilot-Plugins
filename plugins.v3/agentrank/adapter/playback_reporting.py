"""Emby Playback Reporting 高精度播放记录适配器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .emby import EmbyServiceAccess, media_type, merge_playback_samples
from ..model.identity import EmbyIdentity
from ..model.playback import PlaybackCapability, PlaybackSample, PlaybackSnapshot


@dataclass
class _QueryResult:
    """保存一次受控查询的安全分类与后续采集上下文。"""

    capability: PlaybackCapability
    payload: Dict[str, Any] = field(default_factory=dict)
    server_name: str = ""
    host: str = ""
    api_key: str = ""


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

    @staticmethod
    def _probe_query() -> str:
        """构建不读取播放明细的最小只读能力探测 SQL。"""
        return "SELECT COUNT(1) AS ActivityCount FROM PlaybackActivity LIMIT 1"

    @staticmethod
    def _capability(
        identity: EmbyIdentity, status: str, message: str
    ) -> PlaybackCapability:
        """为指定 identity 创建不含敏感字段的能力状态。"""
        return PlaybackCapability(
            profile_id=identity.profile_id,
            status=status,
            message=message,
        )

    def _request_query(self, identity: EmbyIdentity, query: str) -> _QueryResult:
        """执行兼容端点查询并精确分类依赖与传输状态。"""
        if not isinstance(identity, EmbyIdentity):
            raise TypeError("identity must be EmbyIdentity")
        configured_server_name, service = self._access.resolve_service(
            identity.server_name
        )
        if service is None:
            return _QueryResult(
                self._capability(
                    identity, "emby_unavailable", "指定 Emby 服务不可用"
                )
            )
        host, api_key, _instance = self._access.credentials(service)
        if not host or not api_key:
            return _QueryResult(
                self._capability(
                    identity, "emby_unavailable", "Emby 连接信息不可用"
                )
            )
        for path in (
            "user_usage_stats/submit_custom_query",
            "emby/user_usage_stats/submit_custom_query",
        ):
            try:
                response = self._access.request().post_res(
                    f"{host}{path}",
                    params={"api_key": api_key},
                    json={"CustomQueryString": query, "ReplaceUserId": True},
                )
            except Exception:
                return _QueryResult(
                    self._capability(
                        identity,
                        "transient_error",
                        "Playback Reporting 暂时不可用",
                    )
                )
            if response is None:
                return _QueryResult(
                    self._capability(
                        identity,
                        "transient_error",
                        "Playback Reporting 暂时不可用",
                    )
                )
            try:
                status_code = int(getattr(response, "status_code", 0))
            except (TypeError, ValueError):
                status_code = 0
            if status_code == 404:
                continue
            if status_code in {401, 403}:
                return _QueryResult(
                    self._capability(
                        identity,
                        "permission_error",
                        "Playback Reporting 读取权限不足",
                    )
                )
            if status_code != 200:
                return _QueryResult(
                    self._capability(
                        identity,
                        "transient_error",
                        "Playback Reporting 暂时不可用",
                    )
                )
            try:
                payload = response.json() or {}
            except Exception:
                payload = None
            if not isinstance(payload, Mapping) or str(
                payload.get("message") or ""
            ).strip():
                return _QueryResult(
                    self._capability(
                        identity,
                        "transient_error",
                        "Playback Reporting 返回异常",
                    )
                )
            return _QueryResult(
                capability=self._capability(
                    identity, "ready", "Playback Reporting 可访问"
                ),
                payload=dict(payload),
                server_name=configured_server_name,
                host=host,
                api_key=api_key,
            )
        return _QueryResult(
            self._capability(
                identity, "not_installed", "未安装 Playback Reporting"
            )
        )

    def probe(self, identity: EmbyIdentity) -> PlaybackCapability:
        """探测指定 Emby identity 的 Playback Reporting 可用性。"""
        return self._request_query(identity, self._probe_query()).capability

    def _fetch_details(
        self,
        server_name: str,
        host: str,
        api_key: str,
        user_id: str,
        item_ids: Iterable[str],
        library_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """在所选内容库内批量读取播放条目及其剧集父级详情。"""
        ids = [str(item) for item in item_ids if str(item or "").strip()][:500]
        if not ids:
            return {}
        selected_libraries = (
            [str(item) for item in library_ids if str(item or "").strip()]
            if library_ids is not None
            else None
        )
        if selected_libraries == []:
            return {}
        detail_queries = selected_libraries or [None]
        details: Dict[str, Dict[str, Any]] = {}
        for library_id in detail_queries:
            params = {
                "api_key": api_key,
                "Ids": ",".join(ids),
                "Fields": "ProviderIds,RunTimeTicks,SeriesId,SeriesName,ProductionYear,Overview,Genres,RecursiveItemCount,UserData",
                "Limit": len(ids),
            }
            if library_id is not None:
                params.update({"ParentId": library_id, "Recursive": True})
            response = self._access.request().get_res(
                f"{host}emby/Users/{user_id}/Items", params=params
            )
            if response is None or response.status_code != 200:
                continue
            details.update(
                {
                    str(item.get("Id")): item
                    for item in (response.json() or {}).get("Items") or []
                    if item.get("Id")
                }
            )
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
                    "Fields": "ProviderIds,RunTimeTicks,ProductionYear,Overview,Genres,RecursiveItemCount,UserData",
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
        recent_days: int = 90,
        completion_threshold: float = 0.85,
        abandon_minutes: int = 20,
        library_ids: Optional[Iterable[str]] = None,
    ) -> PlaybackSnapshot:
        """读取 Playback Reporting，并将会话映射为 TMDB 级播放证据。"""
        query_result = self._request_query(identity, self._query(recent_days))
        target = identity.profile_id
        capability = query_result.capability
        if not capability.ready:
            return PlaybackSnapshot(
                target,
                self.source,
                "low" if capability.status == "emby_unavailable" else "high",
                capability.status,
                username=identity.username,
                message=capability.message,
            )
        collected: List[PlaybackSample] = []
        unmapped = 0
        payload = query_result.payload
        rows = [
            row
            for row in self._rows(payload)
            if {
                str(row.get("UserId") or "").strip(),
                str(row.get("UserName") or "").strip(),
            }
            & {identity.user_id, identity.username}
        ]
        details = self._fetch_details(
            query_result.server_name,
            query_result.host,
            query_result.api_key,
            identity.user_id,
            [row.get("ItemId") for row in rows],
            library_ids=library_ids,
        )
        for row in rows:
            item_id = str(row.get("ItemId") or "")
            if library_ids is not None and item_id not in details:
                continue
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
                runtime_seconds = max(
                    0, int(float(detail.get("RunTimeTicks") or 0) / 10_000_000)
                )
            except (TypeError, ValueError):
                unmapped += 1
                continue
            completed_episode = bool(
                runtime_seconds
                and watch_seconds >= runtime_seconds * completion_threshold
            )
            item_media_type = media_type(row.get("ItemType"))
            item_is_episode = str(row.get("ItemType") or "").casefold() == "episode"
            user_data = media_identity.get("UserData") or {}
            # TV 的 completed 只接受 Emby 系列父级整体完成信号。
            series_completed = (
                bool(user_data.get("Played")) if item_media_type == "tv" else False
            )
            completed = (
                series_completed if item_media_type == "tv" else completed_episode
            )
            try:
                total_episode_count = max(
                    0, int(float(media_identity.get("RecursiveItemCount") or 0))
                )
            except (TypeError, ValueError):
                total_episode_count = 0
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
                    overview=" ".join(
                        str(media_identity.get("Overview") or "").split()
                    )[:240],
                    genres=[
                        str(item).strip()[:20]
                        for item in media_identity.get("Genres") or []
                        if str(item).strip()
                    ][:8],
                    completed=completed,
                    play_count=play_count,
                    watched_episode_count=1 if item_is_episode else 0,
                    completed_episode_count=(
                        1 if item_is_episode and completed_episode else 0
                    ),
                    total_episode_count=(
                        total_episode_count if item_media_type == "tv" else 0
                    ),
                    watch_minutes=watch_seconds // 60,
                    last_played_at=str(row.get("LastPlayedAt") or ""),
                    abandoned=item_media_type == "movie"
                    and not completed
                    and watch_seconds >= max(1, int(abandon_minutes)) * 60,
                )
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
