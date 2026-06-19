"""Torrent rename text cleanup helpers."""

from __future__ import annotations

import re


_BRACKET_PREFIX_RE = re.compile(r"\[.*?\][\s.]*")
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
_CHINESE_SUBTITLE_HINT_RE = re.compile(
    r"[\u4e00-\u9fff].*(?:第\s*\d+\s*集|类型[:：]|主演[:：]|别名[:：]|酷喵TV)"
)


def clean_torrent_original_name(value: str) -> str:
    """Return a release name without MoviePilot/Douban subtitle details."""
    if not value:
        return ""

    cleaned = str(value).strip()
    cleaned = _BRACKET_PREFIX_RE.sub("", cleaned)
    cleaned = _LEADING_RENAME_SEPARATOR_RE.sub("", cleaned).strip()
    cleaned = _TORRENT_SUFFIX_RE.sub("", cleaned).strip(" .")
    cleaned = _SUBTITLE_SEPARATOR_RE.split(cleaned, 1)[0].strip()
    cleaned = _TRAILING_SOURCE_RE.sub("", cleaned).strip()

    if _RELEASE_MARKER_RE.search(cleaned):
        match = _GROUP_THEN_CHINESE_RE.match(cleaned)
        if match and _CHINESE_SUBTITLE_HINT_RE.search(match.group(2)):
            cleaned = match.group(1).strip()

    return cleaned


def _extract_original_part(renamed_name: str) -> str:
    match = re.match(r"^\s*\[[^\]]+\]\s*-\s*(.+)$", str(renamed_name or "").strip())
    return match.group(1).strip() if match else str(renamed_name or "").strip()


def is_dirty_renamed_torrent_name(value: str) -> bool:
    """Whether a renamed torrent still contains subtitle details in original_name."""
    original_part = _extract_original_part(value).rstrip(" ]")
    return bool(original_part) and clean_torrent_original_name(original_part) != original_part


def collect_retry_rename_hashes(records: dict) -> set:
    """Return hashes that should be retried: failures plus dirty successful renames."""
    retry_hashes = set()
    for torrent_hash, record in (records or {}).items():
        if not isinstance(record, dict):
            continue
        if not record.get("success") or is_dirty_renamed_torrent_name(record.get("after_name", "")):
            retry_hashes.add(torrent_hash)
    return retry_hashes
