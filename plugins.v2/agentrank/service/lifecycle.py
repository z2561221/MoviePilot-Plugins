"""Agent榜单中心插件生命周期与硬依赖门禁服务。"""

from typing import Any, Callable, Dict, List, Mapping

from ..model.config import configured_identities, normalize_config
from ..model.playback import PlaybackCapability
from .runtime import AgentRankRuntime
from .storage_migration import AgentRankStorageMigrationService


_BLOCK_MESSAGES = {
    "not_installed": "未安装 Playback Reporting，插件无法启用",
    "permission_error": "Playback Reporting 权限不足，插件无法启用",
    "transient_error": "Playback Reporting 暂时不可用，插件保持停用",
    "emby_unavailable": "Emby 服务不可用，插件保持停用",
}
_BLOCK_PRIORITY = {
    "not_installed": 0,
    "permission_error": 1,
    "emby_unavailable": 2,
    "transient_error": 3,
}


def _enablement(
    requested: bool,
    allowed: bool,
    status: str,
    message: str,
    capabilities: Mapping[str, PlaybackCapability] = None,
) -> Dict[str, Any]:
    """构造不含 Emby 凭据和显示名的安全启用状态。"""
    return {
        "requested": bool(requested),
        "allowed": bool(allowed),
        "status": str(status or "stopped"),
        "message": str(message or ""),
        "capabilities": {
            str(profile_id): capability.to_dict()
            for profile_id, capability in dict(capabilities or {}).items()
        },
    }


def _probe_enablement(plugin: Any, config: Mapping[str, Any]) -> Dict[str, Any]:
    """探测所有已选 identity，并要求每个依赖状态均为 ready。"""
    requested = bool(config.get("enabled"))
    if not requested:
        return _enablement(False, False, "disabled", "插件未启用")
    identities = configured_identities(config)
    if not identities:
        return _enablement(
            True, False, "configuration_error", "未选择有效 Emby 用户，插件无法启用"
        )
    service = getattr(plugin, "_playback_service", None)
    if service is None or not hasattr(service, "probe"):
        return _enablement(
            True,
            False,
            "transient_error",
            "Playback Reporting 探测服务尚未就绪，插件保持停用",
        )
    capabilities: Dict[str, PlaybackCapability] = {}
    for identity in identities:
        try:
            capability = service.probe(identity.profile_id, config)
        except Exception:
            capability = PlaybackCapability(
                profile_id=identity.profile_id,
                status="transient_error",
                message="Playback Reporting 探测失败",
            )
        if (
            not isinstance(capability, PlaybackCapability)
            or capability.profile_id != identity.profile_id
        ):
            capability = PlaybackCapability(
                profile_id=identity.profile_id,
                status="transient_error",
                message="Playback Reporting 探测结果无效",
            )
        capabilities[identity.profile_id] = capability
    blockers = [
        capability for capability in capabilities.values() if not capability.ready
    ]
    blocker = min(
        blockers,
        key=lambda capability: _BLOCK_PRIORITY.get(capability.status, 99),
        default=None,
    )
    if blocker is not None:
        return _enablement(
            True,
            False,
            blocker.status,
            _BLOCK_MESSAGES.get(
                blocker.status, "Playback Reporting 不可用，插件保持停用"
            ),
            capabilities,
        )
    return _enablement(
        True, True, "ready", "Playback Reporting 已就绪", capabilities
    )


def stop_plugin(plugin: Any) -> None:
    """幂等停止并移除当前运行时。"""
    runtime = getattr(plugin, "_runtime", None)
    if runtime is not None and hasattr(runtime, "stop"):
        runtime.stop()
    plugin._runtime = None
    plugin._playback_service = None
    plugin._emby_access = None
    plugin._data_lifecycle = None
    plugin._feedback_queue = None
    plugin._feedback_understanding = None
    plugin._feedback_response = None
    plugin._memory_projection = None
    plugin._conversation = None
    plugin._enabled = False
    plugin._enablement = _enablement(False, False, "stopped", "插件已停止")
    plugin._migration_status = {
        "status": "stopped",
        "profile_count": 0,
        "failure_count": 0,
        "profiles": [],
    }
    plugin._data_lifecycle_status = {
        "status": "stopped",
        "profiles": [],
        "retention_policy": {},
    }


def initialize_plugin(
    plugin: Any,
    config: dict = None,
    runtime_factory: Callable[[Any, Dict[str, Any]], Any] = AgentRankRuntime,
) -> None:
    """停止旧运行时、规范化配置、探测硬依赖并组装运行时。"""
    plugin.stop_service()
    normalized = normalize_config(config)
    runtime_config = dict(normalized)
    plugin._config = dict(normalized)
    plugin._enabled = False
    plugin._runtime = runtime_factory(plugin, runtime_config)
    repository = getattr(plugin, "_repository", None)
    migration_status = getattr(plugin, "_migration_status", None)
    if repository is not None and (
        not isinstance(migration_status, Mapping)
        or migration_status.get("status") not in {"ready", "partial_failed"}
    ):
        profile_ids = [
            identity.profile_id for identity in configured_identities(plugin._config)
        ]
        migration_status = AgentRankStorageMigrationService(repository).migrate_profiles(
            profile_ids
        ).to_dict()
        plugin._migration_status = migration_status
    else:
        if repository is None:
            migration_status = {
                "status": "not_initialized",
                "profile_count": 0,
                "failure_count": 0,
                "profiles": [],
            }
            plugin._migration_status = migration_status
    if int(dict(migration_status or {}).get("failure_count") or 0):
        errors = plugin._config.get("_validation_errors")
        if not isinstance(errors, list):
            errors = []
            plugin._config["_validation_errors"] = errors
        message = "AgentRank 新存储初始化失败，请查看迁移状态"
        if message not in errors:
            errors.append(message)
    plugin._enablement = _probe_enablement(plugin, plugin._config)
    plugin._enabled = bool(plugin._enablement.get("allowed"))
    if not plugin._enabled:
        runtime_config["enabled"] = False
        runtime_config["onlyonce"] = False
        runtime = getattr(plugin, "_runtime", None)
        runtime_state = getattr(runtime, "config", None)
        if isinstance(runtime_state, dict):
            runtime_state["enabled"] = False
            runtime_state["onlyonce"] = False
    if plugin._config.get("onlyonce"):
        plugin._config["onlyonce"] = False
        persisted = {
            key: value
            for key, value in plugin._config.items()
            if key != "_validation_errors"
        }
        plugin.update_config(config=persisted)
    runtime = getattr(plugin, "_runtime", None)
    if plugin._enabled and runtime is not None:
        start_background = getattr(runtime, "start_background", None)
        if callable(start_background):
            start_background()


def build_services(plugin: Any) -> List[Dict[str, Any]]:
    """返回当前运行时声明的宿主周期服务。"""
    runtime = getattr(plugin, "_runtime", None)
    if runtime is None:
        return []
    return runtime.get_services()
