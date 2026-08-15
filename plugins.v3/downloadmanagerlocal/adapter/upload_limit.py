"""qBittorrent 与 Transmission 上传限速读写适配器。"""

from __future__ import annotations

import math
from typing import Any, Iterable

from ..model.upload_limit import (
    GlobalUploadSettings,
    TorrentUploadSettings,
    UploadTorrentSnapshot,
)


SUPPORTED_UPLOAD_LIMIT_TYPES = {"qbittorrent", "transmission"}
TRANSMISSION_UPLOAD_ARGUMENTS = [
    "id",
    "name",
    "status",
    "labels",
    "hashString",
    "totalSize",
    "percentDone",
    "leftUntilDone",
    "addedDate",
    "doneDate",
    "rateUpload",
    "peersConnected",
    "peersGettingFromUs",
    "uploadLimit",
    "uploadLimited",
]


def read_global_upload_settings(instance: Any, downloader_type: str) -> GlobalUploadSettings:
    """读取下载器全局上传限速，不触碰下载限速字段。"""
    normalized = _normalize_type(downloader_type)
    if normalized == "qbittorrent":
        client = _require_attr(instance, "qbc")
        normal_bps = _nonnegative_int(getattr(client.transfer, "upload_limit", 0))
        preferences = client.app_preferences() or {}
        alternate_bps = _nonnegative_int(_read(preferences, "alt_up_limit", default=0))
        return GlobalUploadSettings(
            downloader_type=normalized,
            upload_limit_bps=normal_bps,
            upload_enabled=normal_bps > 0,
            alternate_upload_limit_bps=alternate_bps,
            alternate_upload_enabled=alternate_bps > 0,
        )
    client = _require_attr(instance, "trc")
    session = client.get_session()
    limit_kib = _nonnegative_int(_read(
        session,
        "speed_limit_up",
        "speed-limit-up",
        "speedLimitUp",
        default=0,
    ))
    enabled = bool(_read(
        session,
        "speed_limit_up_enabled",
        "speed-limit-up-enabled",
        "speedLimitUpEnabled",
        default=limit_kib > 0,
    ))
    return GlobalUploadSettings(
        downloader_type=normalized,
        upload_limit_bps=limit_kib * 1024,
        upload_enabled=enabled,
    )


def write_global_upload_limit(
    instance: Any,
    downloader_type: str,
    limit_kib: int,
) -> GlobalUploadSettings:
    """写入插件总上传上限；qB 同时覆盖普通与备用上传上限。"""
    normalized = _normalize_type(downloader_type)
    normalized_limit = max(1, int(limit_kib or 0))
    limit_bps = normalized_limit * 1024
    if normalized == "qbittorrent":
        client = _require_attr(instance, "qbc")
        client.transfer.upload_limit = limit_bps
        client.app_set_preferences({"alt_up_limit": limit_bps})
        return GlobalUploadSettings(
            downloader_type=normalized,
            upload_limit_bps=limit_bps,
            upload_enabled=True,
            alternate_upload_limit_bps=limit_bps,
            alternate_upload_enabled=True,
        )
    client = _require_attr(instance, "trc")
    client.set_session(
        speed_limit_up=normalized_limit,
        speed_limit_up_enabled=True,
    )
    return GlobalUploadSettings(
        downloader_type=normalized,
        upload_limit_bps=limit_bps,
        upload_enabled=True,
    )


def expected_global_upload_settings(
    downloader_type: str,
    limit_kib: int,
) -> GlobalUploadSettings:
    """返回插件总上限对应的下载器全局设置快照。"""
    normalized = _normalize_type(downloader_type)
    normalized_limit = max(1, int(limit_kib or 0))
    limit_bps = normalized_limit * 1024
    return GlobalUploadSettings(
        downloader_type=normalized,
        upload_limit_bps=limit_bps,
        upload_enabled=True,
        alternate_upload_limit_bps=(limit_bps if normalized == "qbittorrent" else None),
        alternate_upload_enabled=(True if normalized == "qbittorrent" else None),
    )


def restore_global_upload_settings(
    instance: Any,
    downloader_type: str,
    settings: GlobalUploadSettings,
) -> GlobalUploadSettings:
    """精确恢复接管前的全局上传限速，不改动下载限速。"""
    normalized = _normalize_type(downloader_type)
    if normalized == "qbittorrent":
        client = _require_attr(instance, "qbc")
        normal_bps = max(0, int(settings.upload_limit_bps or 0))
        alternate_bps = max(0, int(settings.alternate_upload_limit_bps or 0))
        client.transfer.upload_limit = normal_bps
        client.app_set_preferences({"alt_up_limit": alternate_bps})
        return GlobalUploadSettings(
            downloader_type=normalized,
            upload_limit_bps=normal_bps,
            upload_enabled=normal_bps > 0,
            alternate_upload_limit_bps=alternate_bps,
            alternate_upload_enabled=alternate_bps > 0,
        )
    client = _require_attr(instance, "trc")
    limit_kib = _bps_to_kib(settings.upload_limit_bps)
    client.set_session(
        speed_limit_up=limit_kib,
        speed_limit_up_enabled=bool(settings.upload_enabled),
    )
    return GlobalUploadSettings(
        downloader_type=normalized,
        upload_limit_bps=limit_kib * 1024,
        upload_enabled=bool(settings.upload_enabled),
    )


def list_upload_torrents(
    instance: Any,
    downloader_id: str,
    downloader_type: str,
) -> tuple[list[UploadTorrentSnapshot], str]:
    """读取下载器任务并归一化上传状态，错误以字符串返回。"""
    normalized = _normalize_type(downloader_type)
    try:
        if normalized == "transmission" and getattr(instance, "trc", None):
            raw_items = instance.trc.get_torrents(arguments=TRANSMISSION_UPLOAD_ARGUMENTS)
            error = None
        else:
            response = instance.get_torrents()
            raw_items, error = _unwrap_torrent_response(response)
        if error:
            return [], str(error)
        return [
            normalize_upload_torrent(item, downloader_id, normalized)
            for item in raw_items or []
        ], ""
    except Exception as error:
        return [], str(error)


def normalize_upload_torrent(
    torrent: Any,
    downloader_id: str,
    downloader_type: str,
) -> UploadTorrentSnapshot:
    """把 qB 字典或 Transmission 对象归一为上传限速快照。"""
    normalized = _normalize_type(downloader_type)
    if normalized == "qbittorrent":
        torrent_hash = _read(torrent, "hash", default="")
        labels = _split_labels(_read(torrent, "tags", default=""))
        state = str(_read(torrent, "state", default="") or "")
        progress = _number(_read(torrent, "progress", default=0))
        amount_left = _number(_read(torrent, "amount_left", default=0))
        total_size = _number(_read(torrent, "total_size", "size", default=0))
        completed = progress >= 1 or (
            total_size > 0 and amount_left <= 0
        ) or _completed_state(state)
        added_at = _timestamp(_read(torrent, "added_on", default=0))
        completed_at = _timestamp(_read(
            torrent,
            "completion_on",
            "completed_on",
            default=0,
        ))
        upload_rate_bps = _nonnegative_int(_read(torrent, "upspeed", default=0))
        upload_demand_peers = max(
            _nonnegative_int(_read(torrent, "num_leechs", default=0)),
            1 if upload_rate_bps > 0 else 0,
        )
        limit_bps = _nonnegative_int(_read(torrent, "up_limit", default=0))
        upload_settings = TorrentUploadSettings(
            limit_bps=limit_bps,
            enabled=limit_bps > 0,
        )
    else:
        torrent_hash = _read(torrent, "hashString", "hash_string", default="")
        labels = _split_labels(_read(torrent, "labels", default=[]))
        state = str(_read(torrent, "status", default="") or "")
        progress = _number(_read(torrent, "percentDone", "percent_done", default=0))
        left = _number(_read(torrent, "leftUntilDone", "left_until_done", default=0))
        total_size = _number(_read(torrent, "totalSize", "total_size", default=0))
        completed = progress >= 1 or (
            total_size > 0 and left <= 0
        ) or _completed_state(state)
        added_at = _timestamp(_read(torrent, "addedDate", "added_date", default=0))
        completed_at = _timestamp(_read(torrent, "doneDate", "done_date", default=0))
        upload_rate_bps = _nonnegative_int(_read(
            torrent, "rateUpload", "rate_upload", default=0
        ))
        upload_demand_peers = max(
            _nonnegative_int(_read(
                torrent,
                "peersGettingFromUs",
                "peers_getting_from_us",
                default=0,
            )),
            _nonnegative_int(_read(
                torrent,
                "peersConnected",
                "peers_connected",
                default=0,
            )),
            1 if upload_rate_bps > 0 else 0,
        )
        limit_kib = _nonnegative_int(_read(
            torrent, "uploadLimit", "upload_limit", default=0
        ))
        enabled = bool(_read(
            torrent,
            "uploadLimited",
            "upload_limited",
            default=limit_kib > 0,
        ))
        upload_settings = TorrentUploadSettings(
            limit_bps=limit_kib * 1024,
            enabled=enabled,
        )
    return UploadTorrentSnapshot(
        downloader_id=str(downloader_id or "").strip(),
        downloader_type=normalized,
        torrent_hash=str(torrent_hash or "").strip().lower(),
        name=str(_read(torrent, "name", default="") or ""),
        labels=tuple(labels),
        state=state,
        completed=bool(completed),
        added_at=added_at,
        completed_at=completed_at,
        upload_rate_bps=upload_rate_bps,
        upload_demand_peers=upload_demand_peers,
        upload_settings=upload_settings,
    )


def write_torrent_upload_limit(
    instance: Any,
    downloader_type: str,
    torrent_hash: str,
    limit_kib: int,
) -> TorrentUploadSettings:
    """写入插件分配的单种限额；零额度使用底层 API 避免被解释为不限速。"""
    normalized = _normalize_type(downloader_type)
    clean_hash = str(torrent_hash or "").strip()
    if not clean_hash:
        raise ValueError("torrent hash is required")
    normalized_limit = max(0, int(limit_kib or 0))
    if normalized == "qbittorrent":
        client = _require_attr(instance, "qbc")
        applied_bps = normalized_limit * 1024 if normalized_limit > 0 else 1
        client.torrents_set_upload_limit(
            limit=applied_bps,
            torrent_hashes=clean_hash,
        )
        return TorrentUploadSettings(limit_bps=applied_bps, enabled=True)
    client = _require_attr(instance, "trc")
    client.change_torrent(
        ids=clean_hash,
        uploadLimited=True,
        uploadLimit=normalized_limit,
    )
    return TorrentUploadSettings(
        limit_bps=normalized_limit * 1024,
        enabled=True,
    )


def expected_torrent_upload_settings(
    downloader_type: str,
    limit_kib: int,
) -> TorrentUploadSettings:
    """返回逻辑单种额度在目标下载器中的实际设置。"""
    normalized = _normalize_type(downloader_type)
    normalized_limit = max(0, int(limit_kib or 0))
    if normalized == "qbittorrent":
        return TorrentUploadSettings(
            limit_bps=normalized_limit * 1024 if normalized_limit > 0 else 1,
            enabled=True,
        )
    return TorrentUploadSettings(
        limit_bps=normalized_limit * 1024,
        enabled=True,
    )


def restore_torrent_upload_settings(
    instance: Any,
    downloader_type: str,
    torrent_hash: str,
    settings: TorrentUploadSettings,
) -> TorrentUploadSettings:
    """恢复接管前的单种上传限速及 Transmission 启用状态。"""
    normalized = _normalize_type(downloader_type)
    clean_hash = str(torrent_hash or "").strip()
    if not clean_hash:
        raise ValueError("torrent hash is required")
    if normalized == "qbittorrent":
        client = _require_attr(instance, "qbc")
        applied_bps = max(0, int(settings.limit_bps or 0)) if settings.enabled else 0
        client.torrents_set_upload_limit(
            limit=applied_bps,
            torrent_hashes=clean_hash,
        )
        return TorrentUploadSettings(
            limit_bps=applied_bps,
            enabled=applied_bps > 0,
        )
    client = _require_attr(instance, "trc")
    limit_kib = _bps_to_kib(settings.limit_bps)
    client.change_torrent(
        ids=clean_hash,
        uploadLimited=bool(settings.enabled),
        uploadLimit=limit_kib,
    )
    return TorrentUploadSettings(
        limit_bps=limit_kib * 1024,
        enabled=bool(settings.enabled),
    )


def global_settings_equal(left: GlobalUploadSettings, right: GlobalUploadSettings) -> bool:
    """比较两个下载器全局上传设置是否等价。"""
    return (
        left.downloader_type == right.downloader_type
        and left.upload_limit_bps == right.upload_limit_bps
        and left.upload_enabled == right.upload_enabled
        and left.alternate_upload_limit_bps == right.alternate_upload_limit_bps
        and left.alternate_upload_enabled == right.alternate_upload_enabled
    )


def torrent_settings_equal(left: TorrentUploadSettings, right: TorrentUploadSettings) -> bool:
    """比较两个单种上传设置是否等价。"""
    return left.limit_bps == right.limit_bps and left.enabled == right.enabled


def settings_from_dict(value: Any) -> TorrentUploadSettings:
    """从持久化字典恢复单种上传设置。"""
    source = value if isinstance(value, dict) else {}
    return TorrentUploadSettings(
        limit_bps=_nonnegative_int(source.get("limit_bps")),
        enabled=bool(source.get("enabled", False)),
    )


def settings_to_dict(value: TorrentUploadSettings) -> dict:
    """把单种上传设置转换为可持久化字典。"""
    return {
        "limit_bps": max(0, int(value.limit_bps or 0)),
        "enabled": bool(value.enabled),
    }


def global_settings_from_dict(value: Any, downloader_type: str) -> GlobalUploadSettings:
    """从持久化字典恢复下载器全局上传设置。"""
    source = value if isinstance(value, dict) else {}
    alternate = source.get("alternate_upload_limit_bps")
    alternate_enabled = source.get("alternate_upload_enabled")
    return GlobalUploadSettings(
        downloader_type=_normalize_type(downloader_type),
        upload_limit_bps=_nonnegative_int(source.get("upload_limit_bps")),
        upload_enabled=bool(source.get("upload_enabled", False)),
        alternate_upload_limit_bps=(
            None if alternate is None else _nonnegative_int(alternate)
        ),
        alternate_upload_enabled=(
            None if alternate_enabled is None else bool(alternate_enabled)
        ),
    )


def global_settings_to_dict(value: GlobalUploadSettings) -> dict:
    """把下载器全局上传设置转换为可持久化字典。"""
    return {
        "upload_limit_bps": max(0, int(value.upload_limit_bps or 0)),
        "upload_enabled": bool(value.upload_enabled),
        "alternate_upload_limit_bps": (
            None if value.alternate_upload_limit_bps is None
            else max(0, int(value.alternate_upload_limit_bps or 0))
        ),
        "alternate_upload_enabled": value.alternate_upload_enabled,
    }


def _unwrap_torrent_response(response: Any) -> tuple[Iterable[Any], Any]:
    """兼容 MoviePilot 下载器返回的列表或二元组。"""
    if isinstance(response, tuple) and len(response) == 2:
        return response[0] or [], response[1]
    if response is None:
        return [], "downloader returned no result"
    return response, None


def _normalize_type(value: str) -> str:
    """校验并返回受支持的下载器类型。"""
    normalized = str(value or "").strip().lower()
    if normalized not in SUPPORTED_UPLOAD_LIMIT_TYPES:
        raise ValueError(f"unsupported downloader type: {value}")
    return normalized


def _require_attr(instance: Any, name: str) -> Any:
    """读取必需的底层客户端属性，缺失时抛出明确错误。"""
    value = getattr(instance, name, None)
    if value is None:
        raise RuntimeError(f"downloader client {name} is unavailable")
    return value


def _read(value: Any, *names: str, default: Any = None) -> Any:
    """兼容字典、snake_case、camelCase 与连字符字段读取。"""
    for name in names:
        if isinstance(value, dict) and name in value:
            return value.get(name)
        getter = getattr(value, "get", None)
        if callable(getter):
            try:
                candidate = getter(name)
            except (KeyError, TypeError):
                candidate = None
            if candidate is not None:
                return candidate
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _split_labels(value: Any) -> list[str]:
    """把 qB tags 或 Transmission labels 拆成去重字符串列表。"""
    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = []
    result = []
    for item in raw_values:
        clean = str(item or "").strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def _completed_state(value: Any) -> bool:
    """判断 qB/TR 状态文本是否表示已完成或做种。"""
    normalized = str(getattr(value, "name", None) or value or "")
    normalized = normalized.replace("_", "").replace(" ", "").lower()
    return normalized in {
        "uploading",
        "forcedup",
        "stalledup",
        "pausedup",
        "stoppedup",
        "queuedup",
        "checkingup",
        "seeding",
        "seedpending",
        "completed",
    }


def _number(value: Any) -> float:
    """把任意数值安全转换为非负浮点数。"""
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _nonnegative_int(value: Any) -> int:
    """把任意数值安全转换为非负整数。"""
    return max(0, int(_number(value)))


def _timestamp(value: Any) -> float:
    """把 Unix 时间戳或 datetime 风格对象转换为秒。"""
    if hasattr(value, "timestamp"):
        try:
            return max(0.0, float(value.timestamp()))
        except (TypeError, ValueError, OSError):
            return 0.0
    return _number(value)


def _bps_to_kib(value: Any) -> int:
    """把 B/s 向上换算为 KiB/s，零值保持为零。"""
    bps = _nonnegative_int(value)
    return int(math.ceil(bps / 1024)) if bps > 0 else 0


__all__ = (
    "SUPPORTED_UPLOAD_LIMIT_TYPES",
    "TRANSMISSION_UPLOAD_ARGUMENTS",
    "expected_global_upload_settings",
    "expected_torrent_upload_settings",
    "global_settings_equal",
    "global_settings_from_dict",
    "global_settings_to_dict",
    "list_upload_torrents",
    "normalize_upload_torrent",
    "read_global_upload_settings",
    "restore_global_upload_settings",
    "restore_torrent_upload_settings",
    "settings_from_dict",
    "settings_to_dict",
    "torrent_settings_equal",
    "write_global_upload_limit",
    "write_torrent_upload_limit",
)
