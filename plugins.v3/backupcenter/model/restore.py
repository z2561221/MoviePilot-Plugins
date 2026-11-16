"""本次已解包恢复负载的规划模型。"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RestoreServiceError(RuntimeError):
    """表示恢复预检、兼容性或写入失败。"""


@dataclass(frozen=True)
class RestorePayloadPlan:
    """缺失 JSON 用 None 表示；空对象与显式空插件数据仍保留。"""

    root: Path
    system_settings: dict[str, Any] | None
    plugin_configs: dict[str, Any] | None
    plugin_data: dict[str, Any] | None
    data_plugin_ids: tuple[str, ...]
    data_rows: tuple[tuple[str, str, Any], ...]
