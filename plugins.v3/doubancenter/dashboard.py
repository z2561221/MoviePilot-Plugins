"""仪表盘业务的旧路径兼容门面。"""

import sys

from .service import dashboard as _dashboard


sys.modules[__name__] = _dashboard
