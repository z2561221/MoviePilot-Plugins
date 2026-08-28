"""插件仓 V3 代际同步、导入与发布映射测试。"""

import ast
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.sync_to_mp_local import sync_to_target  # noqa: E402


V3_PLUGIN_ROOT = REPO_ROOT / "plugins.v3" / "doubancenter"
FORBIDDEN_IMPORT_ROOTS = (
    "app.sdk._legacy",
    "app.core",
    "app.helper",
    "app.utils",
    "app.log",
    "app.application",
    "app.domain",
    "app.foundation",
    "app.adapters",
    "app.runtime",
)
REVIEWED_INTERNAL_IMPORTS = {"app.adapters.external.cookiecloud"}
LEGACY_DB_IMPORTS = {"app.db.subscribe_oper", "app.db.subscribehistory_oper"}


def _is_forbidden_import(module_name: str) -> bool:
    """判断模块名是否命中禁止路径且不在已审查允许清单。"""
    if module_name in LEGACY_DB_IMPORTS:
        return True
    if module_name in REVIEWED_INTERNAL_IMPORTS:
        return False
    return any(
        module_name == root or module_name.startswith(f"{root}.")
        for root in FORBIDDEN_IMPORT_ROOTS
    )


def test_v3_plugin_does_not_use_unreviewed_internal_import_paths():
    """V3 源码不能使用未审查的宿主旧路径或内部目录。"""
    violations = []
    for path in sorted(V3_PLUGIN_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            elif isinstance(node, ast.Call) and node.args:
                function_name = ""
                if isinstance(node.func, ast.Name):
                    function_name = node.func.id
                elif (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                ):
                    function_name = f"{node.func.value.id}.{node.func.attr}"
                argument = node.args[0]
                if (
                    function_name in {"__import__", "importlib.import_module"}
                    and isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                ):
                    modules.append(argument.value)
            for module_name in modules:
                if _is_forbidden_import(module_name):
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} {module_name}")
    assert violations == []


def test_v3_sdk_migrations_use_current_public_exports():
    """媒体身份和媒体服务器能力使用最新 V3 稳定 SDK。"""
    api_source = (V3_PLUGIN_ROOT / "controller" / "api.py").read_text(encoding="utf-8-sig")
    identity_source = (V3_PLUGIN_ROOT / "model" / "identity.py").read_text(encoding="utf-8-sig")
    folio_source = (V3_PLUGIN_ROOT / "service" / "folio.py").read_text(encoding="utf-8-sig")
    migration_source = (V3_PLUGIN_ROOT / "migration.py").read_text(encoding="utf-8-sig")
    subscription_source = (V3_PLUGIN_ROOT / "service" / "subscription.py").read_text(encoding="utf-8-sig")
    assert "from app.sdk.media import resolve_media_identity" in api_source
    assert "from app.sdk.media import normalize_media_source, resolve_media_identity" in identity_source
    assert "from app.sdk.services import MediaServerHelper, MediaServerIdentityHelper" in folio_source
    assert "from app.schemas.types import MediaSource, MediaType, MessageType" in folio_source
    assert "NotificationType" not in folio_source
    assert "from app.db.oper.subscribe import SubscribeOper" in subscription_source
    assert '"app.db.oper.subscribe"' in migration_source
    assert '"app.db.oper.subscribehistory"' in migration_source
    assert "app.db.subscribe_oper" not in migration_source + subscription_source
    assert "app.db.subscribehistory_oper" not in migration_source
    assert "app.domain.media" not in api_source + identity_source
    assert "app.application.mediaserver" not in folio_source


def test_v3_entrypoints_keep_business_implementation_out_of_package_root():
    """根目录入口只保留兼容门面，业务实现必须位于 service 层。"""
    root = V3_PLUGIN_ROOT
    for filename, service_name in (("feed.py", "rank_pipeline"), ("folio.py", "folio"), ("dashboard.py", "dashboard")):
        source = (root / filename).read_text(encoding="utf-8-sig")
        assert f"from .service import {service_name}" in source
        assert "def " not in source
    controller_source = (root / "controller" / "api.py").read_text(encoding="utf-8-sig")
    assert "from ..service import dashboard as dash" in controller_source
    assert "from ..service import folio" in controller_source
    assert "from ..service import rank_pipeline as feed" in controller_source
    assert "from .. import dashboard" not in controller_source
    assert "from .. import feed" not in controller_source
    assert "from .. import folio" not in controller_source
    rank_source = (root / "service" / "rank_pipeline.py").read_text(encoding="utf-8-sig")
    assert "rss_adapter.RequestUtils =" not in rank_source
    assert "rss_adapter.DomUtils =" not in rank_source


def test_v3_event_manager_uses_public_sdk_contract():
    """事件管理使用 V3 正式 SDK，避免触发兼容导入告警。"""
    source = (V3_PLUGIN_ROOT / "__init__.py").read_text(encoding="utf-8-sig")
    webhook = (V3_PLUGIN_ROOT / "service" / "webhook.py").read_text(encoding="utf-8-sig")
    assert "from app.sdk.events import Event, eventmanager" in source
    assert "from app.sdk.events import Event" in webhook
    assert "app.core.event" not in source + webhook


def test_v3_cookiecloud_uses_runtime_supported_adapter():
    """CookieCloud 保留唯一已审查的 V3 内部适配器路径。"""
    adapter_source = (V3_PLUGIN_ROOT / "adapter" / "douban_account.py").read_text(encoding="utf-8-sig")
    facade_source = (V3_PLUGIN_ROOT / "doubanapi.py").read_text(encoding="utf-8-sig")
    assert "from app.adapters.external.cookiecloud import CookieCloudHelper" in adapter_source
    assert "from .adapter import douban_account as _account" in facade_source
    assert "app.integrations.cookiecloud" not in adapter_source + facade_source


def test_sync_to_target_writes_only_v3_layout(tmp_path):
    """V3 同步必须写入 package.v3.json 与 plugins.v3。"""
    source = tmp_path / "source"
    target = tmp_path / "target"
    source_plugin = source / "plugins.v3" / "doubancenter"
    target_v2_plugin = target / "plugins.v2" / "doubancenter"
    source_plugin.mkdir(parents=True)
    target_v2_plugin.mkdir(parents=True)
    (target / "plugins.v3").mkdir(parents=True)
    (source / "package.v3.json").write_text(
        json.dumps({"DoubanCenter": {"name": "豆瓣中心", "version": "3.0.0"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (target / "package.v3.json").write_text("{}", encoding="utf-8")
    (target / "package.v2.json").write_text(
        json.dumps({"DoubanCenter": {"version": "1.2.20"}}),
        encoding="utf-8",
    )
    (source_plugin / "__init__.py").write_text("plugin_version = '3.0.0'\n", encoding="utf-8")
    (target_v2_plugin / "__init__.py").write_text("plugin_version = '1.2.20'\n", encoding="utf-8")

    actions = sync_to_target(
        source,
        target,
        ["DoubanCenter"],
        include_icons=False,
        generation="v3",
    )

    assert json.loads((target / "package.v3.json").read_text(encoding="utf-8"))["DoubanCenter"]["version"] == "3.0.0"
    assert json.loads((target / "package.v2.json").read_text(encoding="utf-8"))["DoubanCenter"]["version"] == "1.2.20"
    assert (target / "plugins.v3" / "doubancenter" / "__init__.py").is_file()
    assert (target_v2_plugin / "__init__.py").read_text(encoding="utf-8") == "plugin_version = '1.2.20'\n"
    assert "plugin:DoubanCenter" in actions


def test_release_workflow_maps_package_v3_to_plugins_v3():
    """Release workflow 必须按索引代际选择同代源码目录。"""
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "'package.v3.json'" in workflow
    assert 'process_package "package.v3.json" "plugins.v3"' in workflow
