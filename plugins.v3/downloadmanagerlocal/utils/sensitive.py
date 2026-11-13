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
    """隐藏下载配方中的认证配置和 URL 查询参数中的 PT 私密令牌。"""
    if not url:
        return url
    prefix = ""
    value = str(url)
    if value.startswith("["):
        end = value.find("]")
        if end < 0:
            return "[下载配方已隐藏]"
        prefix, value = "[下载配方已隐藏]", value[end + 1:]
    try:
        parts = urlsplit(value)
    except Exception:
        return prefix + "[地址无法解析]"
    if not parts.query:
        return prefix + value
    masked = []
    changed = False
    for key, query_value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in SENSITIVE_QUERY_KEYS:
            masked.append((key, "***"))
            changed = True
        else:
            masked.append((key, query_value))
    if not changed:
        return prefix + value
    return prefix + urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(masked, doseq=True, safe="*"), parts.fragment))
