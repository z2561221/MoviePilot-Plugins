"""读取和验证已解包负载，不访问或修改宿主当前状态。"""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..model.backup import RestoreSelection
from ..model.restore import RestorePayloadPlan, RestoreServiceError
from .manifest_service import ManifestService


class RestorePayloadReader:
    """每次恢复解析一次所选 JSON，先验证全部目标 PluginData 行。"""

    @staticmethod
    def read_optional_json(path: Path) -> dict[str, Any] | None:
        """区分文件缺失与存在但为空。"""
        return ManifestService.read_json(path) if path.is_file() else None

    @staticmethod
    def validate_plugin_data(
        data: dict[str, Any], plugin_ids: Iterable[str]
    ) -> tuple[list[str], list[tuple[str, str, Any]]]:
        """只展开所选插件；显式空行列表仍属于需要替换的插件。"""
        included_ids: list[str] = []
        validated: list[tuple[str, str, Any]] = []
        for plugin_id in plugin_ids:
            if plugin_id not in data:
                continue
            rows = data.get(plugin_id)
            if not isinstance(rows, list):
                raise RestoreServiceError(f"插件数据格式无效：{plugin_id}")
            included_ids.append(plugin_id)
            for row in rows:
                if not isinstance(row, dict) or not str(row.get("key") or "").strip():
                    raise RestoreServiceError(f"插件数据项无效：{plugin_id}")
                validated.append((plugin_id, str(row["key"]), row.get("value")))
        return included_ids, validated

    @classmethod
    def load(
        cls, root: Path, selection: RestoreSelection, plugin_ids: Iterable[str]
    ) -> RestorePayloadPlan:
        """在安全解包和清单一致性校验之后建立本次独立规划。"""
        system_settings = cls.read_optional_json(root / "system_config.json") if selection.mp_settings else None
        plugin_configs = cls.read_optional_json(root / "plugin_configs.json") if selection.plugin_settings else None
        plugin_data = cls.read_optional_json(root / "plugin_data.json") if selection.plugin_data else None
        included_ids, rows = cls.validate_plugin_data(plugin_data or {}, plugin_ids)
        # 已验证行保留键和值即可，原始行字典及未选插件数据不跨恢复阶段存活。
        return RestorePayloadPlan(root, system_settings, plugin_configs, plugin_data is not None, tuple(included_ids), tuple(rows))
