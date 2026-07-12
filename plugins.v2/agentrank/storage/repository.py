"""基于 MoviePilot 插件数据接口的每用户存储仓库。"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Type, TypeVar
from urllib.parse import quote

from ..model.archive import ArchiveFeedback
from ..model.board import RecommendationBoard
from ..model.candidate import Candidate
from ..model.profile import UserProfile
from ..model.run import RecommendationRun


ModelType = TypeVar("ModelType")


class AgentRankRepository:
    """统一封装 AgentRank 的隔离键、迁移与容错读取。"""

    recovery_log_key = "agentrank_recovery_log"

    def __init__(self, plugin: Any, history_limit: int = 50):
        """绑定插件数据接口并设置历史上限。"""
        self._plugin = plugin
        self._history_limit = max(1, min(int(history_limit), 200))

    @staticmethod
    def _scope(value: str, field_name: str) -> str:
        """校验并转义用户名或运行标识，避免键空间碰撞。"""
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{field_name} is required")
        return quote(text, safe="@._-")

    def _key(self, prefix: str, username: str) -> str:
        """生成按用户名隔离的持久化键。"""
        return f"{prefix}:{self._scope(username, 'username')}"

    def _candidate_key(self, run_id: str, username: str) -> str:
        """生成按运行和用户名双重隔离的候选快照键。"""
        return (
            f"candidate_snapshot:{self._scope(run_id, 'run_id')}:"
            f"{self._scope(username, 'username')}"
        )

    def _record_recovery(self, key: str, action: str, detail: str = "") -> None:
        """记录迁移或损坏数据恢复证据，且不因日志损坏而失败。"""
        try:
            history = self._plugin.get_data(key=self.recovery_log_key)
            history = list(history) if isinstance(history, list) else []
        except Exception:
            history = []
        history.append(
            {
                "key": key,
                "action": action,
                "detail": detail,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._plugin.save_data(key=self.recovery_log_key, value=history[-100:])

    def _load_model(
        self,
        key: str,
        model_type: Type[ModelType],
        legacy_keys: List[str] = None,
    ) -> Optional[ModelType]:
        """容错读取模型，并在命中旧键时迁移到当前键。"""
        value = self._plugin.get_data(key=key)
        source_key = key
        if value is None:
            for legacy_key in legacy_keys or []:
                value = self._plugin.get_data(key=legacy_key)
                if value is not None:
                    source_key = legacy_key
                    break
        if value is None:
            return None
        try:
            model = model_type.from_dict(value)
        except (TypeError, ValueError, KeyError) as error:
            self._record_recovery(source_key, "ignored_corrupt_data", str(error))
            return None
        if source_key != key:
            self._plugin.save_data(key=key, value=model.to_dict())
            self._record_recovery(source_key, "migrated_legacy_key", f"to {key}")
        return model

    def save_profile(self, profile: UserProfile) -> None:
        """保存当前用户画像快照。"""
        self._plugin.save_data(
            key=self._key("profile_snapshot", profile.username), value=profile.to_dict()
        )

    def load_profile(self, username: str) -> Optional[UserProfile]:
        """读取当前用户画像；损坏或不存在时返回空。"""
        return self._load_model(
            self._key("profile_snapshot", username),
            UserProfile,
            legacy_keys=[self._key("profile", username)],
        )

    def save_board(self, board: RecommendationBoard) -> None:
        """保存当前用户榜单。"""
        self._plugin.save_data(
            key=self._key("recommendation_board", board.username), value=board.to_dict()
        )

    def load_board(self, username: str) -> Optional[RecommendationBoard]:
        """读取当前用户榜单；损坏或不存在时返回空。"""
        return self._load_model(
            self._key("recommendation_board", username), RecommendationBoard
        )

    def save_archive(self, archive: ArchiveFeedback) -> None:
        """保存当前用户忽略归档。"""
        self._plugin.save_data(
            key=self._key("archive", archive.username), value=archive.to_dict()
        )

    def load_archive(self, username: str) -> ArchiveFeedback:
        """读取当前用户归档；不存在或损坏时返回空归档。"""
        archive = self._load_model(self._key("archive", username), ArchiveFeedback)
        return archive or ArchiveFeedback(username=username)

    def save_candidate_snapshot(
        self, run_id: str, username: str, candidates: List[Candidate]
    ) -> None:
        """保存冻结的本轮候选快照。"""
        self._plugin.save_data(
            key=self._candidate_key(run_id, username),
            value={
                "schema_version": 1,
                "run_id": run_id,
                "username": username,
                "candidates": [candidate.to_dict() for candidate in candidates],
            },
        )

    def load_candidate_snapshot(self, run_id: str, username: str) -> List[Candidate]:
        """读取本轮候选快照；损坏时返回空列表并记录证据。"""
        key = self._candidate_key(run_id, username)
        value = self._plugin.get_data(key=key)
        if value is None:
            return []
        try:
            if not isinstance(value, Mapping):
                raise ValueError("candidate snapshot must be a mapping")
            if str(value.get("run_id") or "") != str(run_id):
                raise ValueError("candidate snapshot run_id mismatch")
            if str(value.get("username") or "") != str(username):
                raise ValueError("candidate snapshot username mismatch")
            return [Candidate.from_dict(item) for item in value.get("candidates") or []]
        except (TypeError, ValueError, KeyError) as error:
            self._record_recovery(key, "ignored_corrupt_data", str(error))
            return []

    def append_run(self, run: RecommendationRun) -> None:
        """把运行记录写入对应用户历史头部并执行上限裁剪。"""
        key = self._key("run_history", run.username)
        raw_history = self._plugin.get_data(key=key)
        history = list(raw_history) if isinstance(raw_history, list) else []
        history.insert(0, run.to_dict())
        self._plugin.save_data(key=key, value=history[: self._history_limit])

    def load_run_history(self, username: str) -> List[RecommendationRun]:
        """容错读取当前用户的有界运行历史。"""
        key = self._key("run_history", username)
        value = self._plugin.get_data(key=key)
        if value is None:
            return []
        if not isinstance(value, list):
            self._record_recovery(key, "ignored_corrupt_data", "history must be a list")
            return []
        result: List[RecommendationRun] = []
        for item in value[: self._history_limit]:
            try:
                run = RecommendationRun.from_dict(item)
            except (TypeError, ValueError, KeyError) as error:
                self._record_recovery(key, "ignored_corrupt_item", str(error))
                continue
            if run.username == username:
                result.append(run)
            else:
                self._record_recovery(key, "ignored_cross_user_item", run.username)
        return result

    def annotate_run(
        self,
        username: str,
        run_id: str,
        status: str,
        metrics: Dict[str, Any] = None,
        errors: List[str] = None,
    ) -> bool:
        """更新指定运行记录的状态与后处理证据。"""
        key = self._key("run_history", username)
        value = self._plugin.get_data(key=key)
        if not isinstance(value, list):
            return False
        changed = False
        updated: List[Any] = []
        for item in value:
            if (
                not changed
                and isinstance(item, Mapping)
                and str(item.get("username") or "") == username
                and str(item.get("run_id") or "") == run_id
            ):
                current = dict(item)
                current["status"] = status
                current_metrics = dict(current.get("metrics") or {})
                current_metrics.update(metrics or {})
                current["metrics"] = current_metrics
                current_errors = [str(error) for error in current.get("errors") or []]
                current_errors.extend(str(error) for error in errors or [])
                current["errors"] = current_errors
                updated.append(current)
                changed = True
            else:
                updated.append(item)
        if changed:
            self._plugin.save_data(key=key, value=updated[: self._history_limit])
        return changed

    def delete_profile(self, username: str) -> None:
        """删除当前用户画像，不触碰其他用户或 MoviePilot 订阅。"""
        self._plugin.del_data(key=self._key("profile_snapshot", username))

    def delete_board(self, username: str) -> None:
        """删除当前用户榜单，不触碰归档和运行历史。"""
        self._plugin.del_data(key=self._key("recommendation_board", username))

    def _restore_raw(self, key: str, value: Any) -> None:
        """在复合写入失败后恢复单个键的原始值。"""
        if value is None:
            self._plugin.del_data(key=key)
        else:
            self._plugin.save_data(key=key, value=value)

    def save_board_and_archive(
        self, board: RecommendationBoard, archive: ArchiveFeedback
    ) -> None:
        """原子替换同一用户的榜单和归档，失败时恢复两者。"""
        if board.username != archive.username:
            raise ValueError("board and archive username mismatch")
        board_key = self._key("recommendation_board", board.username)
        archive_key = self._key("archive", archive.username)
        old_board = self._plugin.get_data(key=board_key)
        old_archive = self._plugin.get_data(key=archive_key)
        try:
            self._plugin.save_data(key=board_key, value=board.to_dict())
            self._plugin.save_data(key=archive_key, value=archive.to_dict())
        except Exception:
            self._restore_raw(board_key, old_board)
            self._restore_raw(archive_key, old_archive)
            raise

    def save_profile_and_board(
        self, profile: UserProfile, board: RecommendationBoard
    ) -> None:
        """原子替换同一用户的画像与榜单，失败时恢复两者。"""
        if profile.username != board.username:
            raise ValueError("profile and board username mismatch")
        profile_key = self._key("profile_snapshot", profile.username)
        board_key = self._key("recommendation_board", board.username)
        old_profile = self._plugin.get_data(key=profile_key)
        old_board = self._plugin.get_data(key=board_key)
        try:
            self._plugin.save_data(key=profile_key, value=profile.to_dict())
            self._plugin.save_data(key=board_key, value=board.to_dict())
        except Exception:
            self._restore_raw(profile_key, old_profile)
            self._restore_raw(board_key, old_board)
            raise

    def clear_profile_and_board(self, username: str) -> None:
        """原子删除当前用户画像和榜单，失败时恢复原始数据。"""
        profile_key = self._key("profile_snapshot", username)
        board_key = self._key("recommendation_board", username)
        old_profile = self._plugin.get_data(key=profile_key)
        old_board = self._plugin.get_data(key=board_key)
        try:
            self._plugin.del_data(key=profile_key)
            self._plugin.del_data(key=board_key)
        except Exception:
            self._restore_raw(profile_key, old_profile)
            self._restore_raw(board_key, old_board)
            raise
