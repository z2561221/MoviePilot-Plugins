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
security = ModuleType("app.sdk.security")
security.verify_token = lambda: SimpleNamespace(super_user=True, sub="1")
sys.modules["app.sdk.security"] = security
sdk.security = security
