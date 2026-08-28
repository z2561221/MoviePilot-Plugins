"""AgentRank 经审查的 MoviePilot V3 宿主兼容入口。

``SYSTEM_INTERNAL_USER_ID`` 在当前 V3 宿主仍只由
``app.foundation.identity`` 提供，``app.sdk`` 尚无等价导出。AgentRank 需要该身份
隔离内部 Agent 会话和记忆，因此暂时保留这一项符号级允许清单；当稳定 SDK 导出后
应删除本模块中的内部导入，并由契约测试阻止其它内部路径扩散。
"""

# Reviewed against MoviePilot V3 origin/v3 on 2026-08-29.
from app.foundation.identity import SYSTEM_INTERNAL_USER_ID

__all__ = ["SYSTEM_INTERNAL_USER_ID"]
