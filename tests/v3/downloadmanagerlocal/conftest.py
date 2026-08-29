"""下载中心 V3 测试的生产命名空间引导。"""

from pathlib import Path


def pytest_configure():
    """把 V3 插件目录挂入 ``app.plugins``，保持生产导入身份。"""
    import app.plugins

    plugin_root = Path(__file__).resolve().parents[3] / "plugins.v3"
    if str(plugin_root) not in app.plugins.__path__:
        app.plugins.__path__.append(str(plugin_root))
