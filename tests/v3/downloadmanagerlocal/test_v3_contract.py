"""验证下载中心 V3 媒体、站点与 REST 合同。"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app import schemas
from app.schemas.types import MediaSource, MediaType
from app.plugins.downloadmanagerlocal import DownloadManagerLocal
from app.plugins.downloadmanagerlocal.adapter import moviepilot as moviepilot_adapter
from app.plugins.downloadmanagerlocal.controller import handlers
from app.plugins.downloadmanagerlocal.iyuu_helper import IyuuHelper
from app.plugins.downloadmanagerlocal.model.api import HashActionResult, OverviewResult
from app.plugins.downloadmanagerlocal.service import rename as rename_service


PLUGIN_ROOT = Path(__file__).resolve().parents[3] / "plugins.v3/downloadmanagerlocal"


def test_all_plugin_routes_declare_concrete_v3_models() -> None:
    """20 条普通 JSON 路由必须使用 bearer 和具体响应模型。"""
    plugin = object.__new__(DownloadManagerLocal)

    routes = plugin.get_api()

    assert len(routes) == 20
    assert {route["path"] for route in routes} == {
        "/downloaders",
        "/rename_history",
        "/overview",
        "/reset_speed_monitor_baseline",
        "/upload_limit_status",
        "/upload_limit_reallocate",
        "/upload_limit_site_tags",
        "/upload_limit_site_rules_update",
        "/upload_limit_disable_restore",
        "/diagnostics",
        "/retry_renames",
        "/retry_rename",
        "/delete_rename_history",
        "/rename_archive",
        "/restore_rename_archive",
        "/delete_rename_archive",
        "/recovery_torrent",
        "/sites",
        "/tag_cleanup_scan",
        "/tag_cleanup_execute",
    }
    for route in routes:
        assert route["auth"] == "bear"
        assert route.get("response_model") not in {None, dict, list}
    bare_paths = {
        "/downloaders",
        "/rename_history",
        "/overview",
        "/upload_limit_status",
        "/diagnostics",
        "/rename_archive",
        "/sites",
    }
    envelope_paths = {route["path"] for route in routes} - bare_paths
    for route in routes:
        response_model = route["response_model"]
        is_envelope = isinstance(response_model, type) and issubclass(
            response_model,
            schemas.Response,
        )
        assert is_envelope is (route["path"] in envelope_paths)


def test_json_post_routes_use_pydantic_request_models() -> None:
    """接收 JSON 的 POST 路由必须拒绝裸 dict 请求体。"""
    plugin = object.__new__(DownloadManagerLocal)
    json_paths = {
        "/reset_speed_monitor_baseline",
        "/upload_limit_reallocate",
        "/upload_limit_site_tags",
        "/upload_limit_site_rules_update",
        "/upload_limit_disable_restore",
        "/tag_cleanup_scan",
        "/tag_cleanup_execute",
    }

    routes = {route["path"]: route for route in plugin.get_api()}

    for path in json_paths:
        payload = inspect.signature(routes[path]["endpoint"]).parameters["payload"]
        annotation_text = str(payload.annotation)
        assert "dict" not in annotation_text
        assert "Request" in annotation_text


def test_operation_business_failure_is_single_v3_envelope() -> None:
    """业务失败必须落在顶层 success/message，业务数据只出现一层。"""
    plugin = SimpleNamespace(
        _retry_rename=lambda _hash: {"code": 1, "msg": "记录不存在", "hash": "deadbeef"}
    )

    response = handlers.api_retry_rename(plugin, "deadbeef")

    assert isinstance(response, schemas.Response)
    assert response.success is False
    assert response.message == "记录不存在"
    assert isinstance(response.data, HashActionResult)
    assert response.data.hash == "deadbeef"
    dumped = response.model_dump()
    assert set(dumped) == {"success", "message", "data"}
    assert "data" not in dumped["data"]


def test_query_business_model_is_bare_payload_for_current_v3() -> None:
    """V3 动态查询路由返回裸业务模型，不依赖宿主自动套壳。"""
    result = OverviewResult(code=0, cards={})

    payload = result.model_dump()

    assert payload["code"] == 0
    assert "data" not in payload


@pytest.mark.parametrize(
    ("media_source", "media_id", "expected_identity"),
    [
        (MediaSource.TMDB.value, "123", (MediaSource.TMDB, "123")),
        (MediaSource.TMDB.value, None, None),
        (None, "123", None),
        ("invalid source", "123", None),
        (MediaSource.TMDB.value, "0", None),
        (" ", " ", None),
    ],
)
def test_rename_history_passes_only_complete_media_identity(
    monkeypatch,
    media_source,
    media_id,
    expected_identity,
) -> None:
    """历史身份非法或不完整时仅按 meta/mtype 识别，不伪造 TMDB ID。"""
    history = SimpleNamespace(
        type=MediaType.MOVIE.value,
        media_source=media_source,
        media_id=media_id,
        torrent_name="Example.2024.1080p",
        seasons="",
        episodes="",
    )
    calls = []

    class Chain:
        """记录媒体识别参数的测试链。"""

        @staticmethod
        def recognize_media(**kwargs):
            """记录一次识别调用并返回未命中。"""
            calls.append(kwargs)
            return None

    plugin = SimpleNamespace(
        _rename_exclude_dirs="",
        chain=Chain(),
        _rename_movie_format="{{ title }}",
        _rename_tv_format="{{ title }}",
    )
    monkeypatch.setattr(rename_service, "get_download_history_by_hash", lambda _hash: history)
    monkeypatch.setattr(
        rename_service,
        "_build_rename_meta",
        lambda _torrent_name, _history: SimpleNamespace(),
    )
    monkeypatch.setattr(rename_service, "save_rename_record", lambda *_args, **_kwargs: None)

    rename_service.rename_torrent(
        plugin,
        SimpleNamespace(),
        "qbittorrent",
        "deadbeef",
        "Example.2024.1080p",
        "/downloads/example",
    )

    assert calls
    first_call = calls[0]
    if expected_identity:
        assert (first_call["media_source"], first_call["media_id"]) == expected_identity
    else:
        assert "media_source" not in first_call
        assert "media_id" not in first_call


def test_site_adapter_merges_v3_database_record_and_indexer(monkeypatch) -> None:
    """站点模板必须叠加 V3 数据库凭据，且数据库字段优先。"""
    site = SimpleNamespace(
        id=7,
        name="实验站",
        domain="tracker.example",
        url="https://tracker.example/",
        pri=1,
        rss="https://tracker.example/rss",
        cookie="secret-cookie",
        ua="test-agent",
        apikey="secret-api-key",
        token=None,
        proxy=False,
        render=False,
        public=False,
        is_active=True,
        downloader="qb-main",
        note={"passkey": "secret-passkey", "uid": "42"},
    )

    class FakeSiteOper:
        """提供固定站点记录的 SiteOper 替身。"""

        @staticmethod
        def get_by_domain(_domain):
            """返回固定站点。"""
            return site

        @staticmethod
        def list_order_by_pri():
            """返回固定站点列表。"""
            return [site]

    class FakeSitesHelper:
        """提供固定索引模板的 SitesHelper 替身。"""

        @staticmethod
        def get_indexer(_domain):
            """返回不含用户凭据的模板。"""
            return {"id": 99, "name": "模板站", "url": "https://template.invalid/"}

    monkeypatch.setattr(moviepilot_adapter, "SiteOper", FakeSiteOper)
    monkeypatch.setattr(moviepilot_adapter, "SitesHelper", FakeSitesHelper)

    result = moviepilot_adapter.get_site_indexer("tracker.example")

    assert result["id"] == 7
    assert result["name"] == "实验站"
    assert result["cookie"] == "secret-cookie"
    assert result["passkey"] == "secret-passkey"
    assert moviepilot_adapter.list_custom_site_dicts() == []


def test_v3_source_removes_legacy_host_contracts() -> None:
    """V3 源码不得调用旧宿主合同或依赖已安装插件路径。"""
    sources = "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in PLUGIN_ROOT.rglob("*.py")
    )

    assert "SystemConfigKey.UserSite" not in sources
    assert "tmdbid=" not in sources
    assert "app.plugins.downloadmanagerlocal" not in sources
    for legacy_module in (
        "app.core.event",
        "app.core.meta.metabase",
        "app.core.metainfo",
        "app.core.config",
        "app.helper.downloader",
        "app.helper.sites",
        "app.helper.torrent",
        "app.log",
        "app.utils.http",
        "app.utils.media",
        "app.utils.string",
    ):
        assert f"from {legacy_module}" not in sources


def test_v3_database_imports_use_oper_modules() -> None:
    """V3 数据库访问必须使用当前 Oper 模块路径。"""
    imports = []
    legacy_modules = {
        "app.db.downloadhistory_oper",
        "app.db.site_oper",
        "app.db.systemconfig_oper",
        "app.db.user_oper",
    }
    current_modules = {
        "app.db.oper.downloadhistory",
        "app.db.oper.site",
        "app.db.oper.systemconfig",
        "app.db.oper.user",
    }
    for path in PLUGIN_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.extend((node.module, alias.name) for alias in node.names)

    imported_modules = {module for module, _symbol in imports}
    assert imported_modules.isdisjoint(legacy_modules)
    assert current_modules <= imported_modules


def test_v3_notification_channel_import_uses_current_contract() -> None:
    """V3 消息发送必须使用 NotificationChannel 而非旧 MessageChannel。"""
    imports = []
    for path in PLUGIN_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.schemas.types":
                imports.extend(alias.name for alias in node.names)

    assert "MessageChannel" not in imports
    assert "NotificationChannel" in imports


def test_v3_message_imports_use_current_message_type() -> None:
    """V3 通知消息不得继续导入已迁移的 NotificationType 符号。"""
    legacy_imports = []
    current_imports = []
    for path in PLUGIN_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module not in {
                "app.schemas",
                "app.schemas.types",
            }:
                continue
            for alias in node.names:
                if alias.name == "NotificationType":
                    legacy_imports.append((path.relative_to(PLUGIN_ROOT), node.lineno))
                elif alias.name == "MessageType":
                    current_imports.append((path.relative_to(PLUGIN_ROOT), node.lineno))

    assert legacy_imports == []
    assert current_imports


def test_v3_internal_imports_match_symbol_allowlist() -> None:
    """内部宿主导入只能保留尚无 SDK 出口的 TorrentHelper。"""
    internal_prefixes = (
        "app.application.",
        "app.domain.",
        "app.foundation.",
        "app.adapters.",
        "app.runtime.",
        "app.infrastructure.",
        "app.services.",
    )
    allowed = {
        ("app.application.torrent", "TorrentHelper"),
        ("app.services.torrent", "TorrentHelper"),
    }
    actual = set()
    for path in PLUGIN_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if node.module.startswith(internal_prefixes):
                actual.update((node.module, alias.name) for alias in node.names)

    assert actual == allowed


def test_frontend_uses_injected_plugin_instance_id() -> None:
    """Vue 联邦组件必须使用宿主注入的实例 ID，不得硬编码源插件路径。"""
    api_source = (PLUGIN_ROOT / "frontend/src/components/api.js").read_text(encoding="utf-8")
    config_source = (PLUGIN_ROOT / "frontend/src/components/Config.vue").read_text(encoding="utf-8")
    page_source = (PLUGIN_ROOT / "frontend/src/components/Page.vue").read_text(encoding="utf-8")

    assert "plugin/DownloadManagerLocal" not in api_source
    assert "pluginId" in config_source and "sourcePluginId" in config_source
    assert "pluginId" in page_source and "sourcePluginId" in page_source


def test_runtime_mutable_state_is_instance_owned(monkeypatch) -> None:
    """运行事件、队列、缓存和锁不得在插件实例之间共享。"""
    base_class = DownloadManagerLocal.__mro__[1]
    monkeypatch.setattr(base_class, "__init__", lambda _self: None)
    first = DownloadManagerLocal()
    second = DownloadManagerLocal()

    for name in (
        "_event",
        "_recheck_torrents",
        "_torrent_tags",
        "_tracker_mappings",
        "_iyuu_error_caches",
        "_iyuu_success_caches",
        "_iyuu_permanent_error_caches",
        "_seed_recheck_lock",
    ):
        assert getattr(first, name) is not getattr(second, name)


def test_iyuu_helper_cache_is_instance_owned() -> None:
    """IYUU 站点缓存和汇报摘要不得由类属性隐式共享。"""
    first = IyuuHelper("")
    second = IyuuHelper("")

    assert first._sites is not second._sites
    assert first._sid_sha1 is second._sid_sha1 is None
