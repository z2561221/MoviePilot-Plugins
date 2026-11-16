"""状态、配置、榜单和运行历史查询。"""

from typing import Any, Dict, List

from app import schemas

from .errors import ApiContractError
from ..model.config import configured_identities, default_config
from ..model.identity import EmbyIdentity
from ..service.board_history import BoardHistoryService
from ..service.prompt import configured_agent_display_name


class ReadApiMixin:
    """状态、配置、榜单和运行历史查询。"""

    def status(self) -> Dict[str, Any]:
        """返回插件全局运行状态。"""
        runtime = getattr(self.plugin, "_runtime", None)
        default_profile_id = str(
            self.plugin._config.get("default_profile_id") or ""
        )
        enablement = self._enablement_data()
        state = (
            "ready"
            if self.plugin.get_state()
            else "blocked"
            if enablement.get("status") not in {"disabled", "stopped"}
            else "stopped"
        )
        if runtime is None and state != "blocked":
            state = "stopped"
        return self._success(
            {
                "enabled": bool(self.plugin.get_state()),
                "state": state,
                "plugin_version": self.plugin.plugin_version,
                "validation_errors": list(
                    self.plugin._config.get("_validation_errors") or []
                ),
                "default_profile_id": default_profile_id,
                "playback": self._playback_data(default_profile_id),
                "enablement": enablement,
                "migration": self._migration_data(),
                "data_lifecycle": self._data_lifecycle_data(),
            }
        )

    def status_for_token(
        self, _token_payload: schemas.TokenPayload
    ) -> Dict[str, Any]:
        """向任一已登录 MP 用户返回完整插件状态。"""
        response = self.status()
        data = response["data"]
        identities = self._identity_map()
        profile_ids = list(identities)
        data["profiles"] = [
            {
                "profile_id": profile_id,
                "username": identities[profile_id].username,
            }
            for profile_id in profile_ids
        ]
        data["migration"] = self._migration_data(profile_ids)
        data["data_lifecycle"] = self._data_lifecycle_data(profile_ids)
        return response

    def config_options(self, discover: bool = True) -> Dict[str, Any]:
        """返回 Config 与 Emby 身份切换器需要的安全选项。"""
        from ..service.notification_type import notification_type_options

        selected_identities = [
            identity.to_dict()
            for identity in configured_identities(self.plugin._config)
        ]
        identity_map = {
            identity["profile_id"]: identity for identity in selected_identities
        }
        access = getattr(self.plugin, "_emby_access", None)
        if discover and access is not None and hasattr(access, "enumerate_identities"):
            try:
                for identity in access.enumerate_identities() or []:
                    identity_map[identity.profile_id] = identity.to_dict()
            except Exception:
                pass
        identities = list(identity_map.values())
        libraries = {}
        if discover and access is not None and hasattr(access, "enumerate_libraries"):
            for identity_data in identities:
                try:
                    identity = EmbyIdentity.from_dict(identity_data)
                    libraries[identity.profile_id] = access.enumerate_libraries(identity)
                except Exception:
                    libraries[identity_data["profile_id"]] = []
        return self._success(
            {
                "emby_identities": identities,
                "emby_libraries": libraries,
                "default_profile_id": str(
                    self.plugin._config.get("default_profile_id") or ""
                ),
                "config": dict(self.plugin._config),
                "defaults": default_config(),
                "notification_type_options": notification_type_options(),
                "enablement": self._enablement_data(),
                "playback_status": {
                    identity["profile_id"]: self._playback_data(identity["profile_id"])
                    for identity in selected_identities
                    if discover and getattr(self.plugin, "_playback_service", None) is not None
                },
            }
        )

    def overview(self, profile_id: Any) -> Dict[str, Any]:
        """返回一个 Emby 画像身份的画像、榜单和最近运行摘要。"""
        target = self._profile_id(profile_id)
        repository = self._repository()
        profile = repository.load_profile(target)
        board = repository.load_board(target)
        archive = repository.load_archive(target)
        history = repository.load_run_history(target)
        memory = repository.load_preference_memory(target)
        questions = repository.load_pending_questions(target)
        consumptions = repository.load_board_consumptions(target)
        attributions = repository.load_outcome_attributions(target)
        return self._success(
            {
                "profile_id": target,
                "username": self._display_name(target),
                "profile": self._profile_data(
                    target, profile, memory=memory, questions=questions
                ),
                "board": self._board_data(
                    board, consumptions=consumptions, attributions=attributions
                ) if board else None,
                "archive": archive.to_dict(),
                "latest_run": history[0].to_dict() if history else None,
                "history": [item.to_dict() for item in history[:15]],
                "history_total": len(history),
                "learning_health": repository.calculate_learning_health(
                    target, memory=memory, questions=questions,
                    consumptions=consumptions, attributions=attributions,
                ).to_dict(),
                "agent_display_name": configured_agent_display_name(
                    self.plugin._config.get("agent_display_name")
                ),
                "playback": self._playback_data(target),
                "enablement": self._enablement_data(),
                "migration": self._migration_data([target]),
                "data_lifecycle": self._data_lifecycle_data([target]),
            }
        )

    def board(self, profile_id: Any) -> Dict[str, Any]:
        """返回画像身份当前榜单或显式空榜单。"""
        target = self._profile_id(profile_id)
        board = self._repository().load_board(target)
        if board:
            return self._success(self._board_data(board))
        return self._success(
            {
                "profile_id": target,
                "username": self._display_name(target),
                "run_id": "",
                "status": "idle",
                "recommendations": [],
                "generated_at": "",
                "revision": 0,
                "message": "尚未生成榜单",
            }
        )

    def profile(self, profile_id: Any) -> Dict[str, Any]:
        """返回画像身份当前画像或显式空画像。"""
        target = self._profile_id(profile_id)
        profile = self._repository().load_profile(target)
        return self._success(self._profile_data(target, profile))

    def run_history(
        self, profile_id: Any, page: int = 1, page_size: int = 15
    ) -> Dict[str, Any]:
        """返回用户有界运行历史。"""
        target = self._profile_id(profile_id)
        items = self._repository().load_run_history(target)
        current_page = max(1, int(page or 1))
        current_page_size = max(1, min(int(page_size or 15), 50))
        start = (current_page - 1) * current_page_size
        paged_items = items[start : start + current_page_size]
        return self._success(
            {
                "profile_id": target,
                "username": self._display_name(target),
                "items": [item.to_dict() for item in paged_items],
                "total": len(items),
                "page": current_page,
                "page_size": current_page_size,
            }
        )

    def board_history(
        self, profile_id: Any, page: int = 1, page_size: int = 10
    ) -> Dict[str, Any]:
        """返回只读的历史榜单快照及相邻轮次变化摘要。"""
        target = self._profile_id(profile_id)
        history = BoardHistoryService(self._repository()).page(target, page, page_size)
        items: List[Dict[str, Any]] = []
        for entry in history.items:
            board_data = self._board_snapshot_data(entry.board)
            for item in board_data.get("recommendations") or []:
                item["history_state"] = entry.history_state(item.get("candidate_id"))
            items.append(
                {
                    "board": board_data,
                    "run": entry.run.to_dict() if entry.run is not None else None,
                    **entry.summary(),
                }
            )
        return self._success(
            {
                "profile_id": target,
                "username": self._display_name(target),
                "items": items,
                "total": history.total,
                "page": history.page,
                "page_size": history.page_size,
                "notice": history.notice,
                "legacy_fallback": history.legacy_fallback,
            }
        )

    async def refresh(self, payload: Any) -> Dict[str, Any]:
        """立即受理一次后台手动推荐。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        self._require_enabled()
        runtime = getattr(self.plugin, "_runtime", None)
        if runtime is None:
            raise ApiContractError(503, "runtime_unavailable", "插件运行时尚未就绪")
        try:
            starter = getattr(runtime, "start_refresh", None)
            if callable(starter):
                progress = starter(target)
                return self._success(dict(progress or {}))
            result = await runtime.refresh(target)
        except Exception as error:
            raise ApiContractError(502, "refresh_failed", f"榜单刷新失败：{error}") from error
        return self._success(
            {
                "profile_id": target,
                "username": self._display_name(target),
                "status": result.status,
                "message": getattr(result, "message", ""),
                "run_id": getattr(result, "run_id", ""),
                "final_count": int(getattr(result, "final_count", 0) or 0),
            }
        )

    def run_progress(self, profile_id: Any) -> Dict[str, Any]:
        """返回页面刷新后仍可读取的榜单生成进度。"""
        target = self._profile_id(profile_id)
        runtime = getattr(self.plugin, "_runtime", None)
        if runtime is None or not callable(getattr(runtime, "run_progress", None)):
            raise ApiContractError(503, "runtime_unavailable", "插件运行时尚未就绪")
        return self._success(runtime.run_progress(target))
