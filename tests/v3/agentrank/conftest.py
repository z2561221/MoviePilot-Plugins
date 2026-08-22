"""AgentRank V3 聚焦测试的轻量包与宿主鉴权桩。"""

import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType, SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"

package = sys.modules.setdefault("agentrank", ModuleType("agentrank"))
package.__path__ = [str(PLUGIN_DIR)]

try:
    sdk = import_module("app.sdk")
except ModuleNotFoundError:
    app_module = sys.modules.setdefault("app", ModuleType("app"))
    sdk = ModuleType("app.sdk")
    sdk.__path__ = []
    sys.modules["app.sdk"] = sdk
    app_module.sdk = sdk
app_module = sys.modules.setdefault("app", ModuleType("app"))
api = sys.modules.setdefault("app.api", ModuleType("app.api"))
api.__path__ = []
endpoints = sys.modules.setdefault("app.api.endpoints", ModuleType("app.api.endpoints"))
endpoints.__path__ = []
host_plugin = ModuleType("app.api.endpoints.plugin")
host_plugin.verify_token = lambda: SimpleNamespace(super_user=True, sub="1")
sys.modules["app.api.endpoints.plugin"] = host_plugin
endpoints.plugin = host_plugin
api.endpoints = endpoints
app_module.api = api
