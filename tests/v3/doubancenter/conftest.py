"""DoubanCenter V3 测试的生产命名空间引导。"""

import sys
from pathlib import Path


def pytest_configure():
    """把 V3 插件目录挂入 ``app.plugins``，保持生产导入身份。"""
    import app.plugins
    from app.application.configuration import SystemConfigService, configure_system_config
    from app.db.oper.systemconfig import SystemConfigOper
    from app.db.session import SessionFactory

    plugin_root = Path(__file__).resolve().parents[3] / "plugins.v3"
    if str(plugin_root) not in app.plugins.__path__:
        app.plugins.__path__.append(str(plugin_root))
    sys.modules.pop("doubancenter", None)

    system_config = SystemConfigOper()
    with SessionFactory() as session:
        system_config.load_snapshot(session)
    configure_system_config(SystemConfigService(repository=system_config))
