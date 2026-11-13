"""MoviePilot 下载器、站点、HTTP 与系统配置访问适配器。"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

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
