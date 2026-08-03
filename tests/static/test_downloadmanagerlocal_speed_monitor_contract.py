from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"

EXPECTED_DEFAULTS = {
    "speed_monitor_enabled": False,
    "speed_monitor_downloaders": [],
    "speed_monitor_mode": "auto",
    "speed_monitor_tolerance": 1.5,
    "speed_monitor_min_samples": 5,
    "speed_monitor_interval_minutes": 5,
    "speed_monitor_grace_minutes": 10,
    "speed_monitor_consecutive_abnormal_samples": 2,
    "speed_monitor_manual_speed_bps": {},
    "speed_monitor_floor_speed_bps": {},
    "speed_monitor_notification_type": "Plugin",
}


def _load_module(name: str, relative_path: str):
    """按文件路径加载不依赖 MoviePilot 运行时的轻量模块。"""
    path = PLUGIN_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _get_form_defaults() -> dict:
    """从插件入口 AST 提取 Vue 表单默认配置。"""
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
    assert isinstance(defaults_node, ast.Dict)
    defaults = {}
    for key_node, value_node in zip(defaults_node.keys, defaults_node.values):
        if key_node is None:
            assert isinstance(value_node, ast.Name)
            assert value_node.id == "SPEED_MONITOR_CONFIG_DEFAULTS"
            defaults.update(EXPECTED_DEFAULTS)
            continue
        defaults[ast.literal_eval(key_node)] = ast.literal_eval(value_node)
    return defaults


def test_speed_monitor_defaults_are_complete_and_exposed_by_form():
    config = _load_module("downloadmanagerlocal_utils_config", "utils/config.py")

    assert config.SPEED_MONITOR_CONFIG_DEFAULTS == EXPECTED_DEFAULTS
    form_defaults = _get_form_defaults()
    assert {key: form_defaults[key] for key in EXPECTED_DEFAULTS} == EXPECTED_DEFAULTS


def test_speed_monitor_config_normalizes_ranges_modes_and_per_downloader_speeds():
    config = _load_module("downloadmanagerlocal_utils_config_normalize", "utils/config.py")

    normalized = config.normalize_speed_monitor_config({
        "speed_monitor_enabled": 1,
        "speed_monitor_downloaders": ["qb-main", "", "qb-main", 123, "tr-backup"],
        "speed_monitor_mode": "invalid",
        "speed_monitor_tolerance": 1.0,
        "speed_monitor_min_samples": 0,
        "speed_monitor_interval_minutes": 999,
        "speed_monitor_grace_minutes": -5,
        "speed_monitor_consecutive_abnormal_samples": 99,
        "speed_monitor_manual_speed_bps": {
            "qb-main": 1024,
            "bad-zero": 0,
            "bad-text": "fast",
        },
        "speed_monitor_floor_speed_bps": {
            "tr-backup": "2048.5",
            "bad-negative": -1,
        },
        "speed_monitor_notification_type": "",
    })

    assert normalized == {
        "speed_monitor_enabled": True,
        "speed_monitor_downloaders": ["qb-main", "tr-backup"],
        "speed_monitor_mode": "auto",
        "speed_monitor_tolerance": 1.5,
        "speed_monitor_min_samples": 1,
        "speed_monitor_interval_minutes": 60,
        "speed_monitor_grace_minutes": 0,
        "speed_monitor_consecutive_abnormal_samples": 10,
        "speed_monitor_manual_speed_bps": {"qb-main": 1024.0},
        "speed_monitor_floor_speed_bps": {"tr-backup": 2048.5},
        "speed_monitor_notification_type": "Plugin",
    }


def test_speed_monitor_persisted_state_keys_are_explicit_and_versioned():
    state = _load_module("downloadmanagerlocal_model_state_monitor", "model/state.py")

    assert state.SPEED_MONITOR_SCHEMA_VERSION == 1
    assert state.SPEED_MONITOR_SESSIONS_KEY == "speed_monitor_sessions"
    assert state.SPEED_MONITOR_BASELINES_KEY == "speed_monitor_baselines"
    assert state.SPEED_MONITOR_ALERTS_KEY == "speed_monitor_alerts"
    assert state.PERSISTED_STATE_KEYS["speed_monitor_sessions"] == state.SPEED_MONITOR_SESSIONS_KEY
    assert state.PERSISTED_STATE_KEYS["speed_monitor_baselines"] == state.SPEED_MONITOR_BASELINES_KEY
    assert state.PERSISTED_STATE_KEYS["speed_monitor_alerts"] == state.SPEED_MONITOR_ALERTS_KEY


def test_speed_monitor_delete_contract_is_fixed_to_all_torrent_data():
    config = _load_module("downloadmanagerlocal_utils_config_delete", "utils/config.py")

    assert config.SPEED_MONITOR_DELETE_FILE is True
    assert "删除种子及全部数据" in config.SPEED_MONITOR_DELETE_WARNING
    assert "不可恢复" in config.SPEED_MONITOR_DELETE_WARNING
    assert "订阅助手增强版" in config.SPEED_MONITOR_EXTERNAL_LINK_WARNING
