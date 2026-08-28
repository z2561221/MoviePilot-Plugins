"""AgentRank V3 测试使用宿主运行时一致的插件模块命名空间。"""

import importlib.util
import sys
from pathlib import Path

from tests._bootstrap import prepare_v3_backend


prepare_v3_backend()

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"
MODULE_NAME = "app.plugins.agentrank"

if MODULE_NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        MODULE_NAME,
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法创建 AgentRank V3 生产命名空间模块")
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
