"""AgentRank V3 API 与联邦前端响应合同测试。"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from agentrank.controller.api import (
    AgentRankApiController,
    ApiContractError,
    _http_error,
    build_api_routes,
)
from agentrank.controller.schemas import API_RESPONSE_MODELS


ROOT = Path(__file__).resolve().parents[3]
FRONTEND_API = ROOT / "plugins.v3" / "agentrank" / "frontend" / "src" / "components" / "api.js"
PREVIEW = ROOT / "plugins.v3" / "agentrank" / "frontend" / "src" / "PreviewApp.vue"
RECOMMENDATION_ACTIONS = (
    ROOT
    / "plugins.v3"
    / "agentrank"
    / "frontend"
    / "src"
    / "components"
    / "RecommendationActions.vue"
)


def test_every_json_route_declares_a_named_business_response_model():
    """全部普通 JSON 路由声明独立且命名明确的业务模型。"""
    routes = build_api_routes(SimpleNamespace())

    assert len(routes) == len(API_RESPONSE_MODELS)
    assert {route["path"] for route in routes} == set(API_RESPONSE_MODELS)
    assert all(route["response_model"] is API_RESPONSE_MODELS[route["path"]] for route in routes)
    assert len({model.__name__ for model in API_RESPONSE_MODELS.values()}) == len(routes)


def test_endpoint_boundary_returns_business_data_without_manual_envelope():
    """内部兼容包装在 FastAPI endpoint 边界只解包一次。"""
    controller = AgentRankApiController(object())

    assert controller._endpoint(lambda: {"success": True, "data": {"ready": True}}) == {
        "ready": True
    }


def test_api_contract_error_uses_clean_detail_and_machine_code_header():
    """HTTP 错误交给宿主统一包装，机器码保留在专用响应头。"""
    with pytest.raises(Exception) as raised:
        _http_error(ApiContractError(409, "board_conflict", "榜单已刷新"))

    assert raised.value.status_code == 409
    assert raised.value.detail == "榜单已刷新"
    assert raised.value.headers == {"X-AgentRank-Error-Code": "board_conflict"}


def test_frontend_reads_exactly_one_v3_envelope():
    """联邦前端不再读取 Axios 外层或旧 error 对象。"""
    source = FRONTEND_API.read_text(encoding="utf-8")

    assert "const payload = response\n" in source
    assert "payload.success === false" in source
    assert "payload.success !== true" in source
    assert "return payload.data" in source
    assert "response?.data ?? response" not in source
    assert "payload.error" not in source
    assert "x-agentrank-error-code" in source
    preview = PREVIEW.read_text(encoding="utf-8")
    assert "return { data: { success:" not in preview


def test_native_subscribe_uses_v3_primary_identity_only():
    """原生订阅载荷使用成对主身份，来源 ID 仅保留为辅助字段。"""
    source = RECOMMENDATION_ACTIONS.read_text(encoding="utf-8")

    assert "props.item?.media_source" in source
    assert "props.item?.media_id" in source
    assert "media.media_source = source" in source
    assert "media.media_id = sourceId" in source
    assert "media.mediaid_prefix" not in source
    assert "media.tmdbid" not in source
    assert "media.doubanid" not in source
