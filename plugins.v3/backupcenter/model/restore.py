"""本次已解包恢复负载的规划模型。"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RestoreServiceError(RuntimeError):
    """表示恢复预检、兼容性或写入失败。"""


@dataclass(frozen=True)
class RestorePayloadPlan:
    """配置缺失用 None；数据保留文件存在性、目标身份和已验证行。"""

    root: Path
    system_settings: dict[str, Any] | None
    plugin_configs: dict[str, Any] | None
    plugin_data_present: bool
    data_plugin_ids: tuple[str, ...]
    data_rows: tuple[tuple[str, str, Any], ...]
