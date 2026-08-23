"""豆瓣中心 V3 REST 合同测试。"""

from fastapi import HTTPException

from app import schemas

from doubancenter.controller import api as api_controller
from doubancenter.controller import schemas as api_schemas


class ApiPlugin:
    """提供路由表绑定所需的占位 endpoint。"""

    def __getattr__(self, name):
        """返回可调用的占位 endpoint。"""
        return lambda **kwargs: None


def test_all_plugin_routes_use_bearer_and_concrete_response_models():
    """18 条普通 JSON 路由均声明 bearer 与具体响应模型。"""
    routes = api_controller.get_api(ApiPlugin())
    assert len(routes) == 18
    assert {route["path"] for route in routes} == set(api_schemas.API_RESPONSE_MODELS)
    for route in routes:
        assert route["auth"] == "bear"
        assert route["response_model"] is schemas.Response[api_schemas.API_RESPONSE_MODELS[route["path"]]]
    assert "object" not in repr(api_schemas.ResolveMediaData.model_fields["root"].annotation).lower()


def test_to_response_produces_one_business_envelope():
    """业务数据由宿主 Response 包装一次，不形成双层 data。"""
    response = api_controller._to_response(
        {
            "success": True,
            "message": "识别成功",
            "data": {"title": "测试", "media_source": "douban", "media_id": "99"},
        },
        api_schemas.ResolveMediaData,
    )
    dumped = response.model_dump()
    assert set(dumped) == {"success", "message", "data"}
    assert dumped["success"] is True
    assert dumped["message"] == "识别成功"
    assert dumped["data"]["media_source"] == "douban"
    assert dumped["data"]["media_id"] == "99"
    assert "data" not in dumped["data"]


def test_business_failure_and_empty_result_remain_single_envelope():
    """业务失败与空结果均使用同一 V3 envelope。"""
    failed = api_controller._to_response(
        {"success": False, "message": "未找到"},
        api_schemas.DeleteArchiveData,
    )
    assert failed.model_dump() == {"success": False, "message": "未找到", "data": None}
    empty = api_controller._to_response(
        {"success": True, "data": []},
        api_schemas.PendingObservationsData,
    )
    assert empty.model_dump() == {"success": True, "message": "", "data": []}


def test_request_identity_rejects_half_and_zero_pairs():
    """API 入口拒绝半身份和零 ID，并保留动态来源。"""
    source, media_id = api_controller._normalize_request_identity("vendor.one", 7)
    assert source.value == "vendor.one"
    assert media_id == "7"
    for media_source, invalid_id in (("douban", None), (None, "7"), ("douban", "0")):
        try:
            api_controller._normalize_request_identity(media_source, invalid_id)
        except HTTPException as err:
            assert err.status_code == 400
        else:
            raise AssertionError("无效身份对未被拒绝")
