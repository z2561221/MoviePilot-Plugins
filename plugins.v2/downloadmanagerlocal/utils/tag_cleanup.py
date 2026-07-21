"""下载器标签清理的纯判断工具。"""

import re
from typing import Dict, Iterable, Set


TEMP_TAG_PREFIX = "DML_TMP_"
LEGACY_TEMP_TAG_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")


def normalize_tags(values: Iterable[str]) -> Set[str]:
    """将标签序列标准化为非空字符串集合。"""
    if isinstance(values, str):
        values = values.split(",")
    return {str(value).strip() for value in values or [] if str(value).strip()}


def classify_tag(
    tag: str,
    hashes: Iterable[str],
    torrent_tags_by_hash: Dict[str, Set[str]],
    managed_tags: Set[str],
    active_tags: Set[str],
    site_prefix: str = "",
) -> str:
    """按归属证据将单个标签分类。"""
    tag_text = str(tag or "").strip()
    hash_set = normalize_tags(hashes)
    if tag_text in active_tags:
        return "active_temporary"
    if tag_text.startswith(TEMP_TAG_PREFIX):
        return "temporary"
    if (
        LEGACY_TEMP_TAG_PATTERN.fullmatch(tag_text)
        and len(hash_set) == 1
        and any(
            (torrent_tags_by_hash.get(torrent_hash, set()) - {tag_text}) & managed_tags
            for torrent_hash in hash_set
        )
    ):
        return "legacy_temporary"
    if site_prefix and tag_text.startswith(site_prefix):
        return "site"
    if tag_text in managed_tags:
        return "managed"
    return "other"


def is_auto_removable(kind: str) -> bool:
    """判断标签分类是否具备自动清理所需的归属证据。"""
    return kind in {"temporary", "legacy_temporary"}


__all__ = (
    "LEGACY_TEMP_TAG_PATTERN",
    "TEMP_TAG_PREFIX",
    "classify_tag",
    "is_auto_removable",
    "normalize_tags",
)
