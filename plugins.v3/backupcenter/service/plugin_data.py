"""规范化宿主公开插件数据接口返回的记录。"""

from collections.abc import Mapping
from typing import Any, List, Tuple


def normalize_plugin_data_rows(records: Any, plugin_id: str) -> List[Tuple[str, Any]]:
    """将映射或宿主数据对象转换为稳定的键值元组列表。"""
    if isinstance(records, Mapping):
        source = records.items()
    else:
        source = (
            (
                record.get("key") if isinstance(record, Mapping) else getattr(record, "key", None),
                record.get("value")
                if isinstance(record, Mapping)
                else getattr(record, "value", None),
            )
            for record in records or []
        )
    result: List[Tuple[str, Any]] = []
    for key, value in source:
        if not str(key or "").strip():
            raise ValueError(f"插件数据记录无效：{plugin_id}")
        result.append((str(key), value))
    return result
