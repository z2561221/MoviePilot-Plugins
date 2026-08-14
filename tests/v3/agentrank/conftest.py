"""AgentRank V3 聚焦测试的轻量包与宿主鉴权桩。"""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"

package = sys.modules.setdefault("agentrank", ModuleType("agentrank"))
package.__path__ = [str(PLUGIN_DIR)]

security = ModuleType("app.core.security")
security.verify_token = lambda: SimpleNamespace(super_user=True, sub="1")
sys.modules.setdefault("app.core.security", security)
