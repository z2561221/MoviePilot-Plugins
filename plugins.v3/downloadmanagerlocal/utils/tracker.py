"""Tracker 域名映射解析工具"""

from typing import Dict


def parse_tracker_mappings(mapping_str: str) -> Dict[str, str]:
    """解析 tracker 域名映射字符串为 dict。

    格式：每行一条，`域名 -> 目标域名`。
    """
    mappings: Dict[str, str] = {}
    if not mapping_str:
        return mappings
    for line in mapping_str.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "->" in line:
            parts = line.split("->", 1)
            key = parts[0].strip()
            val = parts[1].strip()
            if key and val:
                mappings[key] = val
    return mappings
