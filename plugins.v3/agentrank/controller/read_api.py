"""状态、配置、榜单和运行历史查询。"""

from typing import Any, Dict, List

from app import schemas

from .errors import ApiContractError
from ..model.config import configured_identities, default_config
from ..model.identity import EmbyIdentity
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

    def config_options(self) -> Dict[str, Any]:
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
        if access is not None and hasattr(access, "enumerate_identities"):
            try:
                for identity in access.enumerate_identities() or []:
                    identity_map[identity.profile_id] = identity.to_dict()
            except Exception:
                pass
        identities = list(identity_map.values())
        libraries = {}
        if access is not None and hasattr(access, "enumerate_libraries"):
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
                    if getattr(self.plugin, "_playback_service", None) is not None
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
        return self._success(
            {
                "profile_id": target,
                "username": self._display_name(target),
                "profile": self._profile_data(target, profile),
                "board": self._board_data(board) if board else None,
                "archive": archive.to_dict(),
                "latest_run": history[0].to_dict() if history else None,
                "history": [item.to_dict() for item in history[:15]],
                "history_total": len(history),
                "learning_health": repository.build_learning_health(target).to_dict(),
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
        repository = self._repository()
        boards = list(repository.load_board_history(target))
        legacy_fallback = False
        notice = ""
        if not boards:
            current = repository.load_board(target)
            if current is not None and current.recommendations:
                # 历史功能上线前没有快照时，至少让用户看到当前榜单，并明确标记起点。
                boards = [current]
                legacy_fallback = True
                notice = "历史榜单从本次开始记录，当前榜单为上线前的最后一轮。"
            else:
                notice = "榜单生成后，这里会记录每一轮的完整榜单。"
        runs = {
            run.run_id: run
            for run in repository.load_run_history(target)
            if str(run.run_id or "").strip()
        }
        board_by_run_id = {
            board.run_id: board
            for board in boards
            if str(board.run_id or "").strip()
        }
        def board_ids(value: Any) -> set[str]:
            """提取一轮榜单中非空且去重的候选标识。"""
            return {
                str(item.candidate_id or "").strip()
                for item in (value.recommendations if value else ())
                if str(item.candidate_id or "").strip()
            }

        def overlap_rate(current_ids: set[str], previous_ids: set[str]) -> float:
            """计算当前榜单与参照榜单的候选重合率。"""
            if not current_ids or not previous_ids:
                return 0.0
            return round(len(current_ids & previous_ids) / max(1, len(current_ids)), 4)

        items: List[Dict[str, Any]] = []
        for index, board in enumerate(boards):
            current_ids = board_ids(board)
            previous = board_by_run_id.get(str(board.previous_run_id or "").strip())
            if previous is None and index + 1 < len(boards):
                previous = boards[index + 1]
            previous_ids = board_ids(previous)
            older_ids = set().union(*(board_ids(value) for value in boards[index + 1 :]))
            return_count = len((current_ids & older_ids) - previous_ids)
            recent_rates = []
            for recent_index in range(index, min(len(boards) - 1, index + 5)):
                recent_current = board_ids(boards[recent_index])
                recent_previous = board_ids(boards[recent_index + 1])
                recent_rates.append(overlap_rate(recent_current, recent_previous))
            run = runs.get(board.run_id)
            metrics = dict(run.metrics or {}) if run is not None else {}
            consumption = repository.load_board_consumption(
                target, board.run_id, board.revision
            )
            board_data = self._board_snapshot_data(board)
            for item in board_data.get("recommendations") or []:
                candidate_id = str(item.get("candidate_id") or "").strip()
                item["history_state"] = (
                    "repeat" if candidate_id in previous_ids else "new"
                )
            items.append(
                {
                    "board": board_data,
                    "run": run.to_dict() if run is not None else None,
                    "new_count": len(current_ids - previous_ids),
                    "overlap_count": len(current_ids & previous_ids),
                    "previous_overlap_rate": overlap_rate(current_ids, previous_ids),
                    "return_count": return_count,
                    "returning_count": return_count,
                    "recent_average_overlap_rate": round(
                        sum(recent_rates) / len(recent_rates), 4
                    ) if recent_rates else 0.0,
                    "trigger_reason": str(
                        metrics.get("trigger_reason") or (
                            "legacy_snapshot" if legacy_fallback else "unknown"
                        )
                    ),
                    "exposed": bool(consumption.exposed) if consumption else False,
                    "exposure_count": int(consumption.exposure_count or 0) if consumption else 0,
                    "interacted": bool(consumption.interacted) if consumption else False,
                    "legacy_fallback": legacy_fallback,
                }
            )
        current_page = max(1, int(page or 1))
        current_page_size = max(1, min(int(page_size or 10), 50))
        start = (current_page - 1) * current_page_size
        return self._success(
            {
                "profile_id": target,
                "username": self._display_name(target),
                "items": items[start : start + current_page_size],
                "total": len(items),
                "page": current_page,
                "page_size": current_page_size,
                "notice": notice,
                "legacy_fallback": legacy_fallback,
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
