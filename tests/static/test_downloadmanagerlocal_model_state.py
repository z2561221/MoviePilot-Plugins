from __future__ import annotations

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"


def _load_state_module():
    """加载状态模型模块，避免引入完整 MoviePilot 运行时。"""
    path = PLUGIN_DIR / "model" / "state.py"
    spec = importlib.util.spec_from_file_location("downloadmanagerlocal_model_state", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakePlugin:
    """提供最小 get_data/save_data 行为的测试替身。"""

    def __init__(self, data=None):
        self.data = dict(data or {})
        self.saved = []

    def get_data(self, key):
        return self.data.get(key)

    def save_data(self, key, value):
        self.saved.append((key, value))
        self.data[key] = value


def test_persisted_state_keys_keep_legacy_storage_names():
    state = _load_state_module()

    assert state.RENAME_RECORDS_KEY == "rename_records"
    assert state.RENAME_RETRY_STATE_KEY == "rename_retry_state"
    assert state.SEED_RECHECK_QUEUE_KEY == "seed_recheck_queue"
    assert state.IYUU_CACHE_CONFIG_KEYS == (
        "iyuu_permanent_error_caches",
        "iyuu_error_caches",
        "iyuu_success_caches",
    )


def test_dynamic_iyuu_keys_keep_existing_format():
    state = _load_state_module()

    assert state.iyuu_history_key("abc123") == "iyuu_abc123"
    assert state.iyuu_source_key("def456") == "iyuu_source_def456"


def test_persisted_state_key_inventory_documents_dynamic_and_static_keys():
    state = _load_state_module()

    inventory = state.PERSISTED_STATE_KEYS

    assert inventory["rename_history"] == "rename_records"
    assert inventory["rename_retry_state"] == "rename_retry_state"
    assert inventory["seed_recheck_queue"] == "seed_recheck_queue"
    assert inventory["iyuu_history"] == "iyuu_<source_hash>"
    assert inventory["iyuu_source"] == "iyuu_source_<seed_hash>"


def test_dict_data_helpers_preserve_non_dict_fallback_behavior():
    state = _load_state_module()
    plugin = FakePlugin({
        "valid": {"a": 1},
        "invalid": ["not", "dict"],
    })

    assert state.load_dict_data(plugin, "valid") == {"a": 1}
    assert state.load_dict_data(plugin, "invalid") == {}
    assert state.load_dict_data(plugin, "missing") == {}

    state.save_dict_data(plugin, "valid", {"b": 2})
    state.save_dict_data(plugin, "invalid", None)

    assert plugin.saved == [("valid", {"b": 2}), ("invalid", {})]
