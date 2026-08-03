from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"
CONFIG = PLUGIN_DIR / "frontend" / "src" / "components" / "Config.vue"
ROUTES = PLUGIN_DIR / "controller" / "api.py"


def _source() -> str:
    return CONFIG.read_text(encoding="utf-8")


def test_speed_monitor_configuration_fields_and_ranges_are_visible():
    source = _source()

    for field in [
        "speed_monitor_enabled",
        "speed_monitor_downloaders",
        "speed_monitor_mode",
        "speed_monitor_tolerance",
        "speed_monitor_min_samples",
        "speed_monitor_interval_minutes",
        "speed_monitor_grace_minutes",
        "speed_monitor_consecutive_abnormal_samples",
        "speed_monitor_manual_speed_bps",
        "speed_monitor_floor_speed_bps",
        "speed_monitor_notification_type",
    ]:
        assert field in source
    assert "MiB/s" in source
    assert 'min="0.01" max="102400"' in source
    assert "自动稳健基准" in source
    assert "手动最低速度" in source


def test_runtime_flow_is_internal_and_external_link_is_explanatory_only():
    source = _source()
    script = source.split("</script>", 1)[0]
    runtime_flow = re.search(
        r"const runtimeFlows = \[(?P<body>.*?)\n\]", script, re.S
    )

    assert runtime_flow
    flow_source = runtime_flow.group("body")
    expected = [
        "下载任务",
        "监控会话",
        "有效采样",
        "基准/手动阈值",
        "TG通知",
        "关闭 / 删除并清理",
    ]
    assert all(step in flow_source for step in expected)
    assert [flow_source.index(step) for step in expected] == sorted(
        flow_source.index(step) for step in expected
    )
    assert "SubscribeAssistantEnhanced" not in flow_source
    assert "订阅助手增强版（SubscribeAssistantEnhanced）" in source
    assert "不属于本插件运行链路" in source


def test_monitor_status_matches_overview_contract_and_warns_before_deletion():
    source = _source()

    for field in [
        "active_sessions",
        "pending_alerts",
        "selected_downloaders",
        "reference_speed_bps",
        "relative_only",
        "last_disposition",
    ]:
        assert field in source
    assert "删除种子及全部数据，且不可恢复" in source
    assert "关闭告警不会删除任务" in source
    assert "reset_speed_monitor_baseline" in source
    assert "重置自动基准" in source


def test_monitor_layout_has_mobile_and_tablet_overflow_guards():
    source = _source()

    assert re.search(r"\.dm-config\s*\{[^}]*max-width:\s*100%", source, re.S)
    assert re.search(r"\.dm-content\s*\{[^}]*min-width:\s*0", source, re.S)
    assert re.search(r"@media \(max-width: 760px\).*?\.dm-monitor-summary, .*?grid-template-columns:\s*1fr", source, re.S)
    assert re.search(r"@media \(min-width: 761px\) and \(max-width: 960px\)", source)
    assert "overflow-wrap: anywhere" in source


def test_speed_baseline_reset_route_is_bearer_protected():
    source = ROUTES.read_text(encoding="utf-8")

    route = re.search(
        r'"path": "/reset_speed_monitor_baseline"(?P<body>.*?)}', source, re.S
    )
    assert route
    assert '"auth": "bear"' in route.group("body")
    assert '"methods": ["POST"]' in route.group("body")
