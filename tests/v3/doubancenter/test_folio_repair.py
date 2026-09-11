"""历史分季修复的备份、并发保护、幂等和接口契约测试。"""

import copy
import json
from pathlib import Path
from types import MethodType

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import schemas
from app.plugins.doubancenter import DoubanCenter
from app.plugins.doubancenter.controller import api as api_controller
from app.plugins.doubancenter.controller import schemas as api_schemas
from app.plugins.doubancenter.service import folio_repair
from tests.v3.doubancenter.folio_fakes import FolioMediaChain, FolioPlugin, HUANZHU_SUBJECTS, huanzhu_media


def _record():
    """返回第二季错误共用首部身份的历史样本。"""
    return {"subject_id": "1786739", "subject_name": "还珠格格", "media_source": "douban", "media_id": "1786739",
            "timestamp": "2026-09-10 14:37:22", "poster_path": "https://image.tmdb.org/t/p/original/old.jpg",
            "type": "电视剧", "custom": {"keep": True}}


def _target():
    """只明确源身份，不由调用者指定目标豆瓣 ID。"""
    return {"key": "还珠格格 第2季", "media_source": "themoviedb", "media_id": "4285", "season": 2, "episode_group": ""}


@pytest.fixture
def repair_plugin(monkeypatch, tmp_path):
    """隔离网络与档案文件，使用生产格式的媒体样本。"""
    chain = FolioMediaChain(huanzhu_media(), HUANZHU_SUBJECTS)
    monkeypatch.setattr(folio_repair, "MediaChain", lambda: chain)
    return FolioPlugin({"还珠格格 第2季": _record()}, tmp_path)


def test_preview_is_readonly_and_apply_backs_up_preserving_timestamp(repair_plugin):
    """预览无持久化，应用先保存原始档案并完整保留观看时间及扩展字段。"""
    plugin = repair_plugin
    before = copy.deepcopy(plugin.data)
    preview = folio_repair.preview(plugin, [_target()])
    assert preview["ready"] is True
    assert preview["changed"] == 1
    assert plugin.data == before
    assert list(plugin.data_path.iterdir()) == []
    assert preview["items"][0]["after"]["media_id"] == "1786740"
    result = folio_repair.apply(plugin, preview["plan_id"])
    assert result["updated"] == 1
    backup = json.loads(Path(result["backup_path"]).read_text(encoding="utf-8"))
    assert backup["data"] == before["folio_data"]
    after = plugin.data["folio_data"][_target()["key"]]
    assert after["timestamp"] == _record()["timestamp"]
    assert after["custom"] == {"keep": True}
    assert after["media_id"] == "1786740"
    assert after["origin"]["season"] == 2
    assert after["season_label"] == "第2季"
    assert result["raw_count"] == 1


def test_apply_and_new_preview_are_idempotent(repair_plugin):
    """同预览重复应用和同目标重新预览都不产生第二次写入或备份。"""
    first = folio_repair.preview(repair_plugin, [_target()])
    applied = folio_repair.apply(repair_plugin, first["plan_id"])
    again = folio_repair.apply(repair_plugin, first["plan_id"])
    assert again["updated"] == 0
    assert again["already_applied"] is True
    assert again["backup_path"] == applied["backup_path"]
    second = folio_repair.preview(repair_plugin, [_target()])
    assert second["changed"] == 0
    assert second["ready"] is True
    assert folio_repair.apply(repair_plugin, second["plan_id"])["updated"] == 0
    assert len(list(repair_plugin.data_path.rglob("*.json"))) == 1


def test_refresh_verified_poster_only_uses_confirmed_subject(repair_plugin, monkeypatch):
    """显式刷新已核验海报只改图片，保留身份、时间和未知字段，并支持幂等回读。"""
    first = folio_repair.preview(repair_plugin, [_target()])
    folio_repair.apply(repair_plugin, first["plan_id"])
    before = copy.deepcopy(repair_plugin.data["folio_data"])
    chain = folio_repair.MediaChain()
    poster = "https://img3.doubanio.com/view/photo/m_ratio_poster/public/second-part.webp"
    chain.subjects[1]["pic"] = {"large": poster}
    monkeypatch.setattr(chain, "recognize_media", lambda **kwargs: pytest.fail("已核验海报刷新不重新识别媒体"))
    assert folio_repair.preview(repair_plugin, [_target()])["changed"] == 0
    app = FastAPI()
    app.add_api_route("/preview", MethodType(DoubanCenter.api_folio_repair_preview, repair_plugin),
                      methods=["POST"], response_model=schemas.Response[api_schemas.FolioRepairPreviewData])
    with TestClient(app) as client:
        response = client.post("/preview", json={"items": [_target()], "refresh_posters": True})
    assert response.status_code == 200
    plan = response.json()["data"]
    assert plan["ready"] is True
    assert plan["changed"] == 1
    assert repair_plugin.data["folio_data"] == before
    result = folio_repair.apply(repair_plugin, plan["plan_id"])
    assert result["updated"] == 1
    assert json.loads(Path(result["backup_path"]).read_text(encoding="utf-8"))["data"] == before
    after = repair_plugin.data["folio_data"][_target()["key"]]
    assert after == {**before[_target()["key"]], "poster_path": poster}
    assert folio_repair.apply(repair_plugin, plan["plan_id"])["updated"] == 0
    assert folio_repair.preview(repair_plugin, [_target()], refresh_posters=True)["changed"] == 0


@pytest.mark.parametrize("detail", [None, {"id": "wrong", "is_tv": True},
                                   {"id": "1786740", "is_tv": False},
                                   {"id": "1786740", "is_tv": True}])
def test_poster_refresh_rejects_missing_or_wrong_subject(repair_plugin, monkeypatch, detail):
    """查询失败、条目或类型不符和无海报时保留原记录，不能盲换图片。"""
    first = folio_repair.preview(repair_plugin, [_target()])
    folio_repair.apply(repair_plugin, first["plan_id"])
    before = copy.deepcopy(repair_plugin.data)
    monkeypatch.setattr(folio_repair.MediaChain(), "douban_info", lambda **kwargs: detail)
    plan = folio_repair.preview(repair_plugin, [_target()], refresh_posters=True)
    assert plan["ready"] is False
    assert plan["changed"] == 0
    with pytest.raises(ValueError, match="未核实"):
        folio_repair.apply(repair_plugin, plan["plan_id"])
    assert repair_plugin.data == before


def test_poster_refresh_requires_verified_playback_identity(repair_plugin):
    """仅刷新海报不能顺带修复未核验身份。"""
    before = copy.deepcopy(repair_plugin.data)
    plan = folio_repair.preview(repair_plugin, [_target()], refresh_posters=True)
    assert plan["ready"] is False
    assert plan["changed"] == 0
    assert repair_plugin.data == before


def test_concurrent_target_update_rejects_stale_plan(repair_plugin):
    """预览后目标播放记录更新时拒绝覆盖，保留新时间。"""
    plan = folio_repair.preview(repair_plugin, [_target()])
    latest = repair_plugin.data["folio_data"][_target()["key"]]
    latest["timestamp"] = "2026-09-10 15:00:00"
    with pytest.raises(ValueError, match="预览后变化"):
        folio_repair.apply(repair_plugin, plan["plan_id"])
    assert latest["media_id"] == "1786739"
    assert list(repair_plugin.data_path.iterdir()) == []


def test_concurrent_unrelated_record_is_kept_and_backed_up(repair_plugin):
    """其他影片同时增加记录时，应用只替换目标并备份当前全集。"""
    plan = folio_repair.preview(repair_plugin, [_target()])
    repair_plugin.data["folio_data"]["别的影片"] = {**_record(), "media_id": "99", "subject_id": "99"}
    result = folio_repair.apply(repair_plugin, plan["plan_id"])
    assert result["raw_count"] == 2
    assert repair_plugin.data["folio_data"]["别的影片"]["media_id"] == "99"
    backup = json.loads(Path(result["backup_path"]).read_text(encoding="utf-8"))
    assert "别的影片" in backup["data"]


def test_new_duplicate_origin_after_preview_is_a_conflict(repair_plugin):
    """新播放事件创建同一源季身份时，旧标题迁移必须重新核对。"""
    plan = folio_repair.preview(repair_plugin, [_target()])
    repair_plugin.data["folio_data"]["新播放键"] = {**_record(), "origin": {
        "media_source": "themoviedb", "media_id": "4285", "type": "tv", "season": 2, "episode_group": "",
    }}
    with pytest.raises(ValueError, match="相同播放身份"):
        folio_repair.apply(repair_plugin, plan["plan_id"])


def test_unresolved_and_expired_plans_cannot_apply(repair_plugin, monkeypatch):
    """缺详情的预览保留原始记录，过期预览不能继续应用。"""
    chain = FolioMediaChain(huanzhu_media(), [])
    monkeypatch.setattr(folio_repair, "MediaChain", lambda: chain)
    plan = folio_repair.preview(repair_plugin, [_target()])
    assert plan["ready"] is False
    with pytest.raises(ValueError, match="未核实"):
        folio_repair.apply(repair_plugin, plan["plan_id"])
    repair_plugin._folio_repair_plans[plan["plan_id"]]["expires_at"] = 0
    with pytest.raises(ValueError, match="过期"):
        folio_repair.apply(repair_plugin, plan["plan_id"])
    assert repair_plugin.data["folio_data"][_target()["key"]] == _record()


def test_backup_failure_prevents_any_record_write(repair_plugin, monkeypatch):
    """备份无法写入时，不允许开始修复档案。"""
    plan = folio_repair.preview(repair_plugin, [_target()])

    def fail_backup(*args):
        """模拟备份目录不可写。"""
        raise OSError("backup unavailable")

    monkeypatch.setattr(folio_repair, "_backup", fail_backup)
    with pytest.raises(OSError):
        folio_repair.apply(repair_plugin, plan["plan_id"])
    assert repair_plugin.data["folio_data"][_target()["key"]] == _record()


def test_repair_plan_is_instance_scoped(repair_plugin, tmp_path):
    """其他插件实例不能应用当前实例的预览。"""
    plan = folio_repair.preview(repair_plugin, [_target()])
    other = FolioPlugin({"还珠格格 第2季": _record()}, tmp_path)
    with pytest.raises(ValueError, match="过期"):
        folio_repair.apply(other, plan["plan_id"])


def test_repair_api_has_typed_body_envelope_and_conflict_status(repair_plugin):
    """FastAPI 实际解析结构化请求，冲突返回 409，数据不套双层 envelope。"""
    app = FastAPI()
    app.add_api_route("/preview", MethodType(DoubanCenter.api_folio_repair_preview, repair_plugin),
                      methods=["POST"], response_model=schemas.Response[api_schemas.FolioRepairPreviewData])
    app.add_api_route("/apply", MethodType(DoubanCenter.api_folio_repair_apply, repair_plugin),
                      methods=["POST"], response_model=schemas.Response[api_schemas.FolioRepairApplyData])
    with TestClient(app) as client:
        response = client.post("/preview", json={"items": [_target()]})
        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {"success", "message", "data"}
        assert payload["success"] is True
        assert payload["data"]["ready"] is True
        assert "data" not in payload["data"]
        assert client.post("/preview", json={"items": [{**_target(), "subject_id": "arbitrary"}]}).status_code == 422
        repair_plugin.data["folio_data"][_target()["key"]]["timestamp"] = "2026-09-10 16:00:00"
        assert client.post("/apply", json={"plan_id": payload["data"]["plan_id"]}).status_code == 409
        assert client.post("/preview", json={"items": [_target(), _target()]}).status_code == 400
    raw = api_controller.api_folio_data(repair_plugin, raw=True).model_dump()
    assert raw["data"][_target()["key"]]["timestamp"] == "2026-09-10 16:00:00"
