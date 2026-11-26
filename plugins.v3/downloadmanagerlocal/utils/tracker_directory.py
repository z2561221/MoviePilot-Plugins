"""把 MP 的配置站点和模板别名投影为按完整域名边界查询的目录。"""

from collections import defaultdict
from urllib.parse import urlsplit


def tracker_host(value: str) -> str:
    """从 URL、裸域名或 host:port 提取规范主机名，不保留认证路径。"""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        host = urlsplit(text if "://" in text else "//" + text).hostname or ""
        return host.rstrip(".").encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError):
        return ""


def matching_domain(host, domains):
    """从精确主机逐级查找已登记父域，最具体的归属优先。"""
    while host:
        if host in domains:
            return host
        host = host.partition(".")[2]
    return None


def matching_site_domain(host, directory):
    """独立站点共用父域时，只认已登记的子域，不把未知子域全算作父站。"""
    key = matching_domain(host, directory)
    if (key and key != host and directory[key] is not None
            and any(child.endswith("." + key) and site != directory[key] for child, site in directory.items())):
        return None
    return key


def build_directory(sites, templates):
    """模板只用于关联已配置记录，空值保留未配置或不唯一的域名边界。"""
    template_ids = {tracker_host(domain): item.get("id") for domain, item in templates.items()
                    if domain and isinstance(item, dict) and item.get("id")}
    configured = defaultdict(set)
    by_template = defaultdict(set)
    for position, (name, domain, url) in enumerate(sites):
        entry = (position, str(name or "").strip())
        hosts = {host for value in (domain, url) if (host := tracker_host(value))}
        for host in hosts:
            configured[host].add(entry)
        identities = {template_ids[key] for host in hosts if (key := matching_domain(host, template_ids))}
        if len(identities) == 1:
            by_template[identities.pop()].add(entry)
    for domain, identity in template_ids.items():
        configured.setdefault(domain, by_template[identity])
    return {domain: (next(iter(entries))[1] or None) if len(entries) == 1 else None
            for domain, entries in configured.items()}


def normalized_aliases(mappings):
    """规范化兜底映射，允许用户以大小写、尾点或端口书写同一主机。"""
    return {source: target for key, value in mappings.items()
            if (source := tracker_host(key)) and (target := tracker_host(value))}


def resolve_tracker(host, directory, custom, builtin):
    """原域名由 MP 决定；未知才选择一层别名，并要求目标也在 MP 唯一归属。"""
    direct = matching_site_domain(host, directory)
    if direct is not None:
        return directory[direct]
    for mappings in (custom, builtin):
        if key := matching_domain(host, mappings):
            return directory.get(matching_site_domain(mappings[key], directory))
    return None
