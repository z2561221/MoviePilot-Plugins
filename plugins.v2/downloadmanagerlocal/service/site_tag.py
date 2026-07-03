"""站点标签服务边界，兼容委托到 legacy modules 实现。"""

from ..modules.site_tag import find_site_by_domain, tag_torrent

__all__ = ("find_site_by_domain", "tag_torrent")
