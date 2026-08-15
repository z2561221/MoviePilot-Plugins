"""敏感信息脱敏工具。"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SENSITIVE_QUERY_KEYS = {
    "apikey",
    "api_key",
    "auth",
    "authkey",
    "passkey",
    "rsskey",
    "token",
    "uid",
}


def mask_sensitive_url(url: str) -> str:
    """隐藏 URL 查询参数中的 PT 私密令牌。"""
    if not url:
        return url
    try:
        parts = urlsplit(str(url))
    except Exception:
        return url
    if not parts.query:
        return str(url)
    masked = []
    changed = False
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in SENSITIVE_QUERY_KEYS:
            masked.append((key, "***"))
            changed = True
        else:
            masked.append((key, value))
    if not changed:
        return str(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(masked, doseq=True, safe="*"), parts.fragment))
