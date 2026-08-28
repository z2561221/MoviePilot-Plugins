"""榜单业务流水线的旧路径兼容门面。"""

import sys

from .service import rank_pipeline as _pipeline


sys.modules[__name__] = _pipeline
