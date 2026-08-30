"""BackupCenter V3 动态路由与统一响应合同测试。"""

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "backupcenter"
PACKAGE_NAME = "backupcenter_v3_contract"


def _package(name: str, path: Path) -> ModuleType:
    """创建不会执行插件入口文件的测试包。"""
    module = ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
    return module


class _PluginManager:
    """提供控制器导入所需的最小插件管理器。"""


def _verify_token() -> None:
    """提供 FastAPI 依赖声明所需的测试认证函数。"""
    return None


_package("app", PLUGIN_DIR)
_package("app.sdk", PLUGIN_DIR)
config_module = ModuleType("app.sdk.config")
config_module.settings = SimpleNamespace(
    DB_TYPE="sqlite",
    SECRET_KEY="backupcenter-api-contract",
)
sys.modules["app.sdk.config"] = config_module
plugin_module = ModuleType("app.sdk.plugins")
plugin_module.PluginManager = _PluginManager
sys.modules["app.sdk.plugins"] = plugin_module
database_module = ModuleType("app.sdk.database")
database_module.create_backup = lambda: SimpleNamespace(name="test.sqlite")
sys.modules["app.sdk.database"] = database_module
api_package = _package("app.api", PLUGIN_DIR)
endpoint_package = _package("app.api.endpoints", PLUGIN_DIR)
host_plugin_module = ModuleType("app.api.endpoints.plugin")
host_plugin_module.verify_token = _verify_token
endpoint_package.plugin = host_plugin_module
api_package.endpoints = endpoint_package
sys.modules["app"].api = api_package
sys.modules["app.api.endpoints.plugin"] = host_plugin_module
_package("app.schemas", PLUGIN_DIR)
schema_types_module = ModuleType("app.schemas.types")
schema_types_module.SystemConfigKey = SimpleNamespace(UserInstalledPlugins="installed")
sys.modules["app.schemas.types"] = schema_types_module
version_module = ModuleType("version")
version_module.APP_VERSION = "v3.0.0"
sys.modules["version"] = version_module

_package(PACKAGE_NAME, PLUGIN_DIR)
_package(f"{PACKAGE_NAME}.controller", PLUGIN_DIR / "controller")
_package(f"{PACKAGE_NAME}.model", PLUGIN_DIR / "model")
_package(f"{PACKAGE_NAME}.service", PLUGIN_DIR / "service")

api_module = importlib.import_module(f"{PACKAGE_NAME}.controller.api")
api_model = importlib.import_module(f"{PACKAGE_NAME}.model.api")
backup_model = importlib.import_module(f"{PACKAGE_NAME}.model.backup")
restore_module = importlib.import_module(f"{PACKAGE_NAME}.service.restore_service")

BackupCenterApiController = api_module.BackupCenterApiController
build_api_routes = api_module.build_api_routes
EncryptionStatusData = api_model.EncryptionStatusData
BackupLogsData = api_model.BackupLogsData
ScopeError = backup_model.ScopeError
RestoreService = restore_module.RestoreService
RestoreServiceError = restore_module.RestoreServiceError


class _Plugin:
    """提供 API 路由构建所需的最小插件对象。"""


class _PluginDataStore:
    """模拟宿主公开插件数据接口并支持注入写入失败。"""

    def __init__(self, data=None, fail_on_save: str | None = None):
        self.data = {plugin_id: dict(values) for plugin_id, values in (data or {}).items()}
        self.fail_on_save = fail_on_save

    def get_data(self, key=None, plugin_id=None):
        """返回目标插件的单项数据或全部数据行。"""
        values = self.data.setdefault(plugin_id, {})
        if key is not None:
            return values.get(key)
        return [SimpleNamespace(key=item_key, value=value) for item_key, value in values.items()]

    def save_data(self, key, value, plugin_id=None):
        """保存数据，并在指定键上模拟宿主写入失败。"""
        if key == self.fail_on_save:
            raise RuntimeError("injected save failure")
        self.data.setdefault(plugin_id, {})[key] = value

    def del_data(self, key, plugin_id=None):
        """删除目标插件的数据键。"""
        self.data.setdefault(plugin_id, {}).pop(key, None)


def _write_plugin_data_payload(root: Path, payload: dict) -> None:
    """写入恢复服务使用的插件数据负载。"""
    (root / "plugin_data.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def test_routes_declare_business_models_and_native_export() -> None:
    """普通 JSON 路由声明业务模型，ZIP 导出保持原生响应。"""
    plugin = _Plugin()
    routes = build_api_routes(plugin)

    assert len(routes) == 13
    assert all(route["auth"] == "bear" for route in routes)
    export = next(route for route in routes if route["path"].endswith("/export"))
    ordinary = [route for route in routes if route is not export]

    assert all(route["response_model"] is not None for route in ordinary)
    assert export["response_model"] is None
    assert export["response_class"] is FileResponse
    assert "application/zip" in export["responses"][200]["content"]
    logs = next(route for route in routes if route["path"] == "/logs")
    assert logs["methods"] == ["GET"]
    assert logs["response_model"] is BackupLogsData


def test_controller_returns_raw_business_data() -> None:
    """控制器不再手工生成 success/data 双层响应。"""
    controller = BackupCenterApiController(_Plugin())

    result = controller._run(lambda: {"configured": True})

    assert result == {"configured": True}
    assert "success" not in result


def test_controller_errors_use_v3_http_message() -> None:
    """已知业务错误通过 HTTPException 交给 V3 统一错误处理。"""
    controller = BackupCenterApiController(_Plugin())

    def fail() -> None:
        """触发一条可公开显示的范围错误。"""
        raise ScopeError("至少选择一项备份内容")

    try:
        controller._run(fail)
    except HTTPException as error:
        assert error.status_code == 422
        assert error.detail == "至少选择一项备份内容"
    else:
        raise AssertionError("业务错误未转换为 HTTPException")


def test_v3_route_keeps_business_data_unwrapped() -> None:
    """V3 动态路由直接返回与声明模型匹配的业务对象。"""

    def endpoint() -> dict[str, bool]:
        """返回未包装的口令状态业务对象。"""
        return {"configured": True}

    result = endpoint()
    validated = EncryptionStatusData.model_validate(result)

    assert result == {"configured": True}
    assert validated.configured is True
    assert set(result) == {"configured"}


def test_restore_plugin_data_uses_public_interface_and_keeps_unselected_data(
    tmp_path: Path,
) -> None:
    """选择性恢复只替换目标插件，并通过公开数据接口写入。"""
    plugin = _PluginDataStore(
        {"PluginA": {"old": 1}, "PluginB": {"keep": 2}}
    )
    _write_plugin_data_payload(
        tmp_path,
        {"PluginA": [{"key": "new", "value": {"enabled": True}}]},
    )

    restored = RestoreService(plugin, SimpleNamespace())._restore_plugin_data(
        tmp_path, ["PluginA"]
    )

    assert restored == 1
    assert plugin.data["PluginA"] == {"new": {"enabled": True}}
    assert plugin.data["PluginB"] == {"keep": 2}


def test_restore_plugin_data_rolls_back_partial_writes(tmp_path: Path) -> None:
    """任一写入失败时恢复所有目标插件的写入前快照。"""
    original = {
        "PluginA": {"old_a": 1},
        "PluginB": {"old_b": {"value": 2}},
    }
    plugin = _PluginDataStore(original, fail_on_save="fail")
    _write_plugin_data_payload(
        tmp_path,
        {
            "PluginA": [{"key": "new_a", "value": 3}],
            "PluginB": [
                {"key": "new_b", "value": 4},
                {"key": "fail", "value": 5},
            ],
        },
    )

    with pytest.raises(RestoreServiceError, match="已自动回滚"):
        RestoreService(plugin, SimpleNamespace())._restore_plugin_data(
            tmp_path, ["PluginA", "PluginB"]
        )

    assert plugin.data == original
