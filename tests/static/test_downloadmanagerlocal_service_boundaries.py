from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"

SERVICE_NAMES = {
    "archive",
    "diagnostics",
    "iyuu",
    "recheck",
    "rename",
    "site_tag",
    "transfer",
}


def _load_boundaries_module():
    """加载服务边界清单，不引入完整 MoviePilot 运行时。"""
    path = PLUGIN_DIR / "service" / "boundaries.py"
    spec = importlib.util.spec_from_file_location("downloadmanagerlocal_service_boundaries", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_downloadmanagerlocal_service_facades_exist_for_orchestration_modules():
    for name in SERVICE_NAMES:
        assert (PLUGIN_DIR / "service" / f"{name}.py").exists()


def test_downloadmanagerlocal_entrypoint_imports_services_not_legacy_modules():
    source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")

    assert "from .modules." not in source
    for name in SERVICE_NAMES:
        assert f"from .service.{name} import " in source


def test_downloadmanagerlocal_modules_do_not_define_api_response_handlers():
    for path in (PLUGIN_DIR / "modules").glob("*.py"):
        module = ast.parse(path.read_text(encoding="utf-8"))
        function_names = {
            node.name
            for node in module.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert not {name for name in function_names if name.startswith("api_")}


def test_downloadmanagerlocal_service_boundary_inventory_documents_legacy_modules():
    boundaries = _load_boundaries_module()

    assert set(boundaries.SERVICE_BOUNDARIES) == SERVICE_NAMES
    for name, item in boundaries.SERVICE_BOUNDARIES.items():
        assert item["service"] == f"service/{name}.py"
        assert item["legacy_module"] == f"modules/{item['legacy_name']}.py"
        assert item["owner"]

    assert boundaries.LEGACY_MODULE_EXCEPTIONS == {}
    assert set(boundaries.LEGACY_MODULE_COMPATIBILITY_SHIMS) == {
        item["legacy_module"] for item in boundaries.SERVICE_BOUNDARIES.values()
    }
