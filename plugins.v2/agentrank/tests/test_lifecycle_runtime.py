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

AgentRankRuntime = runtime_module.AgentRankRuntime
initialize_plugin = lifecycle_module.initialize_plugin
stop_plugin = lifecycle_module.stop_plugin


class FakeOrchestrator:
    """Record user order and optionally fail selected users."""

    def __init__(self, failures=None):
        self.failures = set(failures or [])
        self.calls = []

    async def run(self, username, config):
        self.calls.append(username)
        if username in self.failures:
            raise RuntimeError(f"{username} failed")
        return SimpleNamespace(username=username, status="success")


class FakePlugin:
    """Minimal plugin object used by lifecycle assembly tests."""

    def __init__(self):
        self._runtime = None
        self._config = {}
        self._enabled = False
        self.stop_calls = 0

    def stop_service(self):
        self.stop_calls += 1
        stop_plugin(self)


def _config(**overrides):
    config = {
        "enabled": True,
        "schedule_enabled": True,
        "cron": "0 8 * * *",
        "users": ["alice", "bob"],
        "default_user": "alice",
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
    orchestrator = FakeOrchestrator(failures={"alice"})
    runtime = AgentRankRuntime(FakePlugin(), _config(), orchestrator, lambda cron: cron)

    results = asyncio.run(runtime.run_scheduled())

    assert orchestrator.calls == ["alice", "bob"]
    assert results[0]["username"] == "alice"
    assert results[0]["status"] == "failed"
    assert results[1]["username"] == "bob"
    assert results[1]["status"] == "success"


def test_initialize_normalizes_config_and_replaces_previous_runtime():
    """Reinitialization stops the previous runtime before installing a new one."""
    plugin = FakePlugin()
    old_runtime = SimpleNamespace(stopped=False, stop=lambda: setattr(old_runtime, "stopped", True))
    plugin._runtime = old_runtime
    created = []

    def runtime_factory(plugin_arg, config_arg):
        runtime = SimpleNamespace(plugin=plugin_arg, config=config_arg, stopped=False)
        created.append(runtime)
        return runtime

    initialize_plugin(plugin, _config(), runtime_factory=runtime_factory)

    assert old_runtime.stopped is True
    assert plugin._enabled is True
    assert plugin._runtime is created[0]
    assert plugin._config["default_user"] == "alice"


def test_stop_is_idempotent_cancels_active_task_and_blocks_refresh():
    """Stopping twice is safe and cancels a currently blocked scheduled run."""
    entered = asyncio.Event()

    class BlockingOrchestrator(FakeOrchestrator):
        async def run(self, username, config):
            self.calls.append(username)
            entered.set()
            await asyncio.Event().wait()

    async def scenario():
        runtime = AgentRankRuntime(
            FakePlugin(),
            _config(users=["alice"]),
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
            await runtime.refresh("alice")

    asyncio.run(scenario())
