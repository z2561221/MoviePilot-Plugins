from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"
CONFIG = PLUGIN_DIR / "frontend" / "src" / "components" / "Config.vue"
ROUTES = PLUGIN_DIR / "controller" / "api.py"


def _source() -> str:
    """读取下载中心配置页源码。"""
    return CONFIG.read_text(encoding="utf-8")


def test_upload_limit_configuration_exposes_confirmed_fields_and_units():
    """上传限速配置页应展示已确认的字段、默认值和 KiB/s 单位。"""
    source = _source()

    for field in [
        "upload_limit_enabled",
        "upload_limit_downloaders",
        "upload_limit_downloader_limits_kib",
        "upload_limit_site_rules",
        "upload_limit_grace_minutes",
    ]:
        assert field in source
    assert "上传限速" in source
    assert "qBittorrent / Transmission" in source
    assert "新种宽限（分钟）" in source
    assert "默认 30" in source
    assert "单位为 KiB/s（1 Mbps ≈ 122 KiB/s）" in source
    assert "仍受对应下载器总上传上限" in source


def test_upload_limit_only_renders_selected_downloaders_and_requires_caps():
    """未选择的下载器不应显示额度输入，已选择项必须提示正整数总上限。"""
    source = _source()

    selected = re.search(
        r"const uploadSelectedDownloaders = computed\(\(\) => \{(?P<body>.*?)\n\}\)",
        source,
        re.S,
    )
    assert selected
    assert "filter(item => selected.has(item.value))" in selected.group("body")
    assert 'v-for="item in uploadSelectedDownloaders"' in source
    assert "uploadMissingLimits" in source
    assert "请至少选择一个 qBittorrent 或 Transmission 下载器" in source
    assert "尚未设置正整数总上限" in source
    assert "保存后上传限速不会启动" in source


def test_upload_limit_site_priority_and_default_group_wording_is_explicit():
    """站点策略应固定默认组、相对权重和跨下载器共享硬上限语义。"""
    source = _source()

    for title, value in [("高", "high"), ("中", "medium"), ("低", "low")]:
        assert f"{{ title: '{title}', value: '{value}' }}" in source
    assert "默认组" in source
    assert "form.tag_siteprefix || '🏠'" in source
    assert "优先级中 · 不设置独立站点上限 · 仅受下载器总上限控制" in source
    assert "跨下载器共享硬上限" in source
    assert "4 / 2 / 1 相对权重" in source
    assert "并非固定分成 10 份" in source
    assert "57.1% / 28.6% / 14.3%" in source
    assert "每 30 秒动态转给仍有上传需求的任务" in source


def test_upload_limit_site_scan_is_opt_in_and_rule_operations_persist_immediately():
    """站点扫描仅服务于策略需求，扫描和清空都应立即保存。"""
    source = _source()

    assert "仅在需要按站点设置优先级或独立上限时扫描；仅使用下载器总上限时无需扫描。" in source
    assert "async function clearUploadSiteRules()" in source
    assert "postPluginJsonApi(props.api, 'upload_limit_site_rules_update', { rules: {} })" in source
    assert "form.upload_limit_site_rules = {}" in source
    assert "站点策略已清空并立即生效；点击“立即分配”可马上恢复默认组分配" in source
    assert "rules: Object.fromEntries(Object.entries(form.upload_limit_site_rules || {})" in source
    assert "form.upload_limit_site_rules = response?.rules" in source
    assert "策略已立即生效" in source
    assert 'prepend-icon="mdi-delete-sweep-outline"' in source
    assert ':disabled="!uploadSiteRuleRows.length"' in source
    assert "mdi-home-speedometer" not in source
    assert "{ key: 'upload_sites', title: '站点策略', icon: 'mdi-home-outline' }" in source


def test_upload_limit_status_actions_use_saved_backend_state_and_restore_notice():
    """立即分配和停用恢复应以已保存运行态为准，并说明离线保持行为。"""
    source = _source()

    for endpoint in [
        "upload_limit_status",
        "upload_limit_reallocate",
        "upload_limit_site_tags",
        "upload_limit_site_rules_update",
        "upload_limit_disable_restore",
    ]:
        assert endpoint in source
    assert ':disabled="!uploadLimit.enabled"' in source
    assert ':disabled="!uploadLimit.active && !uploadLimit.enabled"' in source
    assert "MP 或插件离线时，下载器继续保留最后一次已写入的限速" in source
    assert "当前值仍等于插件最后写入值时才会恢复" in source
    assert "若你后来手工修改过，则保留手工值" in source


def test_upload_limit_status_auto_refresh_only_runs_on_visible_status_page():
    """运行状态仅在对应配置页可见时自动刷新，并在离开时清理。"""
    source = _source()

    assert "UPLOAD_STATUS_REFRESH_INTERVAL_MS = 30_000" in source
    assert "activeMain.value === 'upload'" in source
    assert "activeSub.value === 'upload_status'" in source
    assert "document.visibilityState === 'visible'" in source
    assert "refreshUploadLimitStatus({ silent: true })" in source
    assert "window.setInterval(refreshVisibleUploadLimitStatus, UPLOAD_STATUS_REFRESH_INTERVAL_MS)" in source
    assert "document.addEventListener('visibilitychange', syncUploadStatusAutoRefresh)" in source
    assert "document.removeEventListener('visibilitychange', syncUploadStatusAutoRefresh)" in source
    assert "onBeforeUnmount(stopUploadStatusAutoRefresh)" in source


def test_upload_limit_navigation_follows_runtime_order_and_rate_wording_is_clear():
    """上传限速应位于做种校验后，当前速率不得被误解为分配额度。"""
    source = _source()

    seed_position = source.index("{ key: 'seed', title: '做种校验'")
    upload_position = source.index("{ key: 'upload', title: '上传限速'")
    assert seed_position < upload_position
    public_flow_position = source.index("label: '公共链路'")
    upload_flow_position = source.index("label: '上传限速'")
    assert public_flow_position < upload_flow_position
    assert "当前速率" in source
    assert "实际上传流量，不代表分配额度" in source


def test_upload_limit_layout_has_desktop_tablet_and_mobile_guards():
    """上传限速配置和状态布局应在桌面、平板与移动端稳定降级。"""
    source = _source()

    assert re.search(
        r"\.dm-stat-grid\s*\{[^}]*repeat\(6,\s*minmax\(0,\s*1fr\)\)",
        source,
        re.S,
    )
    for css_class in [
        "dm-upload-config-row",
        "dm-upload-site-row",
        "dm-upload-status-grid",
        "dm-upload-site-status-row",
    ]:
        assert f".{css_class}" in source
    assert re.search(
        r"@media \(max-width: 760px\).*?\.dm-upload-config-row, .*?grid-template-columns:\s*1fr",
        source,
        re.S,
    )
    assert re.search(
        r"@media \(min-width: 761px\) and \(max-width: 960px\).*?\.dm-upload-status-grid\s*\{\s*grid-template-columns:\s*1fr",
        source,
        re.S,
    )


def test_upload_limit_routes_are_bearer_protected():
    """上传限速 Vue API 必须保持 bear 认证和预期方法。"""
    source = ROUTES.read_text(encoding="utf-8")
    expected = {
        "/upload_limit_status": "GET",
        "/upload_limit_reallocate": "POST",
        "/upload_limit_site_tags": "POST",
        "/upload_limit_site_rules_update": "POST",
        "/upload_limit_disable_restore": "POST",
    }

    for path, method in expected.items():
        route = re.search(
            rf'"path": "{path}"(?P<body>.*?\n\s*\}})', source, re.S
        )
        assert route
        assert '"auth": "bear"' in route.group("body")
        assert f'"methods": ["{method}"]' in route.group("body")
