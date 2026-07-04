"""Torrent rename text cleanup helpers."""

from __future__ import annotations

import re


_BRACKET_PREFIX_RE = re.compile(r"\[.*?\][\s.]*")
_LEADING_BRACKET_PREFIX_RE = re.compile(r"^\s*\[[^\]]+\]\s*(?:-\s*)*")
_LEADING_RENAME_SEPARATOR_RE = re.compile(r"^(?:-\s*)+")
_TORRENT_SUFFIX_RE = re.compile(r"\.torrent$", re.IGNORECASE)
_SUBTITLE_SEPARATOR_RE = re.compile(r"\s+\|\s+")
_TRAILING_SOURCE_RE = re.compile(r"\s*\*[^*]+\*\s*$")
_RELEASE_MARKER_RE = re.compile(
    r"(?:S\d{1,2}E\d{1,3}|2160p|1080p|720p|WEB[-_. ]?DL|BluRay|H\.?26[45]|HEVC|AVC|AAC)",
    re.IGNORECASE,
)
_GROUP_THEN_CHINESE_RE = re.compile(
    r"^(.+?-[A-Za-z][A-Za-z0-9._-]{1,32})(?=[\u4e00-\u9fff])([\s\S]+)$"
)
_GROUP_SITE_BRACKET_CHINESE_RE = re.compile(
    r"^(.+?-[A-Za-z][A-Za-z0-9._-]{1,32}(?:@[A-Za-z][A-Za-z0-9._-]{1,32})?)\s*\[([^\]]*[\u4e00-\u9fff][^\]]*)\]\s*$"
)
_GROUP_SITE_SUBTITLE_BLOCK_RE = re.compile(
    r"^(.+?-[A-Za-z][A-Za-z0-9._-]{1,32}(?:@[A-Za-z][A-Za-z0-9._-]{1,32})?)\s*\[([\s\S]*)$"
)
_CHINESE_SUBTITLE_HINT_RE = re.compile(
    r"[\u4e00-\u9fff].*(?:第\s*\d+\s*[集季]|类型[:：]|主演[:：]|别名[:：]|酷喵TV|字幕|双语|中字|Season\s*\d+|/)"
)
_POLLUTION_HINT_RE = re.compile(
    r"(?:\s+\|\s+|类型[:：]|主演[:：]|别名[:：]|酷喵TV|第\s*\d+\s*集)"
)


def extract_release_name(value: str) -> str:
    """提取用于最终命名的发布名，并舍弃站点副标题说明区。"""
    if not value:
        return ""

    cleaned = str(value).strip()
    while True:
        next_cleaned = _LEADING_BRACKET_PREFIX_RE.sub("", cleaned).strip()
        next_cleaned = _LEADING_RENAME_SEPARATOR_RE.sub("", next_cleaned).strip()
        if next_cleaned == cleaned:
            break
        cleaned = next_cleaned
    cleaned = _TORRENT_SUFFIX_RE.sub("", cleaned).strip(" .")

    if _RELEASE_MARKER_RE.search(cleaned):
        match = _GROUP_SITE_SUBTITLE_BLOCK_RE.match(cleaned)
        if match and _CHINESE_SUBTITLE_HINT_RE.search(match.group(2)):
            return match.group(1).strip()
        match = _GROUP_SITE_BRACKET_CHINESE_RE.match(cleaned)
        if match and _CHINESE_SUBTITLE_HINT_RE.search(match.group(2)):
            cleaned = match.group(1).strip()
        match = _GROUP_THEN_CHINESE_RE.match(cleaned)
        if match and _CHINESE_SUBTITLE_HINT_RE.search(match.group(2)):
            cleaned = match.group(1).strip()

    cleaned = _SUBTITLE_SEPARATOR_RE.split(cleaned, 1)[0].strip()
    cleaned = _TRAILING_SOURCE_RE.sub("", cleaned).strip()
    return cleaned


def clean_torrent_original_name(value: str) -> str:
    """返回去除 MoviePilot 或豆瓣副标题污染后的发布名。"""
    return extract_release_name(value)


def is_polluted_original_name(value: str) -> bool:
    """判断候选原始名是否包含副标题、类型、主演等污染信息。"""
    text = str(value or "").strip()
    if not text:
        return False
    cleaned = clean_torrent_original_name(text)
    return cleaned != text or bool(_POLLUTION_HINT_RE.search(text))


def _extract_original_part(renamed_name: str) -> str:
    """从插件重命名格式中提取原始发布名部分。"""
    match = re.match(r"^\s*\[[^\]]+\]\s*-\s*(.+)$", str(renamed_name or "").strip())
    return match.group(1).strip() if match else str(renamed_name or "").strip()


def is_dirty_renamed_torrent_name(value: str) -> bool:
    """判断已重命名种子的原始名部分是否仍含副标题污染。"""
    original_part = _extract_original_part(value).strip()
    if not original_part:
        return False
    if clean_torrent_original_name(original_part) != original_part:
        return True
    trimmed_part = original_part.rstrip(" ]")
    return bool(trimmed_part) and clean_torrent_original_name(trimmed_part) != trimmed_part


def collect_retry_rename_hashes(records: dict) -> set:
    """收集需要补刮的失败记录和脏名称成功记录 hash。"""
    retry_hashes = set()
    for torrent_hash, record in (records or {}).items():
        if not isinstance(record, dict):
            continue
        if not record.get("success") or is_dirty_renamed_torrent_name(record.get("after_name", "")):
            retry_hashes.add(torrent_hash)
    return retry_hashes
