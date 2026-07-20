"""AgentRank lifecycle, scheduler registration, and stop behavior tests."""

import asyncio
import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_lifecycle_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

runtime_module = importlib.import_module(f"{PACKAGE_NAME}.service.runtime")
lifecycle_module = importlib.import_module(f"{PACKAGE_NAME}.service.lifecycle")
playback_module = importlib.import_module(f"{PACKAGE_NAME}.model.playback")

AgentRankRuntime = runtime_module.AgentRankRuntime
initialize_plugin = lifecycle_module.initialize_plugin
stop_plugin = lifecycle_module.stop_plugin
PlaybackCapability = playback_module.PlaybackCapability

HOME_PROFILE = "emby:home:user-1"
REMOTE_PROFILE = "emby:remote:user-1"


def _identity(server_name, user_id, username):
    """构造测试使用的无凭据 Emby identity。"""
    return {
        "server_name": server_name,
        "user_id": user_id,
        "username": username,
        "profile_id": f"emby:{server_name}:{user_id}",
        "schema_version": 1,
    }


class FakeOrchestrator:
    """Record user order and optionally fail selected users."""

    def __init__(self, failures=None):
        self.failures = set(failures or [])
        self.calls = []

    async def run(self, profile_id, config):
        self.calls.append(profile_id)
        if profile_id in self.failures:
            raise RuntimeError(f"{profile_id} failed")
        return SimpleNamespace(profile_id=profile_id, status="success")


class FakePlugin:
    """Minimal plugin object used by lifecycle assembly tests."""

    def __init__(self):
        self._runtime = None
        self._config = {}
        self._enabled = False
        self._enablement = {}
        self.stop_calls = 0
        self.saved_config = None

    def get_state(self):
        """返回测试插件当前硬门禁状态。"""
        return self._enabled

    def stop_service(self):
        self.stop_calls += 1
        stop_plugin(self)

    def update_config(self, config=None):
        """记录生命周期自动复位后持久化的配置。"""
        self.saved_config = dict(config or {})


class FakePlaybackService:
    """返回指定状态的 Playback Reporting 能力结果。"""

    def __init__(self, status="ready"):
        self.status = status
        self.calls = []

    def probe(self, profile_id, config):
        """记录精确 identity 并返回 mock 能力。"""
        self.calls.append((profile_id, config))
        status = (
            self.status.get(profile_id, "transient_error")
            if isinstance(self.status, dict)
            else self.status
        )
        return PlaybackCapability(profile_id, status, "mock probe")


def _config(**overrides):
    config = {
        "enabled": True,
        "schedule_enabled": True,
        "cron": "0 8 * * *",
        "emby_identities": [
            _identity("home", "user-1", "Alice"),
            _identity("remote", "user-1", "Alice"),
        ],
        "default_profile_id": HOME_PROFILE,
    }
    config.update(overrides)
    return config


def test_disabled_or_schedule_off_runtime_registers_no_service():
    """Neither a disabled plugin nor a disabled schedule exposes a Cron job."""
    trigger_factory = lambda cron: f"trigger:{cron}"
    disabled = AgentRankRuntime(
        FakePlugin(), _config(enabled=False), FakeOrchestrator(), trigger_factory
    )
    schedule_off = AgentRankRuntime(
        FakePlugin(), _config(schedule_enabled=False), FakeOrchestrator(), trigger_factory
    )

    assert disabled.get_services() == []
    assert schedule_off.get_services() == []


def test_valid_schedule_registers_one_stable_service():
    """A valid Cron creates one host-managed service with a stable id."""
    runtime = AgentRankRuntime(
        FakePlugin(), _config(), FakeOrchestrator(), lambda cron: f"trigger:{cron}"
    )

    services = runtime.get_services()

    assert len(services) == 1
    assert services[0]["id"] == "AgentRank.Recommendation"
    assert services[0]["trigger"] == "trigger:0 8 * * *"
    assert services[0]["func"] == runtime.run_scheduled


def test_run_once_registers_one_date_service_and_is_consumed():
    """立即运行不依赖周期设置，并且同一运行时只登记一次。"""
    runtime = AgentRankRuntime(
        FakePlugin(),
        _config(schedule_enabled=False, onlyonce=True),
        FakeOrchestrator(),
        lambda cron: f"trigger:{cron}",
        date_trigger_factory=lambda: "trigger:once",
    )

    services = runtime.get_services()

    assert len(services) == 1
    assert services[0]["id"] == "AgentRank.Recommendation.Once"
    assert services[0]["trigger"] == "trigger:once"
    assert services[0]["func"] == runtime.run_scheduled
    assert runtime.get_services() == []


def test_invalid_cron_is_visible_and_runtime_stays_loadable():
    """Cron parser errors become configuration evidence instead of load failures."""
    def invalid_trigger(_cron):
        raise ValueError("bad cron")

    config = _config(cron="broken")
    runtime = AgentRankRuntime(FakePlugin(), config, FakeOrchestrator(), invalid_trigger)

    assert runtime.get_services() == []
    assert any("cron" in error and "bad cron" in error for error in config["_validation_errors"])


def test_scheduled_users_run_sequentially_and_partial_failure_does_not_abort():
    """A failed Alice run is recorded while Bob still executes afterwards."""
    orchestrator = FakeOrchestrator(failures={HOME_PROFILE})
    runtime = AgentRankRuntime(FakePlugin(), _config(), orchestrator, lambda cron: cron)

    results = asyncio.run(runtime.run_scheduled())

    assert orchestrator.calls == [HOME_PROFILE, REMOTE_PROFILE]
    assert results[0]["profile_id"] == HOME_PROFILE
    assert results[0]["username"] == "Alice"
    assert results[0]["status"] == "failed"
    assert results[1]["profile_id"] == REMOTE_PROFILE
    assert results[1]["username"] == "Alice"
    assert results[1]["status"] == "success"


def test_initialize_normalizes_config_and_replaces_previous_runtime():
    """Reinitialization stops the previous runtime before installing a new one."""
    plugin = FakePlugin()
    old_runtime = SimpleNamespace(stopped=False, stop=lambda: setattr(old_runtime, "stopped", True))
    plugin._runtime = old_runtime
    created = []

    def runtime_factory(plugin_arg, config_arg):
        plugin_arg._playback_service = FakePlaybackService()
        runtime = SimpleNamespace(plugin=plugin_arg, config=config_arg, stopped=False)
        runtime.stop = lambda: setattr(runtime, "stopped", True)
        created.append(runtime)
        return runtime

    initialize_plugin(plugin, _config(), runtime_factory=runtime_factory)

    assert old_runtime.stopped is True
    assert plugin._enabled is True
    assert plugin._runtime is created[0]
    assert plugin._config["default_profile_id"] == HOME_PROFILE


def test_initialize_persists_run_once_reset_but_runtime_keeps_request():
    """初始化会关闭持久化开关，同时把本次请求交给新运行时。"""
    plugin = FakePlugin()
    created = []

    def runtime_factory(plugin_arg, config_arg):
        plugin_arg._playback_service = FakePlaybackService()
        runtime = SimpleNamespace(plugin=plugin_arg, config=config_arg)
        runtime.stop = lambda: None
        created.append(runtime)
        return runtime

    initialize_plugin(
        plugin,
        _config(schedule_enabled=False, onlyonce=True),
        runtime_factory=runtime_factory,
    )

    assert plugin._config["onlyonce"] is False
    assert plugin.saved_config["onlyonce"] is False
    assert "_validation_errors" not in plugin.saved_config
    assert created[0].config["onlyonce"] is True


@pytest.mark.parametrize(
    "status",
    ["not_installed", "permission_error", "transient_error", "emby_unavailable"],
)
def test_initialize_blocks_all_unready_playback_reporting_states(status):
    """依赖未就绪时保留配置意图但关闭实际插件和调度副本。"""
    plugin = FakePlugin()
    probes = []

    def runtime_factory(plugin_arg, config_arg):
        playback = FakePlaybackService(status)
        plugin_arg._playback_service = playback
        probes.append(playback)
        return SimpleNamespace(plugin=plugin_arg, config=config_arg, stop=lambda: None)

    initialize_plugin(plugin, _config(), runtime_factory=runtime_factory)

    assert plugin._config["enabled"] is True
    assert plugin.get_state() is False
    assert plugin._enablement["allowed"] is False
    assert plugin._enablement["status"] == status
    assert plugin._enablement["capabilities"][HOME_PROFILE]["status"] == status
    assert plugin._runtime.config["enabled"] is False
    assert len(probes[0].calls) == 2


def test_initialize_ready_playback_reporting_allows_runtime():
    """所有已选 identity 都可访问时才允许插件启用。"""
    plugin = FakePlugin()

    def runtime_factory(plugin_arg, config_arg):
        plugin_arg._playback_service = FakePlaybackService("ready")
        return SimpleNamespace(plugin=plugin_arg, config=config_arg, stop=lambda: None)

    initialize_plugin(plugin, _config(), runtime_factory=runtime_factory)

    assert plugin.get_state() is True
    assert plugin._enablement["status"] == "ready"
    assert plugin._runtime.config["enabled"] is True


def test_initialize_requires_every_selected_identity_to_be_ready():
    """任一已选 identity 被阻断时，整个插件都不得进入运行态。"""
    plugin = FakePlugin()

    def runtime_factory(plugin_arg, config_arg):
        plugin_arg._playback_service = FakePlaybackService(
            {HOME_PROFILE: "transient_error", REMOTE_PROFILE: "not_installed"}
        )
        return SimpleNamespace(plugin=plugin_arg, config=config_arg, stop=lambda: None)

    initialize_plugin(plugin, _config(), runtime_factory=runtime_factory)

    assert plugin.get_state() is False
    assert plugin._enablement["status"] == "not_installed"
    assert plugin._enablement["capabilities"][HOME_PROFILE]["status"] == (
        "transient_error"
    )
    assert plugin._enablement["capabilities"][REMOTE_PROFILE]["status"] == (
        "not_installed"
    )


def test_runtime_refresh_rejects_direct_bypass_when_gate_is_blocked():
    """即使绕过控制器直接调用 runtime，硬门禁仍拒绝执行。"""
    plugin = FakePlugin()
    plugin._enablement = {
        "allowed": False,
        "status": "not_installed",
        "message": "未安装 Playback Reporting，插件无法启用",
    }
    runtime = AgentRankRuntime(
        plugin, _config(), FakeOrchestrator(), lambda cron: cron
    )

    with pytest.raises(RuntimeError, match="未安装 Playback Reporting"):
        asyncio.run(runtime.refresh(HOME_PROFILE))


def test_stop_is_idempotent_cancels_active_task_and_blocks_refresh():
    """Stopping twice is safe and cancels a currently blocked scheduled run."""
    entered = asyncio.Event()

    class BlockingOrchestrator(FakeOrchestrator):
        async def run(self, profile_id, config):
            self.calls.append(profile_id)
            entered.set()
            await asyncio.Event().wait()

    async def scenario():
        runtime = AgentRankRuntime(
            FakePlugin(),
            _config(
                emby_identities=[_identity("home", "user-1", "Alice")],
                default_profile_id=HOME_PROFILE,
            ),
            BlockingOrchestrator(),
            lambda cron: cron,
        )
        task = asyncio.create_task(runtime.run_scheduled())
        await entered.wait()
        runtime.stop()
        runtime.stop()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(RuntimeError, match="stopped"):
            await runtime.refresh(HOME_PROFILE)

    asyncio.run(scenario())
