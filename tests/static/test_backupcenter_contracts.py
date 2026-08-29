"""BackupCenter repository and federation contract gates."""

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = ROOT / "plugins.v3" / "backupcenter"
ENTRYPOINT = PLUGIN_DIR / "__init__.py"
PLUGIN_JSON = PLUGIN_DIR / "plugin.json"
PACKAGE_JSON = ROOT / "package.v3.json"
PACKAGE_V2_JSON = ROOT / "package.v2.json"
API_CONTROLLER = PLUGIN_DIR / "controller" / "api.py"
FRONTEND_API = PLUGIN_DIR / "frontend" / "src" / "components" / "api.js"
VITE_CONFIG = PLUGIN_DIR / "frontend" / "vite.config.js"
REMOTE_ENTRY = PLUGIN_DIR / "dist" / "assets" / "remoteEntry.js"
AGENT_CONTEXT = PLUGIN_DIR / "ai_spec" / "plugin_context.md"


def _json(path: Path) -> dict:
    """读取测试所需 JSON 对象。"""
    return json.loads(path.read_text(encoding="utf-8"))


def _entrypoint_class() -> ast.ClassDef:
    """返回 BackupCenter 插件类 AST。"""
    tree = ast.parse(ENTRYPOINT.read_text(encoding="utf-8"))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BackupCenter"
    )


def _class_string(class_node: ast.ClassDef, name: str) -> str:
    """读取插件类中的字符串常量。"""
    for statement in class_node.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        if any(
            isinstance(target, ast.Name) and target.id == name for target in targets
        ):
            value = statement.value
            assert isinstance(value, ast.Constant) and isinstance(value.value, str)
            return value.value
    raise AssertionError(f"BackupCenter.{name} is not a string literal")


def test_backupcenter_metadata_is_consistent_and_v3_scoped():
    """包索引、插件 manifest 与入口类共享同一身份和 V3 宿主边界。"""
    package = _json(PACKAGE_JSON)["BackupCenter"]
    package_v2 = _json(PACKAGE_V2_JSON)
    manifest = _json(PLUGIN_JSON)
    plugin_class = _entrypoint_class()

    for metadata_key, class_key in (
        ("name", "plugin_name"),
        ("description", "plugin_desc"),
        ("version", "plugin_version"),
        ("icon", "plugin_icon"),
        ("color", "plugin_color"),
        ("author", "plugin_author"),
        ("author_url", "author_url"),
    ):
        assert package[metadata_key] == manifest[metadata_key]
        assert package[metadata_key] == _class_string(plugin_class, class_key)
    assert package["version"] == manifest["version"] == "3.0.2"
    assert "v2" not in package and "v2" not in manifest
    assert package["release"] is True
    assert package["history"] == manifest["history"] == {
        "v3.0.2": "[1]移除重复整库备份;[2]聚焦插件配置恢复;[3]接入宿主恢复点",
        "v3.0.1": "[1]新增运行日志;[2]适配V3接口;[3]修复插件加载",
        "v3.0.0": "[1]备份MP与插件;[2]支持加密校验;[3]附带离线恢复"
    }
    assert "BackupCenter" not in package_v2
    assert not (ROOT / "plugins.v2" / "backupcenter" / "__init__.py").exists()
    assert package["system_version"] == manifest["system_version"] == ">=3.0.0"
    assert package["author_url"] == "https://github.com/z2561221"


def test_backupcenter_federation_contract_is_complete():
    """V3 插件格式暴露配置页、详情页和负责入口切换的全页组件。"""
    vite_source = VITE_CONFIG.read_text(encoding="utf-8")
    entrypoint_source = ENTRYPOINT.read_text(encoding="utf-8")
    remote_source = REMOTE_ENTRY.read_text(encoding="utf-8")

    assert re.search(
        r'return\s+["\']vue["\']\s*,\s*["\']dist/assets["\']',
        entrypoint_source,
    )
    for expose in ("Config", "Page"):
        assert f"'./{expose}'" in vite_source
        assert f'"./{expose}"' in remote_source
    assert "'./AppPage'" in vite_source
    assert '"./AppPage":' in remote_source
    assert (PLUGIN_DIR / "frontend" / "src" / "components" / "AppPage.vue").exists()
    assert "./Dashboard" not in vite_source


def test_backupcenter_api_is_bearer_only_and_exports_offline_package():
    """浏览器 API 只使用宿主 bearer 客户端，并提供完整离线包导出。"""
    controller = API_CONTROLLER.read_text(encoding="utf-8")
    frontend = FRONTEND_API.read_text(encoding="utf-8")

    assert "from app.api.endpoints.plugin import verify_token" in controller
    assert "app.application.security.access" not in controller
    assert "app.core.security" not in controller
    assert '"auth": "bear"' in controller
    assert '"/backups/{backup_id}/export"' in controller
    assert "FileResponse" in controller
    assert "BackgroundTask" in controller
    assert "api.get(" in frontend and "api.post(" in frontend
    assert "responseType: 'blob'" in frontend
    assert "readEnvelopeData" in frontend
    assert "unwrapResponse" not in frontend
    assert "response instanceof Blob" in frontend
    assert '"response_model": response_model' in controller
    assert "def _success" not in controller
    assert "fetch(" not in frontend
    assert "API_TOKEN" not in frontend


def test_backupcenter_exposes_sanitized_operation_logs():
    """运行日志通过 Bearer API 和联邦页面展示脱敏后的最近记录。"""
    controller = API_CONTROLLER.read_text(encoding="utf-8")
    page = (PLUGIN_DIR / "frontend" / "src" / "components" / "Page.vue").read_text(
        encoding="utf-8"
    )
    service = (
        PLUGIN_DIR / "service" / "operation_log_service.py"
    ).read_text(encoding="utf-8")

    assert '("/logs", controller.endpoint_operation_logs, ["GET"]' in controller
    assert "BackupLogsData" in controller
    assert "app.sdk.logging import logger" in service
    assert '_data_key = "operation_logs"' in service
    assert "_limit = 200" in service
    for marker in (
        "运行日志",
        "getPluginApi(props.api, 'logs')",
        "formatDuration",
        "operationLabel",
        "bc-log-list",
    ):
        assert marker in page


def test_backupcenter_requires_superuser_and_registers_no_sidebar():
    """敏感备份 API 要求超级用户且插件不注册独立侧栏。"""
    controller = API_CONTROLLER.read_text(encoding="utf-8")
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")

    assert "def _require_superuser" in controller
    assert 'getattr(token_payload, "super_user", False)' in controller
    assert '"superuser_required"' in controller
    assert "raise HTTPException" in controller
    assert "permissions" not in controller
    assert "def get_sidebar_nav" not in entrypoint


def test_backupcenter_frontend_keeps_online_and_offline_restore_separate():
    """主页面不得把完整数据库恢复伪装成运行中一键操作。"""
    controller = API_CONTROLLER.read_text(encoding="utf-8")
    page = (PLUGIN_DIR / "frontend" / "src" / "components" / "Page.vue").read_text(
        encoding="utf-8"
    )
    for marker in (
        "在线选择性恢复",
        "宿主数据库恢复点",
        "数据库文件与 app.env 不会在线替换",
        "留空时尝试使用配置页当前保存的口令",
        "下载备份包",
        "备份恢复说明",
    ):
        assert marker in page
    assert "restore/logical" in page
    assert "restoreForm.pluginIds = []" in page
    assert "confirmation" not in page
    assert "confirmation" not in controller
    assert "确认文本必须与备份 ID 完全一致" not in (
        PLUGIN_DIR / "service" / "restore_service.py"
    ).read_text(encoding="utf-8")
    assert "restore/database" not in page
    assert "showSettings" in page
    assert "show_switch" in page
    assert "settingsShortcutVisible" in page
    assert 'aria-label="打开配置"' in page
    assert "@click=\"emit('switch')\"" in page


def test_backupcenter_plugin_selects_use_chinese_names_and_id_values():
    """插件选择器显示宿主中文名，但提交值继续使用稳定插件 ID。"""
    controller = API_CONTROLLER.read_text(encoding="utf-8")
    page = (PLUGIN_DIR / "frontend" / "src" / "components" / "Page.vue").read_text(
        encoding="utf-8"
    )

    assert 'manager.get_plugin_attr(plugin_id, "plugin_name")' in controller
    assert '"plugin_options": self._plugin_options(installed)' in controller
    assert ':items="createPluginOptions"' in page
    assert ':items="restorePluginOptions"' in page
    assert page.count('item-title="title"') >= 2
    assert page.count('item-value="value"') >= 2


def test_backupcenter_password_is_configured_outside_normal_plugin_config():
    """口令通过独立 API 密文保存且普通配置提交不携带口令。"""
    controller = API_CONTROLLER.read_text(encoding="utf-8")
    config = (
        PLUGIN_DIR / "frontend" / "src" / "components" / "Config.vue"
    ).read_text(encoding="utf-8")
    save_body = re.search(r"function save\(\) \{(?P<body>.*?)\n\}", config, re.DOTALL)

    assert save_body is not None
    assert "password" not in save_body.group("body")
    assert '"/encryption/status"' in controller
    assert '"/encryption/secret"' in controller
    assert "postPluginApi(props.api, 'encryption/secret'" in config
    assert "口令单独密文保存" in config
    assert "至少需要 4 个字符" in config
    assert "最低 4 位" in config
    assert "不设置口令时生成普通 ZIP" in config


def test_backupcenter_automatic_backup_defaults_to_saturday_and_count_retention():
    """自动备份默认每周六 03:00 并按数量保留。"""
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
    scheduler = (PLUGIN_DIR / "service" / "scheduler.py").read_text(encoding="utf-8")
    config = (
        PLUGIN_DIR / "frontend" / "src" / "components" / "Config.vue"
    ).read_text(encoding="utf-8")

    assert '"auto_backup_cron": "0 3 * * 6"' in entrypoint
    assert '"retention_count": 5' in entrypoint
    assert "_to_apscheduler_crontab" in scheduler
    assert "VCronField" in config
    assert 'v-model="form.auto_backup_cron"' in config
    assert 'label="运行周期"' in config
    assert 'type="time"' not in config
    assert "每周六 03:00" in config
    assert "只清理最旧的自动备份" in config
    for marker in (
        "周期备份范围 · 已选",
        "这里只影响每周自动备份",
        "form.auto_backup_scope",
        "至少选择一项",
    ):
        assert marker in config


def test_backupcenter_automatic_scope_is_persisted_and_used_by_scheduler():
    """周期备份范围来自配置页并参与自动任务，而不是固定写死。"""
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
    controller = API_CONTROLLER.read_text(encoding="utf-8")
    api = FRONTEND_API.read_text(encoding="utf-8")
    config = (
        PLUGIN_DIR / "frontend" / "src" / "components" / "Config.vue"
    ).read_text(encoding="utf-8")

    assert '"auto_backup_scope"' in entrypoint
    assert 'BackupScope.from_payload(self._config.get("auto_backup_scope"))' in entrypoint
    assert "BackupCenterApiController._plugin_name_map(plugin_ids)" in entrypoint
    assert "plugin_ids=plugin_ids" in entrypoint
    assert '"/config"' in controller
    assert "plugin/BackupCenter/config" in api
    assert "auto_backup_scope" in config
    assert "legacy_database_scope" in entrypoint
    assert 'for key in ("mp_settings", "app_env", "cookies")' in entrypoint


def test_backupcenter_basic_settings_expose_immediate_automatic_backup():
    """基础设置提供立即执行按钮并接入受保护 Bearer API。"""
    controller = API_CONTROLLER.read_text(encoding="utf-8")
    config = (
        PLUGIN_DIR / "frontend" / "src" / "components" / "Config.vue"
    ).read_text(encoding="utf-8")

    assert "def run_automatic_backup" in controller
    assert "endpoint_run_automatic_backup" in controller
    assert '("/run", controller.endpoint_run_automatic_backup, ["POST"]' in controller
    assert "plugin.run_automatic_backup()" in controller
    assert "立即运行一次" in config
    assert "postPluginApi(props.api, 'run')" in config
    assert "runLoading" in config
    assert ":loading=\"runLoading\"" in config
    assert "按当前周期备份范围立即生成一份自动备份" in config


def test_backupcenter_scope_uses_plain_language_configuration_and_data_groups():
    """手动创建支持 MoviePilot 细项与单插件配置、数据两类。"""
    page = (PLUGIN_DIR / "frontend" / "src" / "components" / "Page.vue").read_text(
        encoding="utf-8"
    )

    for marker in (
        "备份对象",
        'value="moviepilot"',
        'value="plugin"',
        "每份手动备份只打包一个插件",
        "默认全部不选",
        'label="MoviePilot 设置"',
        'label="环境变量（app.env）"',
        'label="登录 Cookie"',
        'label="插件保存的数据（PluginData）"',
        'label="插件文件和缓存"',
        'label="插件设置"',
        'label="插件数据"',
        "在线恢复哪些内容",
        "只能恢复这份备份里实际保存过的内容",
        "可以只选一项，也可以按需多选",
        'label="恢复 MoviePilot 配置"',
        'label="恢复插件配置"',
        'label="恢复插件数据"',
        'label="选择要恢复的插件"',
        "不包含 app.env 和插件安装清单",
        "数据包含 PluginData、插件文件和缓存",
    ):
        assert marker in page
    assert 'configuration: false' in page
    assert 'data: false' in page
    assert 'mp_settings: false' in page
    assert 'mp_settings: restoreForm.selection.mpSettings' in page
    assert 'plugin_settings: restoreForm.selection.pluginSettings && hasPluginSelection' in page
    assert 'plugin_data: restoreForm.selection.pluginData && hasPluginSelection' in page
    assert 'restoreNeedsPlugins.value || restoreForm.pluginIds.length > 0' in page


def test_backupcenter_records_use_readable_names_with_stable_ids():
    """手动包按插件中文名和内容命名，自动包按日期命名。"""
    controller = API_CONTROLLER.read_text(encoding="utf-8")
    service = (PLUGIN_DIR / "service" / "backup_service.py").read_text(encoding="utf-8")
    page = (PLUGIN_DIR / "frontend" / "src" / "components" / "Page.vue").read_text(
        encoding="utf-8"
    )

    assert "ManualBackupSelection.from_payload" in controller
    assert 'target == "plugin"' in controller
    assert 'manual_target=target' in controller
    assert 'plugin_names=self._plugin_name_map(plugin_ids)' in controller
    assert '"display_name": normalized_display_name' in service
    assert 'subject_name = "MoviePilot"' in service
    assert 'return f"{subject_name}-{content_label}-{local_time}"' in service
    assert 'return f"{cls._backup_kind_labels[backup_kind]}-{local_time}"' in service
    assert 'return temporary_path, f"{display_name}.zip"' in service
    assert "backupDisplayName(item)" in page
    assert "backupOptionTitle(item)" in page
    assert ':items="backupOptions"' in page
    assert 'label="选择一个插件"' in page
    assert ':disabled="!createReady"' in page
    assert "backupDownloadName(item" in page


def test_backupcenter_restore_submit_keeps_disabled_state_readable():
    """恢复按钮禁用时保留清晰警示语义并在操作区纵向居中。"""
    page = (PLUGIN_DIR / "frontend" / "src" / "components" / "Page.vue").read_text(
        encoding="utf-8"
    )

    assert 'class="bc-restore-submit"' in page
    assert (
        '<VCardActions class="bc-restore-actions">\n'
        '          <VSpacer />\n'
        '          <VBtn variant="text" @click="restoreDialog = false">取消</VBtn>'
        in page
    )
    assert ':disabled="!restoreReady"' in page
    assert ".bc-restore-actions { min-height: 76px; align-items: center; padding-block: 10px; }" in page
    assert '.bc-restore-actions > :deep(.v-btn) { align-self: center; margin-block: 0; }' in page
    assert ".bc-restore-submit.v-btn--disabled.v-btn--variant-flat" in page
    assert "color: rgba(var(--v-theme-warning), .72)" in page
    assert "background: rgba(var(--v-theme-warning), .12)" in page
    assert "border: 1px solid rgba(var(--v-theme-warning), .38)" in page
    assert ".bc-restore-submit.v-btn--disabled :deep(.v-btn__overlay)" in page
    assert "opacity: 0" in page


def test_backupcenter_layout_has_stable_mobile_constraints():
    """联邦页面使用稳定配置外壳并在窄屏切换为横向导航。"""
    page = (PLUGIN_DIR / "frontend" / "src" / "components" / "Page.vue").read_text(
        encoding="utf-8"
    )
    config = (
        PLUGIN_DIR / "frontend" / "src" / "components" / "Config.vue"
    ).read_text(encoding="utf-8")

    for source in (page, config):
        assert "@media (max-width: 760px)" in source
    assert "overflow-x: auto" in page
    assert "minmax(0, 1fr)" in page
    assert "width: min(960px, calc(100vw - 48px))" in page
    assert "height: min(660px, calc(100dvh - 48px))" in page
    assert ":global(.bc-page-overlay)" in page
    assert "flex: 1 1 auto" in page
    assert "overflow-y: auto" in page
    assert "min-height: calc(100dvh" not in page
    assert "height: min(860px, 100dvh)" in page
    assert "max-height: 100%" in page
    assert ".bc-record-grid { display: grid; grid-template-columns: 1fr; gap: 12px; }" in page
    for marker in (
        "activeMain = ref('overview')",
        "运行总览",
        "基础设置",
        "高级选项",
        "width: min(1120px, calc(100vw - 48px))",
        "height: clamp(760px, calc(100dvh - 48px), 860px)",
        "width: 160px",
        "overflow-x: auto",
        "height: min(860px, calc(100dvh - 16px))",
    ):
        assert marker in config


def test_backupcenter_python_definitions_have_chinese_docstrings():
    """生产 Python 定义保留中文文档字符串。"""
    gaps = []
    for path in PLUGIN_DIR.rglob("*.py"):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            docstring = ast.get_docstring(node) or ""
            if not re.search(r"[\u4e00-\u9fff]", docstring):
                gaps.append(f"{path.relative_to(ROOT).as_posix()}::{node.name}")
    assert gaps == []


def test_backupcenter_context_records_non_negotiable_restore_boundaries():
    """稳定上下文记录格式、事务、教程和生产恢复边界。"""
    source = AGENT_CONTEXT.read_text(encoding="utf-8")
    for marker in (
        "plugins.v3/backupcenter",
        "v3:false",
        "不修改 MoviePilot 主程序",
        "ScopedSession",
        "SystemConfigOper.set()",
        "不承诺跨键全局事务",
        "多个插件目录之间不承诺全局原子性",
        "BackupCenter` 自身始终从插件范围排除",
        "在线恢复拒绝 `BackupCenter` 自身",
        "备份口令仅在配置页通过独立 Bearer API 设置",
        "payload.zip | payload.enc",
        "payload/docs/RECOVERY-GUIDE.md",
        "完整数据库恢复始终要求管理员停机",
        "禁止 push、合并、发布",
    ):
        assert marker in source
