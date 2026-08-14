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
LEGACY_IMPORT_ROOTS = ("app.helper", "app.utils", "app.log")


def _is_legacy_import(module_name: str) -> bool:
    """判断模块名是否指向 MoviePilot V3 兼容导入层。"""
    return any(
        module_name == root or module_name.startswith(f"{root}.")
        for root in LEGACY_IMPORT_ROOTS
    )


def test_v3_plugin_does_not_use_legacy_import_paths():
    """V3 源码不能继续使用运行时诊断标记的兼容导入路径。"""
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
                if _is_legacy_import(module_name):
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} {module_name}")
    assert violations == []


def test_v3_event_manager_keeps_host_event_contract():
    """事件管理仍使用宿主实际提供的 app.core.event 合同。"""
    source = (V3_PLUGIN_ROOT / "__init__.py").read_text(encoding="utf-8-sig")
    webhook = (V3_PLUGIN_ROOT / "service" / "webhook.py").read_text(encoding="utf-8-sig")
    assert "from app.core.event import Event, eventmanager" in source
    assert "from app.core.event import Event" in webhook
    assert "app.sdk.events" not in source + webhook


def test_v3_cookiecloud_uses_runtime_supported_adapter():
    """CookieCloud 必须使用 V3 运行时诊断给出的正式适配器路径。"""
    source = (V3_PLUGIN_ROOT / "doubanapi.py").read_text(encoding="utf-8-sig")
    assert "from app.adapters.external.cookiecloud import CookieCloudHelper" in source
    assert "app.integrations.cookiecloud" not in source


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
