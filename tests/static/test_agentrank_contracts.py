"""AgentRank repository and federation contract gates."""

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = ROOT / "plugins.v2" / "agentrank"
ENTRYPOINT = PLUGIN_DIR / "__init__.py"
PLUGIN_JSON = PLUGIN_DIR / "plugin.json"
PACKAGE_JSON = ROOT / "package.v2.json"
API_CONTROLLER = PLUGIN_DIR / "controller" / "api.py"
FRONTEND_API = PLUGIN_DIR / "frontend" / "src" / "components" / "api.js"
VITE_CONFIG = PLUGIN_DIR / "frontend" / "vite.config.js"
REMOTE_ENTRY = PLUGIN_DIR / "dist" / "assets" / "remoteEntry.js"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _entrypoint_class() -> ast.ClassDef:
    tree = ast.parse(ENTRYPOINT.read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AgentRank")


def _class_string(class_node: ast.ClassDef, name: str) -> str:
    for statement in class_node.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            value = statement.value
            assert isinstance(value, ast.Constant) and isinstance(value.value, str)
            return value.value
    raise AssertionError(f"AgentRank.{name} is not declared as a string literal")


def test_agentrank_entrypoint_remains_a_thin_contract_layer():
    """The plugin entrypoint may wire layers but must not own domain workflows."""
    tree = ast.parse(ENTRYPOINT.read_text(encoding="utf-8"))
    relative_modules = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }
    assert relative_modules <= {"controller.api", "model.config", "service.lifecycle"}

    plugin_class = _entrypoint_class()
    forbidden_nodes = (ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)
    heavy_methods = [
        method.name
        for method in plugin_class.body
        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(isinstance(node, forbidden_nodes) for node in ast.walk(method))
    ]
    assert heavy_methods == []


def test_agentrank_metadata_is_consistent():
    """Package, plugin manifest, and Python entrypoint share one identity."""
    package = _json(PACKAGE_JSON)["AgentRank"]
    manifest = _json(PLUGIN_JSON)
    plugin_class = _entrypoint_class()

    assert package["name"] == manifest["name"] == _class_string(plugin_class, "plugin_name")
    assert package["version"] == manifest["version"] == _class_string(plugin_class, "plugin_version")
    assert package["author"] == manifest["author"] == _class_string(plugin_class, "plugin_author")
    assert package["author_url"] == manifest["author_url"] == _class_string(plugin_class, "author_url")
    assert package["author_url"] == "https://github.com/z2561221"
    assert package["v2"] is manifest["v2"] is True


def test_agentrank_declares_all_four_federation_exposes():
    """Source configuration and built remote entry expose every MP surface."""
    vite_source = VITE_CONFIG.read_text(encoding="utf-8")
    remote_source = REMOTE_ENTRY.read_text(encoding="utf-8")
    entrypoint_source = ENTRYPOINT.read_text(encoding="utf-8")

    assert re.search(r'return\s+["\']vue["\']\s*,\s*["\']dist/assets["\']', entrypoint_source)
    for expose in ("Config", "Dashboard", "Page", "AppPage"):
        assert f"'./{expose}'" in vite_source
        assert f'"./{expose}"' in remote_source


def test_agentrank_api_contract_is_bearer_only():
    """Every backend route is bearer protected and the UI uses MP's auth client."""
    controller_source = API_CONTROLLER.read_text(encoding="utf-8")
    frontend_source = FRONTEND_API.read_text(encoding="utf-8")

    route_count = controller_source.count('"path":')
    assert route_count > 0
    assert controller_source.count('"auth": "bear"') == route_count
    assert "fetch(" not in frontend_source
    assert "api.get(" in frontend_source
    assert "api.post(" in frontend_source


def test_agentrank_sidebar_contract_targets_discovery_main():
    """The full page entry stays in MP's discovery permission boundary."""
    source = ENTRYPOINT.read_text(encoding="utf-8")
    assert '"nav_key": "main"' in source
    assert '"section": "discovery"' in source
    assert '"permission": "discovery"' in source
