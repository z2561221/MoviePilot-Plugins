from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import schemas
from app.api.response import ResponseAPIRouter
from localtoolkit import LocalToolkit
from localtoolkit.controller.api import run_module
from localtoolkit.model.api import (
    ToolkitHistoryData,
    ToolkitOptionsData,
    ToolkitRunData,
    ToolkitStatusData,
)


class FakeModule:
    """为 API 合同测试提供固定模块结果。"""

    def __init__(self, name: str, result: dict) -> None:
        """保存模块名称与运行结果。"""
        self.module_name = name
        self._result = result

    def get_status(self) -> dict:
        """返回最小模块状态。"""
        return {"run_mode": "manual"}

    def run_once(self) -> dict:
        """返回预设运行结果。"""
        return dict(self._result)


def _plugin_with_result(result: dict) -> SimpleNamespace:
    """构建三个模块共用预设结果的插件替身。"""
    return SimpleNamespace(
        tmdb_cache=FakeModule("清理TMDB", result),
        check_missing=FakeModule("扫描缺集", result),
        library_cleanup=FakeModule("清理库存", result),
    )


def test_routes_declare_concrete_v3_response_models() -> None:
    """确认五个插件路由都声明具体 V3 响应模型。"""
    plugin = object.__new__(LocalToolkit)
    routes = {route["path"]: route for route in plugin.get_api()}

    assert all(route["auth"] == "bear" for route in routes.values())
    assert routes["/local_toolkit/status"]["response_model"] is ToolkitStatusData
    assert routes["/local_toolkit/run/{module}"]["response_model"] == schemas.Response[ToolkitRunData]
    assert routes["/local_toolkit/history"]["response_model"] is ToolkitHistoryData
    assert routes["/local_toolkit/options"]["response_model"] is ToolkitOptionsData
    assert routes["/local_toolkit/invalidate_cache"]["response_model"] == schemas.Response[None]


def test_run_module_keeps_business_failure_in_single_envelope() -> None:
    """确认模块失败不会被外层错误包装成成功。"""
    response = run_module(
        _plugin_with_result({"success": False, "message": "Redis 未连接"}),
        "tmdb_cache",
    )

    assert response.model_dump() == {
        "success": False,
        "message": "Redis 未连接",
        "data": None,
    }


def test_run_module_moves_success_payload_into_data() -> None:
    """确认模块成功数据位于统一响应的 data 字段。"""
    response = run_module(
        _plugin_with_result(
            {
                "success": True,
                "summary": "扫描完成",
                "missing_total": 2,
                "items": [{"path": "Anime", "title": "Demo", "season": 1, "missing": [2, 4]}],
            }
        ),
        "check_missing",
    )

    assert response.success is True
    assert response.message == ""
    assert response.data is not None
    assert response.data.summary == "扫描完成"
    assert response.data.missing_total == 2
    assert response.data.items and response.data.items[0].missing == [2, 4]


def test_run_module_rejects_unknown_module_with_404() -> None:
    """确认未知模块使用标准 404，而不是成功响应中的失败字典。"""
    with pytest.raises(HTTPException) as error:
        run_module(_plugin_with_result({}), "unknown")

    assert error.value.status_code == 404


def test_response_router_produces_exact_single_envelope() -> None:
    """确认宿主路由对业务模型只包装一次，并保留显式业务失败。"""
    router = ResponseAPIRouter()

    def status_endpoint() -> ToolkitStatusData:
        """返回最小工具中心状态。"""
        return ToolkitStatusData(
            enabled=True,
            modules={
                "library_cleanup": {"enabled": False},
                "check_missing": {"run_mode": "manual"},
                "tmdb_cache": {"keys": 0, "size_kb": 0},
            },
        )

    def failed_run_endpoint() -> schemas.Response[ToolkitRunData]:
        """返回显式业务失败。"""
        return schemas.Response[ToolkitRunData](
            success=False,
            message="Redis 未连接",
            data=None,
        )

    router.add_api_route("/status", status_endpoint, methods=["GET"], response_model=ToolkitStatusData)
    router.add_api_route(
        "/run",
        failed_run_endpoint,
        methods=["POST"],
        response_model=schemas.Response[ToolkitRunData],
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    status = client.get("/status").json()
    failed = client.post("/run").json()

    assert set(status) == {"success", "message", "data"}
    assert status["success"] is True
    assert status["data"]["enabled"] is True
    assert failed == {"success": False, "message": "Redis 未连接", "data": None}
