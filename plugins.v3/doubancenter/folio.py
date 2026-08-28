"""豆瓣档案业务的旧路径兼容门面。"""

import sys

from .service import folio as _folio


sys.modules[__name__] = _folio
