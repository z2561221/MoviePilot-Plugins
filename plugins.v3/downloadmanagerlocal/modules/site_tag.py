"""站点标签 legacy 兼容 shim，业务实现位于 service.site_tag。"""

from ..service.site_tag import find_site_by_domain, tag_torrent

__all__ = ("find_site_by_domain", "tag_torrent")
