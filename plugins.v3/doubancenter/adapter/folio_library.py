"""按实际播放身份读取媒体库季海报，原始档案继续保留外部海报回退。"""

import io
import re
import time
from collections.abc import Mapping
from urllib.parse import urlencode, urlparse

from app.sdk.logging import logger
from app.sdk.media import resolve_media_identity
from app.sdk.network import RequestUtils, SecurityUtils, UrlUtils
from app.sdk.services import MediaServerHelper
from PIL import Image

from ..model import folio_record

CACHE_SECONDS = 300
MISS_CACHE_SECONDS = 60
CACHE_LIMIT = 256
_PROVIDERS = {
    "themoviedb": "tmdb", "douban": "douban", "thetvdb": "tvdb",
    "imdb": "imdb", "bangumi": "bangumi",
}


def playback_context(event_info) -> dict:
    """保留事件的服务器及条目 ID，不把播放季号当作 SeasonId。"""
    payload = getattr(event_info, "json_object", None)
    if not isinstance(payload, Mapping):
        return {}
    item = payload.get("Item")
    if not isinstance(item, Mapping):
        return {}
    server = getattr(event_info, "server_name", None) or payload.get("source")
    series_id = item.get("SeriesId") or getattr(event_info, "item_id", None)
    if not server or not _item_id(series_id):
        return {}
    return {
        "server": str(server), "series_id": str(series_id),
        "season_id": _item_id(item.get("SeasonId")),
    }


def _item_id(value) -> str:
    """只接受可作为媒体服务器路径段的条目 ID。"""
    value = str(value or "")
    return value if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) else ""


def _base_url(service) -> str:
    """从已启用服务配置构造不携带凭据的图片源地址。"""
    config = service.config.config or {}
    base = UrlUtils.standardize_base_url(str(config.get("host") or ""))
    parsed = urlparse(base)
    if (parsed.scheme not in {"http", "https"} or not parsed.netloc
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        return ""
    return base


def _get_json(service, path: str, params: dict, memo: dict):
    """在单次投影内复用查询，认证只放请求头且限制请求耗时。"""
    key = (service.name, path, tuple(sorted(params.items())))
    if key not in memo:
        base = _base_url(service)
        apikey = (service.config.config or {}).get("apikey")
        if not base or not apikey:
            return None
        response = RequestUtils(timeout=5, headers={"X-Emby-Token": apikey}).get_res(
            base + path, params=params, allow_redirects=False,
        )
        data = response.json() if response is not None and response.status_code == 200 else None
        memo[key] = data if isinstance(data, dict) else None
    return memo[key]


def _series_match(item: dict, provider: str, media_id: str) -> bool:
    """按来源 ID 核验整剧，不按同名标题或豆瓣分段编号猜测。"""
    providers = item.get("ProviderIds") or {}
    return (item.get("Type") == "Series" and bool(_item_id(item.get("Id")))
            and isinstance(providers, Mapping)
            and any(str(key).casefold() == provider and str(value) == media_id
                    for key, value in providers.items()))


def _find_series(services: list, origin: dict, reference: dict, memo: dict):
    """精确查询播放条目或唯一源身份；重复版本及未知查询结果均保留回退。"""
    source, media_id = resolve_media_identity(
        media_source=origin.get("media_source"), media_id=origin.get("media_id"),
    )
    provider = _PROVIDERS.get(getattr(source, "value", source))
    if not provider or not media_id:
        return None
    if reference:
        services = [service for service in services if service.name == reference.get("server")]
        if not _item_id(reference.get("series_id")):
            return None
    matches = []
    for service in services:
        params = {"Recursive": "true", "IncludeItemTypes": "Series", "Fields": "ProviderIds", "Limit": 2}
        if reference:
            params["Ids"] = reference["series_id"]
        else:
            params["AnyProviderIdEquals"] = f"{provider}.{media_id}"
        data = _get_json(service, "Items", params, memo)
        if data is None or not isinstance(data.get("Items"), list):
            return None
        items = data["Items"]
        if int(data.get("TotalRecordCount", len(items))) > 1 or len(items) > 1:
            return None
        for item in items:
            if (isinstance(item, dict) and _series_match(item, provider, str(media_id))
                    and (not reference or str(item["Id"]) == reference["series_id"])):
                matches.append((service, item))
    return matches[0] if len(matches) == 1 else None


def _valid_image(url: str) -> bool:
    """确认无密钥图片地址返回有效位图，避免给页面返回登录页或失效图片。"""
    response = RequestUtils(timeout=5).get_res(url, allow_redirects=False)
    if response is None or response.status_code != 200:
        return False
    content = response.content
    if not content or len(content) > 8 * 1024 * 1024:
        return False
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        return True
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        return False


def _lookup_poster(services: list, origin: dict, memo: dict):
    """读取匹配季的 Primary 图片，拒绝整剧图、单集截图及错父级条目。"""
    reference = origin.get("mediaserver") or {}
    if not isinstance(reference, dict):
        return None
    match = _find_series(services, origin, reference, memo)
    if not match:
        return None
    service, series = match
    series_id = str(series["Id"])
    data = _get_json(service, f"Shows/{series_id}/Seasons", {"Fields": "ProviderIds"}, memo)
    if data is None or not isinstance(data.get("Items"), list):
        return None
    if int(data.get("TotalRecordCount", len(data["Items"]))) > len(data["Items"]):
        return None
    season_number = int(origin["season"])
    matches = [item for item in data["Items"] if isinstance(item, dict)
               and item.get("Type") == "Season" and str(item.get("SeriesId")) == series_id
               and str(item.get("IndexNumber")) == str(season_number)
               and (not reference.get("season_id") or str(item.get("Id")) == reference["season_id"])]
    if len(matches) != 1:
        return None
    season = matches[0]
    season_id = _item_id(season.get("Id"))
    image_tag = (season.get("ImageTags") or {}).get("Primary")
    if not season_id or not image_tag:
        return None
    url = _base_url(service) + f"Items/{season_id}/Images/Primary?" + urlencode({
        "tag": image_tag, "maxWidth": 400,
    })
    if not _valid_image(url):
        return None
    return {"url": url, "reference": {
        "server": service.name, "series_id": series_id, "season_id": season_id,
        "season": season_number, "image_tag": str(image_tag),
    }}


def _season_episodes(service, series_id: str, season_id: str, number: int, memo: dict) -> list:
    """消费完整季的分页结果，缺页、错父级或重复条目均不能充当分季依据。"""
    episodes, seen = [], set()
    while len(episodes) < 10000:
        data = _get_json(service, f"Shows/{series_id}/Episodes", {
            "SeasonId": season_id, "Fields": "ProviderIds", "StartIndex": len(episodes), "Limit": 200,
        }, memo)
        if not isinstance(data, dict) or not isinstance(data.get("Items"), list):
            return []
        items = data["Items"]
        total = data.get("TotalRecordCount")
        if not isinstance(total, int) or total <= 0 or not items:
            return []
        for item in items:
            if (not isinstance(item, dict) or item.get("Type") != "Episode"
                    or str(item.get("SeriesId")) != series_id or str(item.get("SeasonId")) != season_id
                    or str(item.get("ParentIndexNumber")) != str(number)
                    or not _item_id(item.get("Id")) or item["Id"] in seen
                    or not isinstance(item.get("IndexNumber"), int)):
                return []
            seen.add(item["Id"])
            episodes.append(item)
        if len(episodes) == total:
            return episodes
        if len(episodes) > total:
            return []
    return []


def load_season(plugin, origin: dict, *, refresh: bool = False) -> dict | None:
    """读取实际入库分季，外部剧集组不参与季号解释；按插件实例短期缓存。"""
    try:
        services = list(MediaServerHelper().get_services(type_filter="emby").values())
        service_key = tuple((service.name, _base_url(service)) for service in services)
        reference = origin.get("mediaserver") or {}
        key = (str(origin.get("media_source")), str(origin.get("media_id")), str(origin.get("season")),
               folio_record.fingerprint(reference), service_key)
        cache = getattr(plugin, "_folio_library_season_cache", {})
        now = time.monotonic()
        cache = {item: value for item, value in cache.items() if value[0] > now}
        if not refresh and key in cache:
            return cache[key][1]
        memo = {}
        match = _find_series(services, origin, reference, memo)
        if not match:
            return None
        service, series = match
        series_id = str(series["Id"])
        data = _get_json(service, f"Shows/{series_id}/Seasons", {"Fields": "ProviderIds"}, memo)
        if (not isinstance(data, dict) or not isinstance(data.get("Items"), list)
                or data.get("TotalRecordCount", len(data["Items"])) != len(data["Items"])):
            return None
        number = int(origin["season"])
        seasons = [item for item in data["Items"] if isinstance(item, dict)
                   and item.get("Type") == "Season" and str(item.get("SeriesId")) == series_id
                   and str(item.get("IndexNumber")) == str(number)
                   and (not reference.get("season_id") or str(item.get("Id")) == reference["season_id"])]
        if len(seasons) != 1 or not _item_id(seasons[0].get("Id")):
            return None
        season = seasons[0]
        season_id = str(season["Id"])
        episodes = [item for item in _season_episodes(service, series_id, season_id, number, memo)
                    if not item.get("IsVirtualItem") and item.get("LocationType") != "Virtual"]
        if not episodes:
            return None
        entries = sorted([{"episode": item["IndexNumber"], "air_date": str(item.get("PremiereDate") or "")[:10]}
                          for item in episodes], key=lambda item: item["episode"])
        if not entries[0]["air_date"]:
            return None
        result = {
            "reference": {"server": service.name, "series_id": series_id, "season_id": season_id},
            "season": number, "episode_count": len({item["episode"] for item in entries}),
            "episode_numbers": sorted({item["episode"] for item in entries}),
            "air_date": entries[0]["air_date"], "episodes": entries,
            "name": str(season.get("Name") or ""), "basis": "mediaserver",
        }
        if len(cache) >= CACHE_LIMIT:
            cache.pop(next(iter(cache)))
        cache[key] = (now + CACHE_SECONDS, result)
        plugin._folio_library_season_cache = cache
        return result
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as err:
        logger.debug(f"实际媒体库分季不可用：{type(err).__name__}")
        return None


def bind_season(origin: dict, season: dict) -> dict:
    """将来源身份绑定到已读取的库内季，清除未经播放器确认的外部分组。"""
    return {**origin, "season": season["season"], "episode_group": "",
            "mediaserver": dict(season["reference"]), "library_season": dict(season)}


def _eligible(record: dict) -> bool:
    """旧档案必须具备已核验的播放季，缺少依据时继续使用原海报。"""
    if not isinstance(record, dict):
        return False
    origin = record.get("origin")
    return (record.get("identity_status") == "verified" and isinstance(origin, dict)
            and folio_record.media_kind(record.get("type")) == "tv"
            and folio_record.media_kind(origin.get("type")) == "tv"
            and origin.get("season") is not None and bool(folio_record.origin_key(origin)))


def project_posters(plugin, records: dict) -> dict:
    """只读替换时间线展示图片，按实例短期缓存并保留原档案及缺图回退。"""
    eligible = {key: record for key, record in records.items() if _eligible(record)}
    if not eligible:
        return records
    try:
        services = list(MediaServerHelper().get_services(type_filter="emby").values())
        service_key = tuple((service.name, _base_url(service)) for service in services)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as err:
        logger.debug(f"媒体库季海报服务不可用：{type(err).__name__}")
        return records
    if not services:
        return records
    now = time.monotonic()
    cache = getattr(plugin, "_folio_library_poster_cache", {})
    cache = {key: value for key, value in cache.items() if value[0] > now}
    memo, result = {}, dict(records)
    for key, record in eligible.items():
        origin = record["origin"]
        cache_key = (folio_record.fingerprint(origin), service_key)
        if cache_key not in cache:
            try:
                poster = _lookup_poster(services, origin, memo)
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as err:
                logger.debug(f"媒体库季海报查询失败，使用档案海报：{type(err).__name__}")
                poster = None
            if len(cache) >= CACHE_LIMIT:
                cache.pop(next(iter(cache)))
            cache[cache_key] = (now + (CACHE_SECONDS if poster else MISS_CACHE_SECONDS), poster)
        poster = cache[cache_key][1]
        if poster:
            image_url = SecurityUtils.sign_url(poster["url"])
            result[key] = {
                **record,
                "poster_path": "/api/v1/system/img/0?" + urlencode({"imgurl": image_url, "cache": "true"}),
                "poster_source": "mediaserver", "poster_fallback_path": record.get("poster_path") or "",
                "library_poster": dict(poster["reference"]),
            }
    plugin._folio_library_poster_cache = cache
    return result
