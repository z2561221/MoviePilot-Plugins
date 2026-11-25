"""MoviePilot 下载器、站点、HTTP 与系统配置访问适配器。"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlsplit

from app.application.torrent.download import TorrentHelper
from app.chain.download import DownloadChain
from app.db.oper.downloadhistory import DownloadHistoryOper
from app.db.oper.site import SiteOper
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.sdk.media import TorrentInfo
from app.sdk.network import RequestUtils, SitesHelper
from app.sdk.services import DownloaderHelper
from app.sdk.utilities import StringUtils

try:
    from app.sdk.queries import (
        DownloadHistoryFilter,
        QueryPageRequest,
        list_download_history,
    )
except (ImportError, AttributeError):
    # 旧 V3 镜像尚未提供查询 SDK 时，保留已审查的 Oper 兼容路径。
    DownloadHistoryFilter = None
    QueryPageRequest = None
    list_download_history = None


DownloaderInstance = Qbittorrent | Transmission

PIECES_HASH_PATHS = {
    "pt.keepfrds.com": "/api/torrents/pieces-hash",
    "hhanclub.net": "/nexusapi/pieces-hash",
    "hhanclub.top": "/nexusapi/pieces-hash",
}
FLUX_SITE_NAMES = frozenset({"FluxTorrent", "好学"})


class SiteDownloadError(ValueError):
    """提供脱敏下载错误及站点请求冷却秒数。"""

    def __init__(self, message: str, cooldown: int):
        """保存调用方可执行的冷却期。"""
        super().__init__(message)
        self.cooldown = cooldown


def create_downloader_helper() -> DownloaderHelper:
    """创建 MoviePilot 下载器 helper。"""
    return DownloaderHelper()


def get_downloader_service(name: str):
    """按名称读取下载器服务信息。"""
    return create_downloader_helper().get_service(name)


def get_downloader_config(name: str):
    """按名称读取下载器配置对象。"""
    return create_downloader_helper().get_config(name)


def get_downloader_services(name_filters=None):
    """按名称过滤读取下载器服务信息。"""
    return create_downloader_helper().get_services(name_filters=name_filters)


def list_qb_completed_torrents(name: str) -> tuple[list[dict], bool]:
    """列出指定 qBittorrent 中正在做种的已完成任务。"""
    service = get_downloader_service(name)
    if not service or service.type != "qbittorrent":
        raise ValueError("请选择一个可用的 qBittorrent 下载器")
    if service.instance.is_inactive():
        raise ValueError("所选 qBittorrent 当前未连接")
    try:
        torrents, failed = service.instance.get_torrents()
    except Exception as error:
        raise RuntimeError("读取 qBittorrent 已完成任务失败") from error
    if failed:
        raise RuntimeError("读取 qBittorrent 已完成任务失败")
    items = []
    for torrent in torrents:
        torrent_hash = str(torrent.get("hash") or "").strip().lower()
        torrent_name = str(torrent.get("name") or "").strip()
        try:
            is_complete = float(torrent.get("progress") or 0) >= 1
        except (TypeError, ValueError):
            is_complete = False
        if torrent_hash and torrent_name and is_complete:
            items.append({"hash": torrent_hash, "name": torrent_name})
    items.sort(key=lambda item: item["name"].casefold())
    limit = 500
    return items[:limit], len(items) > limit


def export_qb_completed_torrent(name: str, torrent_hash: str) -> tuple[dict, bytes]:
    """复核已完成 qB 种子后通过导出 API 读取其 torrent 元数据。"""
    normalized_hash = str(torrent_hash or "").strip().lower()
    if len(normalized_hash) != 40 or any(char not in "0123456789abcdef" for char in normalized_hash):
        raise ValueError("种子 hash 格式不正确")
    service = get_downloader_service(name)
    if not service or service.type != "qbittorrent":
        raise ValueError("请选择一个可用的 qBittorrent 下载器")
    if service.instance.is_inactive():
        raise ValueError("所选 qBittorrent 当前未连接")
    try:
        torrents, failed = service.instance.get_torrents(ids=[normalized_hash])
    except Exception as error:
        raise RuntimeError("查询 qBittorrent 种子状态失败") from error
    if failed:
        raise RuntimeError("查询 qBittorrent 种子状态失败")
    torrent = next((item for item in torrents if str(item.get("hash") or "").lower() == normalized_hash), None)
    if not torrent:
        raise ValueError("所选种子已不在该 qBittorrent 中")
    try:
        progress = float(torrent.get("progress") or 0)
    except (TypeError, ValueError) as error:
        raise ValueError("无法确认所选种子是否已完成") from error
    if progress < 1:
        raise ValueError("只允许检查已完成的 qBittorrent 种子")
    try:
        content = service.instance.qbc.torrents_export(torrent_hash=normalized_hash)
    except Exception as error:
        raise RuntimeError("从 qBittorrent 导出 torrent 元数据失败") from error
    if not isinstance(content, bytes) or not content:
        raise RuntimeError("qBittorrent 未返回有效 torrent 元数据")
    return {"hash": normalized_hash, "name": str(torrent.get("name") or "")}, content


def is_downloader_type(downloader_type: str, service: Any) -> bool:
    """判断服务是否为指定下载器类型。"""
    return create_downloader_helper().is_downloader(downloader_type, service=service)


def generate_random_tag(length: int = 10) -> str:
    """生成下载器临时标签。"""
    return StringUtils.generate_random_str(length)


def get_url_domain(url: str) -> str:
    """提取 URL 域名。"""
    return StringUtils.get_url_domain(url)


def get_download_history_by_hash(torrent_hash: str):
    """优先通过查询 SDK 读取下载历史快照，旧镜像回退到 Oper。"""
    normalized_hash = str(torrent_hash or "").strip()
    if not normalized_hash:
        return None

    if list_download_history and DownloadHistoryFilter and QueryPageRequest:
        page = list_download_history(
            filters=DownloadHistoryFilter(download_hash=normalized_hash),
            page=QueryPageRequest(count=1),
        )
        items = getattr(page, "items", None) or []
        if items:
            return items[0]
        return None

    return DownloadHistoryOper().get_by_hash(normalized_hash)


def get_download_hash_by_fullpath(fullpath: str) -> str:
    """按媒体文件完整路径反查下载历史 hash。"""
    return DownloadHistoryOper().get_hash_by_fullpath(fullpath)


def list_builtin_sites() -> list:
    """读取 MoviePilot V3 站点数据库中的全部站点。"""
    return SiteOper().list_order_by_pri()


def _site_to_dict(site) -> dict:
    """把 MoviePilot 站点记录转换为插件内部使用的普通字典。"""
    if not site:
        return {}
    result = dict(getattr(site, "note", None) or {})
    for field in (
        "id",
        "name",
        "domain",
        "url",
        "pri",
        "rss",
        "cookie",
        "ua",
        "apikey",
        "token",
        "proxy",
        "render",
        "public",
        "is_active",
        "downloader",
    ):
        value = getattr(site, field, None)
        if value is not None:
            result[field] = value
    return result


def list_site_dicts() -> list[dict]:
    """读取 MoviePilot V3 统一站点记录的字典视图。"""
    return [_site_to_dict(site) for site in list_builtin_sites() if site]


def list_custom_site_dicts() -> list:
    """V3 站点已统一落库，不再返回独立的自定义站点集合。"""
    return []


def _get_site_by_domain(domain: str):
    """按规范域名查找 MoviePilot V3 站点记录。"""
    normalized = get_url_domain(domain) or str(domain or "").strip()
    if not normalized:
        return None
    site = SiteOper().get_by_domain(normalized)
    if site:
        return site
    for candidate in list_builtin_sites():
        candidate_domain = get_url_domain(
            getattr(candidate, "domain", None) or getattr(candidate, "url", None)
        )
        if candidate_domain == normalized:
            return candidate
    return None


def get_site_indexer(domain: str):
    """按域名合并站点索引模板与 V3 站点数据库凭据。"""
    indexer = SitesHelper().get_indexer(domain) or {}
    site = _get_site_by_domain(domain)
    if not site:
        return indexer or None
    return {**indexer, **_site_to_dict(site)}


def check_site(domain: str):
    """调用 MoviePilot 站点检查。"""
    return SitesHelper().check(domain)


def download_torrent_content(url: str, cookie=None, ua=None, proxy=None, site_id=None, site_name=""):
    """编码配方交由宿主取内容阶段换票，保留插件原有通知与错误处理。"""
    if url.startswith("["):
        torrent = TorrentInfo(enclosure=url, site=site_id, site_name=site_name,
                              site_cookie=cookie or "", site_ua=ua or "", site_proxy=bool(proxy),
                              title="IYUU辅种")
        # v3.2.6 的公共 download_torrent 会发送宿主失败通知；仅复用已核验
        # 的取内容阶段，避免绕过下载中心通知开关或添加资源下载历史。
        get_content = getattr(DownloadChain(), "_get_torrent_content", None)
        result = get_content(torrent) if callable(get_content) else None
        if result is None:
            return None, None, "", [], "换票失败：当前宿主无法获取配方内容"
        content, folder, files, error = result
        return None, content, folder, files, error
    return TorrentHelper().download_torrent(url=url, cookie=cookie, ua=ua, proxy=proxy)


def native_iyuu_site(site: dict) -> str:
    """仅识别本次已核验的新协议站点，不把普通 NexusPHP 模板当成 API。"""
    raw = str(site.get("url") or site.get("domain") or "").strip()
    host = (urlsplit(raw if "://" in raw else "https://" + raw).hostname or "").lower()
    if host in {"piggo.me", "www.piggo.me", "api.piggo.me"}:
        return "piggo"
    if host in {"hxpt.org", "www.hxpt.org"}:
        return "fluxtorrent"
    return ""


def native_iyuu_download_url(site: dict, torrent_id) -> str:
    """委托宿主站点适配生成下载配方；此步骤不请求网络或签发下载票据。"""
    tid = str(torrent_id or "")
    if not tid.isascii() or not tid.isdecimal() or tid.startswith("0"):
        raise ValueError("站内种子 ID 必须是正整数")
    if not (str(site.get("apikey") or "").strip() or str(site.get("token") or "").strip()):
        raise ValueError("站点未配置 API Key/Token")
    kind = native_iyuu_site(site)
    if kind == "piggo":
        from app.modules.indexer.spider.piggo import PiggoSpider
        return PiggoSpider(site).get_download_url(tid)
    if kind == "fluxtorrent":
        from app.modules.indexer.spider.fluxtorrent import FluxTorrentSpider
        normalized = dict(site, apikey=str(site.get("apikey") or "").strip())
        spider = FluxTorrentSpider(normalized)
        # v3.2.6 尚无公共生成方法；仅此已记录的旧宿主兼容入口。
        builder = getattr(spider, "get_download_url", None) or spider._build_download_url
        return builder(tid)
    raise ValueError("站点不属于本次 native 下载适配范围")


def request_get_res(url: str, params: dict | None = None, **kwargs):
    """通过 MoviePilot RequestUtils 发送 GET 请求。"""
    return RequestUtils(**kwargs).get_res(url=url, params=params)


def request_post_res(url: str, params: dict | None = None, json: dict | None = None, **kwargs):
    """通过 MoviePilot RequestUtils 发送 POST 请求。"""
    return RequestUtils(**kwargs).post_res(url, params=params, json=json)


def is_flux_site(site: dict) -> bool:
    """按青蛙助手的精确站名或开放 API 令牌前缀选择 Flux 协议。"""
    return str(site.get("name") or "").strip() in FLUX_SITE_NAMES or str(site.get("passkey") or "").strip().startswith("fxo_")


def pieces_hash_url(site: dict) -> str:
    """按站点当前域名选择 Pieces-hash 查询路径。"""
    base_url = str(site.get("url") or "").rstrip("/")
    if is_flux_site(site):
        return base_url + "/api/v1/crossseed/lookup"
    if site.get("name") == "憨憨":
        return base_url + "/nexusapi/pieces-hash"
    hostname = (urlsplit(base_url).hostname or "").lower().rstrip(".")
    path = PIECES_HASH_PATHS.get(hostname, "/api/pieces-hash")
    return base_url + path


def request_pieces_res(site: dict, fingerprints: list[str]):
    """仅向绑定站点提交 Pieces 凭据，禁止重定向转发。"""
    from app.sdk.config import settings

    user_agent = site.get("ua") or settings.USER_AGENT
    options = {"timeout": 25, "ua": user_agent, "verify": True,
               "proxies": settings.PROXY if site.get("proxy") else None,
               "content_type": "application/json", "accept_type": "application/json"}
    payload = {"passkey": site["passkey"], "pieces_hash": fingerprints}
    if is_flux_site(site):
        options["headers"] = {"Authorization": f"Token {site['passkey']}", "User-Agent": user_agent,
                              "Content-Type": "application/json", "Accept": "application/json"}
        payload = {"pieces_sha1": fingerprints}
    client = RequestUtils(**options)
    try:
        return client.post_res(
            pieces_hash_url(site),
            json=payload,
            allow_redirects=False,
        )
    finally:
        client.close()


def request_pieces_torrent(site: dict, torrent_id: str) -> bytes:
    """按站点协议下载元数据，Flux 临时下载跳转限定在原站点。"""
    from app.sdk.config import settings

    identity = str(torrent_id)
    if not identity.isascii() or not identity.isdecimal() or identity.startswith("0"):
        raise ValueError("站点返回了无效种子编号")
    flux = is_flux_site(site)
    user_agent = site.get("ua") or settings.USER_AGENT
    options = {"timeout": 25, "ua": user_agent, "verify": True,
               "proxies": settings.PROXY if site.get("proxy") else None}
    if flux:
        options["headers"] = {"Authorization": f"Token {site['passkey']}", "User-Agent": user_agent}
    else:
        options["cookies"] = site.get("cookie")
    client = RequestUtils(**options)
    base_url = site["url"].rstrip("/")
    target_url = base_url + (f"/api/v1/crossseed/dl/{identity}" if flux else "/download.php")
    origin = urlsplit(base_url)
    origin_port = origin.port or (443 if origin.scheme == "https" else 80)
    response = None
    try:
        for _redirect in range(4):
            parameters = {} if flux else {"params": {"id": identity, "passkey": site["passkey"]}}
            response = client.get_res(target_url, allow_redirects=False, **parameters)
            if response is not None and response.status_code == 429:
                from ..service.pieces import retry_after_seconds

                raise SiteDownloadError("种子下载触发站点限流，等待冷却", retry_after_seconds(response.headers))
            if flux and response is not None and response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                if not location:
                    raise SiteDownloadError("种子下载重定向缺少目标地址", 300)
                try:
                    next_url = urljoin(target_url, location)
                    parsed = urlsplit(next_url)
                    port = parsed.port or (443 if parsed.scheme == "https" else 80)
                except (TypeError, ValueError):
                    raise SiteDownloadError("种子下载重定向地址无效", 300) from None
                if (parsed.scheme != origin.scheme or parsed.hostname != origin.hostname or port != origin_port
                        or parsed.username or parsed.password or parsed.fragment):
                    raise SiteDownloadError("种子下载重定向超出站点范围", 300)
                response.close()
                response = None
                target_url = next_url
                continue
            if response is None or response.status_code != 200:
                raise SiteDownloadError("站点未返回可用种子文件，请检查下载权限或站点接口兼容性", 300)
            if not isinstance(response.content, bytes) or not response.content or len(response.content) > 16 * 1024 * 1024:
                raise ValueError("目标种子文件为空或超过大小限制")
            return response.content
        raise SiteDownloadError("种子下载重定向次数超限", 300)
    finally:
        if response is not None:
            response.close()
        client.close()
