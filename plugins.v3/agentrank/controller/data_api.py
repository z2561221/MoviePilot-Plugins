"""归档、画像标签以及插件数据导出和重置。"""

from typing import Any, Dict

from .errors import ApiContractError
from ..service.archive import ArchiveService
from ..service.data_lifecycle import DataLifecycleError
from ..service.profile_preferences import ProfilePreferenceService


class DataApiMixin:
    """归档、画像标签以及插件数据导出和重置。"""

    def archive(self, payload: Any, actor_id: str = "") -> Dict[str, Any]:
        """兼容旧忽略入口，并把动作接入统一反馈事实。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        candidate_id = self._candidate_id(body)
        board = self._repository().load_board(target)
        if board is None:
            raise ApiContractError(409, "board_unavailable", "当前没有可操作的推荐榜单")
        idempotency_key = str(body.get("idempotency_key") or "").strip()
        if not idempotency_key:
            idempotency_key = (
                f"legacy-ignore:{target}:{board.run_id}:{board.revision}:{candidate_id}"
            )
        request = dict(body)
        request.update(
            {
                "kind": "ignore",
                "idempotency_key": idempotency_key,
                "run_id": str(body.get("run_id") or board.run_id),
            }
        )
        return self.feedback(request, actor_id)

    def restore(self, payload: Any) -> Dict[str, Any]:
        """恢复一个已忽略推荐。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        candidate_id = self._candidate_id(body)
        result = ArchiveService(self._repository()).restore(target, candidate_id)
        return self._success(result.__dict__)

    def delete_archive(self, payload: Any) -> Dict[str, Any]:
        """永久删除一条归档反馈但不恢复榜单。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        candidate_id = self._candidate_id(body)
        result = ArchiveService(self._repository()).delete_archive(target, candidate_id)
        return self._success(result.__dict__)

    def clear_profile(self, payload: Any) -> Dict[str, Any]:
        """经明确确认后原子清除用户画像和榜单。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        if body.get("confirm") is not True:
            raise ApiContractError(409, "confirmation_required", "重建画像需要明确确认")
        result = ArchiveService(self._repository()).clear_profile(target)
        return self._success(result.__dict__)

    def data_export(self, profile_id: Any) -> Dict[str, Any]:
        """返回当前 profile 的字段白名单脱敏导出。"""
        target = self._profile_id(profile_id)
        try:
            data = self._data_lifecycle().export_profile(target)
        except DataLifecycleError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "data_export_failed", "数据导出失败，旧数据未被修改"
            ) from error
        return self._success(data)

    def reset_learning(self, payload: Any) -> Dict[str, Any]:
        """经明确确认后仅重置 AgentRank 学习数据。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            data = self._data_lifecycle().reset_learning(
                target, body.get("confirm") is True
            )
        except DataLifecycleError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "learning_reset_failed", "重置交互学习失败，旧数据已保留"
            ) from error
        return self._success(data)

    def prepare_full_reset(
        self, payload: Any, requester_id: str
    ) -> Dict[str, Any]:
        """为彻底重置签发绑定当前 MP 用户的短时确认令牌。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            data = self._data_lifecycle().prepare_full_reset(target, requester_id)
        except DataLifecycleError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "full_reset_prepare_failed", "无法生成清空全部数据确认"
            ) from error
        return self._success(data)

    def reset_full(self, payload: Any, requester_id: str) -> Dict[str, Any]:
        """校验一次性令牌后彻底删除 AgentRank 自有 profile 数据。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            data = self._data_lifecycle().reset_full(
                target,
                requester_id,
                str(body.get("confirmation_token") or ""),
            )
        except DataLifecycleError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "full_reset_failed", "清空全部数据失败，旧数据已保留"
            ) from error
        return self._success(data)

    def update_profile_tag(self, payload: Any) -> Dict[str, Any]:
        """添加或删除当前用户的人工偏好或避雷标签。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            result = ProfilePreferenceService(self._repository()).update(
                profile_id=target,
                kind=str(body.get("kind") or "").strip(),
                action=str(body.get("action") or "").strip(),
                raw_tag=body.get("tag"),
            )
        except ValueError as error:
            raise ApiContractError(422, "invalid_profile_tag", str(error)) from error
        profile = self._repository().load_profile(target)
        return self._success(
            {
                "changed": result.changed,
                "action": result.action,
                "kind": result.kind,
                "tag": result.tag,
                "profile": self._profile_data(target, profile),
            }
        )
