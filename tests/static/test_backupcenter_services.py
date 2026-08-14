"""备份中心核心服务的隔离行为测试。"""

import copy
import importlib.util
import sys
import zipfile
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[2] / "plugins.v3" / "backupcenter"
PACKAGE_NAME = "backupcenter_under_test"


def _package(name: str, path: Path) -> ModuleType:
    """创建可加载相对导入模块的测试包。"""
    module = ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
    return module


def _load(name: str, path: Path):
    """从指定路径加载测试模块。"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _SystemConfigKeyValue:
    """提供宿主 SystemConfigKey 的最小 value 契约。"""

    value = "UserInstalledPlugins"


class _SystemConfigKey:
    """提供备份服务导入所需的系统键枚举桩。"""

    UserInstalledPlugins = _SystemConfigKeyValue()


class _PluginColumn:
    """记录 SQLAlchemy `in_` 条件值。"""

    def in_(self, values):
        """返回便于测试断言的过滤条件。"""
        return tuple(values)


class _PluginData:
    """模拟宿主 PluginData 模型构造行为。"""

    plugin_id = _PluginColumn()

    def __init__(self, plugin_id, key, value):
        """保存待插入的插件数据字段。"""
        if key == "raise-constructor":
            raise RuntimeError("constructor failed")
        self.plugin_id_value = plugin_id
        self.key = key
        self.value = value


app_module = _package("app", PLUGIN_DIR)
app_core_module = _package("app.core", PLUGIN_DIR)
app_core_config_module = ModuleType("app.core.config")
app_core_config_module.settings = SimpleNamespace(SECRET_KEY="backupcenter-test-secret")
sys.modules["app.core.config"] = app_core_config_module
app_core_module.config = app_core_config_module
app_log_module = ModuleType("app.log")
app_log_module.logger = SimpleNamespace(warning=lambda *_args, **_kwargs: None)
sys.modules["app.log"] = app_log_module
app_schemas_module = _package("app.schemas", PLUGIN_DIR)
app_schemas_types_module = ModuleType("app.schemas.types")
app_schemas_types_module.SystemConfigKey = _SystemConfigKey
sys.modules["app.schemas.types"] = app_schemas_types_module
app_schemas_module.types = app_schemas_types_module
app_db_module = _package("app.db", PLUGIN_DIR)
app_db_module.ScopedSession = None
app_db_models_module = _package("app.db.models", PLUGIN_DIR)
app_db_plugindata_module = ModuleType("app.db.models.plugindata")
app_db_plugindata_module.PluginData = _PluginData
sys.modules["app.db.models.plugindata"] = app_db_plugindata_module
app_db_models_module.plugindata = app_db_plugindata_module
app_module.core = app_core_module
app_module.schemas = app_schemas_module
app_module.db = app_db_module
apscheduler_module = _package("apscheduler", PLUGIN_DIR)
apscheduler_triggers_module = _package("apscheduler.triggers", PLUGIN_DIR)
apscheduler_cron_module = ModuleType("apscheduler.triggers.cron")


class _CronTrigger:
    """记录调度服务提交给 APScheduler 的 Cron 表达式。"""

    calls = []

    @classmethod
    def from_crontab(cls, expression):
        """记录并返回 Cron 表达式。"""
        cls.calls.append(expression)
        return expression


apscheduler_cron_module.CronTrigger = _CronTrigger
sys.modules["apscheduler.triggers.cron"] = apscheduler_cron_module
apscheduler_triggers_module.cron = apscheduler_cron_module
apscheduler_module.triggers = apscheduler_triggers_module

version_module = ModuleType("version")
version_module.APP_VERSION = "v3.0.0"
sys.modules["version"] = version_module

_package(PACKAGE_NAME, PLUGIN_DIR)
_package(f"{PACKAGE_NAME}.model", PLUGIN_DIR / "model")
_package(f"{PACKAGE_NAME}.service", PLUGIN_DIR / "service")
backup_model = _load(
    f"{PACKAGE_NAME}.model.backup", PLUGIN_DIR / "model" / "backup.py"
)
crypto_module = _load(
    f"{PACKAGE_NAME}.service.crypto_service",
    PLUGIN_DIR / "service" / "crypto_service.py",
)
secret_module = _load(
    f"{PACKAGE_NAME}.service.secret_service",
    PLUGIN_DIR / "service" / "secret_service.py",
)
manifest_module = _load(
    f"{PACKAGE_NAME}.service.manifest_service",
    PLUGIN_DIR / "service" / "manifest_service.py",
)
guide_module = _load(
    f"{PACKAGE_NAME}.service.offline_guide_service",
    PLUGIN_DIR / "service" / "offline_guide_service.py",
)
backup_module = _load(
    f"{PACKAGE_NAME}.service.backup_service",
    PLUGIN_DIR / "service" / "backup_service.py",
)
restore_module = _load(
    f"{PACKAGE_NAME}.service.restore_service",
    PLUGIN_DIR / "service" / "restore_service.py",
)
scheduler_module = _load(
    f"{PACKAGE_NAME}.service.scheduler",
    PLUGIN_DIR / "service" / "scheduler.py",
)


class _SystemConfig:
    """提供备份创建所需的宿主配置快照。"""

    def all(self):
        """返回包含已安装插件的测试配置。"""
        return {"UserInstalledPlugins": ["DemoPlugin"], "Language": "zh-CN"}


class _PluginDataOper:
    """提供备份创建所需的 PluginData 读取接口。"""

    def get_data_all(self, plugin_id):
        """返回指定插件的空数据集合。"""
        return []


class _Plugin:
    """提供备份服务所需的最小插件宿主接口。"""

    def __init__(self, root: Path):
        """初始化临时数据目录和持久化记录。"""
        self.root = root
        self.systemconfig = _SystemConfig()
        self.plugindata = _PluginDataOper()
        self.records = {}

    def get_data_path(self):
        """返回插件测试数据目录。"""
        path = self.root / "plugin-state"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_data(self, key):
        """读取测试持久化记录。"""
        return self.records.get(key)

    def save_data(self, key, value):
        """保存测试持久化记录。"""
        self.records[key] = value

    def del_data(self, key):
        """删除测试持久化记录。"""
        self.records.pop(key, None)


class _Query:
    """记录事务中的查询、过滤和删除调用。"""

    def __init__(self, session):
        """绑定测试会话。"""
        self.session = session

    def filter(self, condition):
        """记录目标插件 ID。"""
        self.session.filtered = condition
        return self

    def delete(self, synchronize_session=False):
        """记录删除调用且不提交。"""
        self.session.deleted = True
        self.session.synchronize_session = synchronize_session


class _Session:
    """模拟 SQLAlchemy 会话的事务状态。"""

    def __init__(self):
        """初始化事务观测字段。"""
        self.filtered = None
        self.deleted = False
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0

    def query(self, model):
        """返回测试查询对象。"""
        assert model is _PluginData
        return _Query(self)

    def add_all(self, rows):
        """消费待写入行，模拟 SQLAlchemy 收集对象。"""
        self.added.extend(list(rows))

    def commit(self):
        """记录唯一提交。"""
        self.commits += 1

    def rollback(self):
        """记录回滚。"""
        self.rollbacks += 1

    def close(self):
        """记录会话关闭。"""
        self.closed += 1


class _ScopedSessionFactory:
    """模拟宿主 ScopedSession 工厂和 remove 接口。"""

    def __init__(self, session):
        """保存即将返回的测试会话。"""
        self.session = session
        self.calls = 0
        self.removes = 0

    def __call__(self):
        """返回测试会话。"""
        self.calls += 1
        return self.session

    def remove(self):
        """记录 scoped session 清理。"""
        self.removes += 1


def _service_settings(root: Path):
    """构造不会访问真实 MoviePilot 数据的服务配置。"""
    config_path = root / "config"
    plugin_path = config_path / "plugins"
    cookie_path = config_path / "cookies"
    plugin_path.mkdir(parents=True)
    cookie_path.mkdir(parents=True)
    return SimpleNamespace(
        CONFIG_PATH=config_path,
        PLUGIN_DATA_PATH=plugin_path,
        COOKIE_PATH=cookie_path,
        DB_TYPE="sqlite",
    )


def test_backup_payload_and_export_keep_recovery_tutorials(tmp_path, monkeypatch):
    """加密负载与导出 ZIP 都保留完整离线教程和校验工具。"""
    plugin = _Plugin(tmp_path)
    service = backup_module.BackupService(plugin, _service_settings(tmp_path))

    def fake_encrypt(source, destination, password):
        """复制 ZIP 以便测试检查加密前负载结构。"""
        assert password == "correct horse battery staple"
        destination.write_bytes(source.read_bytes())
        return {
            "enabled": True,
            "format": "backupcenter-aesgcm-v1",
            "cipher": "AES-256-GCM",
            "kdf": {"name": "scrypt"},
            "nonce": "test",
            "tag": "test",
        }

    monkeypatch.setattr(backup_module.CryptoService, "encrypt_file", fake_encrypt)
    scope = backup_model.BackupScope(
        mp_settings=True,
        plugin_settings=False,
        plugin_data=False,
        plugin_files=False,
        app_env=False,
        cookies=False,
        database=False,
    )
    manifest = service.create_backup(
        scope,
        plugin_ids=["DemoPlugin"],
        password="correct horse battery staple",
        display_name="升级前备份",
    )
    assert manifest["display_name"] == "升级前备份"
    backup_path = service.get_backup_path(manifest["backup_id"])

    with zipfile.ZipFile(backup_path / "payload.enc") as payload:
        payload_names = set(payload.namelist())
        assert "payload/docs/RECOVERY-GUIDE.md" in payload_names
        assert "payload/docs/RECOVERY-CHECKLIST.txt" in payload_names
        assert "payload/manifest.json" in payload_names

    archive_path, archive_name = service.create_export_archive(manifest["backup_id"])
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            prefix = "升级前备份/"
            for relative in (
                "RECOVERY-GUIDE.md",
                "RECOVERY-CHECKLIST.txt",
                "manifest.public.json",
                "payload.enc",
                "checksums.sha256",
                "tools/verify-backup.ps1",
                "tools/decrypt-backup.py",
                "tools/restore-sqlite.ps1",
                "tools/restore-postgresql.ps1",
            ):
                assert f"{prefix}{relative}" in names
        assert archive_name == "升级前备份.zip"
    finally:
        archive_path.unlink(missing_ok=True)


def test_empty_password_creates_plain_zip_backup(tmp_path):
    """未配置口令时创建普通 ZIP，且公开摘要明确标记未加密。"""
    plugin = _Plugin(tmp_path)
    service = backup_module.BackupService(plugin, _service_settings(tmp_path))
    scope = backup_model.BackupScope(
        mp_settings=True,
        plugin_settings=False,
        plugin_data=False,
        plugin_files=False,
        app_env=False,
        cookies=False,
        database=False,
    )

    manifest = service.create_backup(scope, plugin_ids=["DemoPlugin"])
    backup_path = service.get_backup_path(manifest["backup_id"])

    assert manifest["encrypted"] is False
    assert manifest["display_name"].startswith("DemoPlugin-配置-")
    assert manifest["encryption"] == {"enabled": False, "format": "none"}
    assert (backup_path / "payload.zip").is_file()
    assert not (backup_path / "payload.enc").exists()
    with zipfile.ZipFile(backup_path / "payload.zip") as payload:
        assert "payload/docs/RECOVERY-GUIDE.md" in payload.namelist()


def test_backup_display_name_removes_filename_control_characters(tmp_path):
    """自定义名称移除路径与控制字符，避免污染导出文件名。"""
    plugin = _Plugin(tmp_path)
    service = backup_module.BackupService(plugin, _service_settings(tmp_path))
    scope = backup_model.BackupScope(
        plugin_settings=False,
        plugin_data=False,
        plugin_files=False,
        app_env=False,
    )

    manifest = service.create_backup(
        scope,
        plugin_ids=["DemoPlugin"],
        display_name=' 升级前/<配置>:\n测试? ',
    )

    assert manifest["display_name"] == "升级前 配置 测试"


def test_legacy_public_manifest_without_display_name_is_normalized(tmp_path):
    """旧公开清单缺少展示名时只在读取结果中补齐兼容值。"""
    plugin = _Plugin(tmp_path)
    service = backup_module.BackupService(plugin, _service_settings(tmp_path))
    backup_path = service.get_backup_root() / "backup-legacy-emergency"
    backup_path.mkdir()
    manifest_path = backup_path / "manifest.public.json"
    manifest_module.ManifestService.write_json(
        manifest_path,
        {
            "backup_id": "backup-legacy-emergency",
            "backup_kind": "emergency",
            "created_at": "2026-08-13T14:11:28+00:00",
            "scope": {"plugin_data": True},
            "selected_plugin_ids": ["P115StrmHelper"],
        },
    )

    backups = service.list_backups()

    assert backups[0]["display_name"].startswith("恢复前应急备份-")
    assert "display_name" not in manifest_module.ManifestService.read_json(
        manifest_path
    )


def test_manual_backup_selection_defaults_empty_and_maps_both_targets():
    """两种手动备份默认全空，选择后映射各自的明确范围。"""
    with pytest.raises(backup_model.ScopeError, match="至少选择配置或数据"):
        backup_model.ManualBackupSelection.from_payload(None)

    configuration = backup_model.ManualBackupSelection.from_payload(
        {"configuration": True}
    ).to_backup_scope()
    assert configuration.to_dict() == {
        "mp_settings": False,
        "plugin_settings": True,
        "plugin_data": False,
        "plugin_files": False,
        "app_env": False,
        "cookies": False,
        "database": False,
    }

    data = backup_model.ManualBackupSelection.from_payload(
        {"data": True}
    ).to_backup_scope()
    assert data.plugin_settings is False
    assert data.plugin_data is True
    assert data.plugin_files is True

    with pytest.raises(backup_model.ScopeError, match="至少选择一项备份内容"):
        backup_model.ManualBackupSelection.from_payload(None, "moviepilot")

    moviepilot = backup_model.ManualBackupSelection.from_payload(
        {
            "mp_settings": True,
            "app_env": True,
            "plugin_settings": True,
            "cookies": True,
            "plugin_data": True,
            "plugin_files": True,
            "database": True,
        },
        "moviepilot",
    ).to_backup_scope()
    assert all(moviepilot.to_dict().values())


def test_manual_backup_service_rejects_zero_or_multiple_plugins(tmp_path):
    """服务层只对插件手动包强制要求一个插件。"""
    plugin = _Plugin(tmp_path)
    plugin.systemconfig.all = lambda: {
        "UserInstalledPlugins": ["DemoPlugin", "OtherPlugin"]
    }
    service = backup_module.BackupService(plugin, _service_settings(tmp_path))
    scope = backup_model.ManualBackupSelection.from_payload(
        {"configuration": True}
    ).to_backup_scope()

    for plugin_ids in ([], ["DemoPlugin", "OtherPlugin"]):
        with pytest.raises(backup_module.BackupServiceError, match="必须选择一个插件"):
            service.create_backup(scope, plugin_ids=plugin_ids)

    moviepilot = service.create_backup(
        backup_model.BackupScope(
            mp_settings=True,
            plugin_settings=False,
            plugin_data=False,
            plugin_files=False,
            app_env=False,
        ),
        plugin_ids=[],
        manual_target="moviepilot",
    )
    assert moviepilot["selected_plugin_ids"] == []
    assert moviepilot["manual_target"] == "moviepilot"


def test_generated_backup_names_cover_moviepilot_plugin_and_automatic(tmp_path):
    """手动包按对象命名，自动整包只使用自动备份和日期。"""
    plugin = _Plugin(tmp_path)
    service = backup_module.BackupService(plugin, _service_settings(tmp_path))
    manual_scope = backup_model.ManualBackupSelection.from_payload(
        {"configuration": True, "data": True}
    ).to_backup_scope()

    manual = service.create_backup(
        manual_scope,
        plugin_ids=["DemoPlugin"],
        plugin_names={"DemoPlugin": "演示插件"},
    )
    moviepilot = service.create_backup(
        backup_model.BackupScope(
            mp_settings=True,
            plugin_settings=False,
            plugin_data=False,
            plugin_files=False,
            app_env=False,
        ),
        plugin_ids=[],
        manual_target="moviepilot",
    )
    automatic = service.create_backup(
        backup_model.BackupScope(),
        plugin_ids=["DemoPlugin"],
        backup_kind="automatic",
        plugin_names={"DemoPlugin": "演示插件"},
    )

    assert manual["display_name"].startswith("演示插件-配置和数据-")
    assert manual["selected_plugins"] == [{"id": "DemoPlugin", "name": "演示插件"}]
    assert moviepilot["display_name"].startswith("MoviePilot-配置-")
    assert automatic["display_name"].startswith("自动备份-")
    assert "演示插件" not in automatic["display_name"]


def test_automatic_bundle_can_restore_one_plugins_data_only(tmp_path, monkeypatch):
    """自动整包允许只选择其中一个插件的数据在线恢复。"""
    public_manifest = {
        "format_version": 2,
        "backup_id": "backup-automatic",
        "display_name": "自动备份-20260813-030000",
        "created_at": "2026-08-13T03:00:00+00:00",
        "source_mp_version": "v3.0.0",
        "scope": {
            "mp_settings": True,
            "plugin_settings": True,
            "plugin_data": True,
            "plugin_files": True,
            "app_env": True,
            "cookies": False,
            "database": False,
        },
        "selected_plugin_ids": ["PluginA", "PluginB"],
        "selected_plugins": [
            {"id": "PluginA", "name": "插件甲"},
            {"id": "PluginB", "name": "插件乙"},
        ],
        "content_counts": {
            "mp_settings": 1,
            "plugin_settings": 2,
            "plugin_data": 2,
            "plugin_files": 2,
            "cookies": 0,
        },
        "database": {"type": "none", "included": False},
        "emergency": False,
        "backup_kind": "automatic",
        "encrypted": False,
    }
    payload = tmp_path / "payload"
    payload.mkdir()
    manifest_module.ManifestService.write_json(
        payload / "manifest.json", public_manifest
    )
    backup_service = SimpleNamespace(
        read_public_manifest=lambda backup_id: public_manifest,
        create_backup=lambda *_args, **_kwargs: {"backup_id": "backup-emergency"},
    )
    plugin = SimpleNamespace(get_backup_password=lambda: "")
    service = restore_module.RestoreService(plugin, backup_service)

    @contextmanager
    def payload_directory(*_args, **_kwargs):
        """返回测试私有清单目录。"""
        yield payload

    restored_plugins = []
    monkeypatch.setattr(service, "_payload_directory", payload_directory)
    monkeypatch.setattr(
        service, "_stop_target_plugins", lambda plugin_ids: (object(), list(plugin_ids))
    )
    monkeypatch.setattr(
        service,
        "_restore_plugin_data",
        lambda _payload, plugin_ids: restored_plugins.extend(plugin_ids) or 1,
    )
    monkeypatch.setattr(
        service,
        "_reload_target_plugins",
        lambda _manager, plugin_ids: (list(plugin_ids), []),
    )

    result = service.restore_logical(
        backup_id="backup-automatic",
        selection=backup_model.RestoreSelection(plugin_data=True),
        plugin_ids=["PluginA"],
    )

    assert restored_plugins == ["PluginA"]
    assert result["restored"]["plugin_data"] == 1
    assert result["reloaded"] == ["PluginA"]


def test_restore_rejects_content_missing_from_backup():
    """部分恢复不能请求自动包未保存的内容。"""
    manifest = {
        "backup_id": "backup-config-only",
        "source_mp_version": "v3.0.0",
        "scope": {"plugin_settings": True, "plugin_data": False},
        "selected_plugin_ids": ["PluginA"],
        "database": {"included": False},
    }
    backup_service = SimpleNamespace(read_public_manifest=lambda _backup_id: manifest)
    service = restore_module.RestoreService(SimpleNamespace(), backup_service)

    with pytest.raises(restore_module.RestoreServiceError, match="不在这份备份中"):
        service.restore_logical(
            backup_id="backup-config-only",
            selection=backup_model.RestoreSelection(plugin_data=True),
            plugin_ids=["PluginA"],
        )


def test_encrypted_preview_does_not_require_password_before_dialog():
    """加密备份可先完成公开预检，再由恢复对话框收集历史口令。"""
    manifest = {
        "backup_id": "backup-encrypted",
        "source_mp_version": "v3.0.0",
        "database": {"included": False},
        "encryption": {"enabled": True},
    }
    backup_service = SimpleNamespace(
        verify_backup=lambda backup_id: {
            "manifest": manifest,
            "verified_files": ["payload.enc", "manifest.public.json"],
        }
    )
    service = restore_module.RestoreService(SimpleNamespace(), backup_service)

    preview = service.preview("backup-encrypted")

    assert preview["encrypted"] is True
    assert preview["online_restore_allowed"] is True
    assert preview["verified_files"] == ["payload.enc", "manifest.public.json"]


def test_optional_crypto_round_trip_and_wrong_password_cleanup(tmp_path):
    """流式 AES-GCM 可往返解密，错误口令不会留下部分明文。"""
    source = tmp_path / "payload.zip"
    encrypted = tmp_path / "payload.enc"
    restored = tmp_path / "restored.zip"
    source.write_bytes((b"backupcenter" * 100000) + b"end")

    manifest = crypto_module.CryptoService.encrypt_file(
        source, encrypted, "correct horse battery staple"
    )
    assert manifest["enabled"] is True
    assert manifest["tag"]
    crypto_module.CryptoService.decrypt_file(
        encrypted, restored, "correct horse battery staple", manifest
    )
    assert restored.read_bytes() == source.read_bytes()

    with pytest.raises(crypto_module.BackupCryptoError, match="口令错误"):
        crypto_module.CryptoService.decrypt_file(
            encrypted, restored, "incorrect horse battery staple", manifest
        )
    assert not restored.exists()


def test_backup_password_accepts_four_characters_and_rejects_three():
    """加密口令允许四位，三位仍明确拒绝。"""
    assert crypto_module.CryptoService.validate_password(
        "1234", allow_empty=False
    ) == "1234"
    with pytest.raises(crypto_module.BackupCryptoError, match="至少需要 4 个字符"):
        crypto_module.CryptoService.validate_password("123", allow_empty=False)


def test_backup_password_is_encrypted_at_rest_and_can_be_cleared(tmp_path):
    """配置页口令仅以密文持久化并支持清除。"""
    plugin = _Plugin(tmp_path)
    service = secret_module.SecretService(plugin)
    password = "correct horse battery staple"

    service.set_password(password)

    record = plugin.records[service._data_key]
    assert record["version"] == 1
    assert password not in str(record)
    assert service.has_password() is True
    assert service.get_password() == password

    service.clear_password()
    assert service.has_password() is False
    assert service.get_password() == ""


def test_standard_saturday_cron_is_converted_for_apscheduler():
    """UI 的标准 Cron 周六值转换为 APScheduler 的周六值。"""
    plugin = SimpleNamespace(
        get_state=lambda: True,
        _config={
            "auto_backup_enabled": True,
            "auto_backup_cron": "0 3 * * 6",
        },
        run_automatic_backup=lambda: None,
    )

    services = scheduler_module.build_services(plugin)

    assert len(services) == 1
    assert services[0]["trigger"] == "0 3 * * 5"
    assert _CronTrigger.calls[-1] == "0 3 * * 5"


def test_standard_cron_weekday_lists_and_ranges_convert_consistently():
    """标准 Cron 的星期列表、范围和周日七值均稳定转换。"""
    convert = scheduler_module._to_apscheduler_crontab

    assert convert("15 4 * * 1-5") == "15 4 * * 0,1,2,3,4"
    assert convert("0 0 * * 0,6") == "0 0 * * 5,6"
    assert convert("0 0 * * 7") == "0 0 * * 6"
    assert convert("*/5 * * * *") == "*/5 * * * *"


def test_automatic_retention_deletes_only_old_automatic_backups(tmp_path):
    """按数量清理只删除最旧自动备份并保留手动备份。"""
    plugin = _Plugin(tmp_path)
    service = backup_module.BackupService(plugin, _service_settings(tmp_path))
    records = [
        ("backup-auto-new", "2026-08-12T03:00:00+00:00", "automatic"),
        ("backup-manual", "2026-08-11T03:00:00+00:00", "manual"),
        ("backup-auto-mid", "2026-08-10T03:00:00+00:00", "automatic"),
        ("backup-auto-old", "2026-08-09T03:00:00+00:00", "automatic"),
    ]
    for backup_id, created_at, backup_kind in records:
        backup_path = service.get_backup_root() / backup_id
        backup_path.mkdir()
        manifest_module.ManifestService.write_json(
            backup_path / "manifest.public.json",
            {
                "backup_id": backup_id,
                "created_at": created_at,
                "backup_kind": backup_kind,
            },
        )
    plugin.records["backup_index"] = [
        {"backup_id": backup_id} for backup_id, _, _ in records
    ]

    deleted = service.prune_automatic_backups(2)

    assert deleted == ["backup-auto-old"]
    assert (service.get_backup_root() / "backup-manual").is_dir()
    assert (service.get_backup_root() / "backup-auto-mid").is_dir()
    assert not (service.get_backup_root() / "backup-auto-old").exists()


def test_plugin_data_restore_commits_all_selected_plugins_once(tmp_path, monkeypatch):
    """多个插件的 PluginData 删除和重建只提交一次事务。"""
    payload = tmp_path / "payload"
    manifest_module.ManifestService.write_json(
        payload / "plugin_data.json",
        {
            "PluginA": [{"key": "one", "value": {"count": 1}}],
            "PluginB": [{"key": "two", "value": [1, 2]}],
        },
    )
    session = _Session()
    factory = _ScopedSessionFactory(session)
    monkeypatch.setattr(restore_module, "ScopedSession", factory)
    monkeypatch.setattr(restore_module, "PluginData", _PluginData)
    service = restore_module.RestoreService(SimpleNamespace(), SimpleNamespace())

    restored = service._restore_plugin_data(payload, ["PluginA", "PluginB"])

    assert restored == 2
    assert session.filtered == ("PluginA", "PluginB")
    assert session.deleted is True
    assert session.synchronize_session is False
    assert session.commits == 1
    assert session.rollbacks == 0
    assert session.closed == 1
    assert factory.removes == 1
    assert [(row.plugin_id_value, row.key) for row in session.added] == [
        ("PluginA", "one"),
        ("PluginB", "two"),
    ]


def test_plugin_data_restore_rolls_back_when_any_row_fails(tmp_path, monkeypatch):
    """任一 PluginData 行构造失败时回滚且不提交。"""
    payload = tmp_path / "payload"
    manifest_module.ManifestService.write_json(
        payload / "plugin_data.json",
        {
            "PluginA": [
                {"key": "one", "value": 1},
                {"key": "raise-constructor", "value": 2},
            ]
        },
    )
    session = _Session()
    factory = _ScopedSessionFactory(session)
    monkeypatch.setattr(restore_module, "ScopedSession", factory)
    monkeypatch.setattr(restore_module, "PluginData", _PluginData)
    service = restore_module.RestoreService(SimpleNamespace(), SimpleNamespace())

    with pytest.raises(RuntimeError, match="constructor failed"):
        service._restore_plugin_data(payload, ["PluginA"])

    assert session.commits == 0
    assert session.rollbacks == 1
    assert session.closed == 1
    assert factory.removes == 1


def test_invalid_plugin_data_is_rejected_before_transaction(tmp_path, monkeypatch):
    """插件数据格式错误时不得打开删除事务。"""
    payload = tmp_path / "payload"
    manifest_module.ManifestService.write_json(
        payload / "plugin_data.json",
        {"PluginA": [{"key": "", "value": "invalid"}]},
    )
    session = _Session()
    factory = _ScopedSessionFactory(session)
    monkeypatch.setattr(restore_module, "ScopedSession", factory)
    service = restore_module.RestoreService(SimpleNamespace(), SimpleNamespace())

    with pytest.raises(restore_module.RestoreServiceError, match="插件数据项无效"):
        service._restore_plugin_data(payload, ["PluginA"])

    assert factory.calls == 0
    assert session.deleted is False


def test_restore_selection_and_private_manifest_are_boundary_checked():
    """明确空选与公开/私有 manifest 不一致都会阻断恢复。"""
    service = restore_module.RestoreService(SimpleNamespace(), SimpleNamespace())
    assert service._resolve_selected_plugin_ids(["PluginA"], None) == ["PluginA"]
    assert service._resolve_selected_plugin_ids(["PluginA"], []) == []
    with pytest.raises(backup_model.ScopeError, match="插件 ID 无效"):
        service._resolve_selected_plugin_ids(["../PluginA"], None)

    public_manifest = {
        "format_version": 1,
        "backup_id": "backup-test",
        "source_mp_version": "v3.0.0",
        "scope": {"plugin_data": True},
        "selected_plugin_ids": ["PluginA"],
        "content_counts": {"plugin_data": 1},
        "database": {"type": "none", "included": False},
        "emergency": False,
    }
    private_manifest = copy.deepcopy(public_manifest)
    service._verify_private_manifest(public_manifest, private_manifest)
    private_manifest["selected_plugin_ids"] = ["PluginB"]
    with pytest.raises(restore_module.RestoreServiceError, match="不匹配"):
        service._verify_private_manifest(public_manifest, private_manifest)


def test_explicit_empty_plugin_selection_stays_empty_and_excludes_self(tmp_path):
    """显式空选不退化为全部插件，且备份中心自身永不进入范围。"""
    plugin = type("BackupCenter", (_Plugin,), {})(tmp_path)
    plugin.systemconfig.all = lambda: {
        "UserInstalledPlugins": ["DemoPlugin", "BackupCenter"]
    }
    service = backup_module.BackupService(plugin, _service_settings(tmp_path))

    assert service.available_plugin_ids() == ["DemoPlugin"]
    assert service._select_plugin_ids(["DemoPlugin"], None) == ["DemoPlugin"]
    assert service._select_plugin_ids(["DemoPlugin"], []) == []


def test_windows_style_traversal_paths_are_rejected():
    """反斜杠穿越与盘符路径不得绕过 POSIX 路径校验。"""
    for value in (r"..\outside", r"C:outside", r"folder\outside"):
        with pytest.raises(manifest_module.ManifestError, match="不安全路径"):
            manifest_module.ManifestService._safe_relative(value)
        with pytest.raises(restore_module.RestoreServiceError, match="不安全路径"):
            restore_module.RestoreService._safe_zip_path(value)


def test_plugin_file_restore_removes_successful_rollback_directory(tmp_path):
    """插件目录成功原子替换后不遗留恢复前临时副本。"""
    payload = tmp_path / "payload"
    source = payload / "files" / "plugins" / "PluginA"
    source.mkdir(parents=True)
    (source / "state.txt").write_text("new", encoding="utf-8")
    settings = _service_settings(tmp_path)
    target = settings.PLUGIN_DATA_PATH / "PluginA"
    target.mkdir()
    (target / "state.txt").write_text("old", encoding="utf-8")
    backup_service = SimpleNamespace(settings=settings)
    service = restore_module.RestoreService(SimpleNamespace(), backup_service)

    assert service._restore_plugin_files(payload, ["PluginA"]) == ["PluginA"]
    assert (target / "state.txt").read_text(encoding="utf-8") == "new"
    assert list(settings.PLUGIN_DATA_PATH.glob(".PluginA.pre-restore-*")) == []


def test_partial_plugin_stop_failure_reloads_already_stopped_plugins(monkeypatch):
    """停止后续插件失败时，先前已停止插件必须立即恢复运行。"""
    manager = SimpleNamespace(running_plugins={"PluginA": object(), "PluginB": object()})

    def stop(plugin_id):
        """只允许第一个插件成功停止。"""
        if plugin_id == "PluginA":
            manager.running_plugins.pop(plugin_id)

    def reload_plugin(plugin_id):
        """模拟宿主重新加载已停止插件。"""
        manager.running_plugins[plugin_id] = object()

    manager.stop = stop
    manager.reload_plugin = reload_plugin
    plugin_module = ModuleType("app.core.plugin")
    plugin_module.PluginManager = lambda: manager
    monkeypatch.setitem(sys.modules, "app.core.plugin", plugin_module)

    with pytest.raises(restore_module.RestoreServiceError, match="PluginB"):
        restore_module.RestoreService._stop_target_plugins(["PluginA", "PluginB"])

    assert set(manager.running_plugins) == {"PluginA", "PluginB"}


def test_plugin_reload_reports_failed_targets():
    """插件重载异常不得中断其余插件，并返回精确失败列表。"""
    manager = SimpleNamespace(running_plugins={})

    def reload_plugin(plugin_id):
        """模拟一个成功重载和一个失败重载。"""
        if plugin_id == "PluginA":
            manager.running_plugins[plugin_id] = object()
        else:
            raise RuntimeError("reload failed")

    manager.reload_plugin = reload_plugin
    reloaded, failed = restore_module.RestoreService._reload_target_plugins(
        manager, ["PluginA", "PluginB"]
    )

    assert reloaded == ["PluginA"]
    assert failed == ["PluginB"]
