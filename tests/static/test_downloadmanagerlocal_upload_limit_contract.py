from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"

EXPECTED_DEFAULTS = {
    "upload_limit_enabled": False,
    "upload_limit_downloaders": [],
    "upload_limit_downloader_limits_kib": {},
    "upload_limit_site_rules": {},
    "upload_limit_grace_minutes": 30,
}


def _load_module(name: str, relative_path: str):
    """按文件路径加载不依赖 MoviePilot 运行时的上传限速模块。"""
    path = PLUGIN_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _get_form_default_factory_name() -> str:
    """从插件入口 AST 提取 Vue 表单默认配置工厂名。"""
    source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    plugin_class = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "DownloadManagerLocal"
    )
    get_form = next(
        node
        for node in plugin_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "get_form"
    )
    return_node = next(node for node in ast.walk(get_form) if isinstance(node, ast.Return))
    assert isinstance(return_node.value, ast.Tuple)
    defaults_node = return_node.value.elts[1]
    assert isinstance(defaults_node, ast.Call)
    assert isinstance(defaults_node.func, ast.Name)
    return defaults_node.func.id


def test_upload_limit_defaults_are_complete_and_exposed_by_form():
    """上传限速应默认关闭，并由统一配置工厂暴露完整默认模型。"""
    config = _load_module("downloadmanagerlocal_upload_config", "utils/config.py")

    assert config.UPLOAD_LIMIT_CONFIG_DEFAULTS == EXPECTED_DEFAULTS
    assert _get_form_default_factory_name() == "build_plugin_config_defaults"
    defaults = config.build_plugin_config_defaults()
    assert {key: defaults[key] for key in EXPECTED_DEFAULTS} == EXPECTED_DEFAULTS


def test_upload_limit_state_and_weight_contracts_are_versioned():
    """持久化 key、schema、协调周期和高/中/低权重必须保持稳定。"""
    state = _load_module("downloadmanagerlocal_upload_state", "model/state.py")
    model = _load_module("downloadmanagerlocal_upload_model", "model/upload_limit.py")

    assert state.UPLOAD_LIMIT_STATE_KEY == "upload_limit_state"
    assert state.PERSISTED_STATE_KEYS["upload_limit_state"] == state.UPLOAD_LIMIT_STATE_KEY
    assert model.UPLOAD_LIMIT_SCHEMA_VERSION == 1
    assert model.UPLOAD_LIMIT_INTERVAL_SECONDS == 30
    assert model.PRIORITY_WEIGHTS == {"high": 4, "medium": 2, "low": 1}
    assert model.DEFAULT_SITE_KEY == "__default__"
    assert model.DEFAULT_SITE_NAME == "默认组"


def test_upload_limit_lifecycle_starts_coordinates_and_explicitly_restores():
    """启用时启动 worker，显式停用时恢复，而普通停服只保留最后限速。"""
    lifecycle = (PLUGIN_DIR / "service" / "lifecycle.py").read_text(encoding="utf-8")
    worker = (PLUGIN_DIR / "service" / "upload_limit_worker.py").read_text(encoding="utf-8")
    handlers = (PLUGIN_DIR / "controller" / "handlers.py").read_text(encoding="utf-8")

    assert "if is_upload_limit_active(plugin):\n        start_upload_limit_worker(plugin)" in lifecycle
    assert "elif upload_state.get(\"management_active\") or upload_state.get(\"downloaders\"):\n        restore_upload_limits(plugin)" in lifecycle
    stop_service = lifecycle.split("def stop_plugin_service", 1)[1]
    assert "stop_upload_limit_worker(plugin)" in stop_service
    assert "restore_upload_limits(plugin)" not in stop_service
    assert "仅结束协调，不恢复已写入下载器的限速" in worker
    assert 'config["upload_limit_enabled"] = False' in handlers
    assert "stop_upload_limit_worker(plugin)" in handlers
    assert "restore_upload_limits(plugin)" in handlers
    assert handlers.index("plugin.update_config(config=config)", handlers.index("def api_upload_limit_disable_restore")) < handlers.index(
        "restore_upload_limits(plugin)", handlers.index("def api_upload_limit_disable_restore")
    )


def test_download_added_wakes_upload_limit_worker_without_real_writes():
    """新增下载事件只负责唤醒协调 worker，实际写入仍由受控周期执行。"""
    entry_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    events_source = (PLUGIN_DIR / "service" / "events.py").read_text(encoding="utf-8")

    event_block = entry_source.split("def on_download_added", 1)[1].split(
        "@eventmanager.register", 1
    )[0]
    assert "return _handle_download_added_event_impl(self, event)" in event_block
    assert "wake_upload_limit_worker(plugin)" in events_source
    assert "_coordinate_upload_limits" not in event_block
    assert "_coordinate_upload_limits" not in events_source
