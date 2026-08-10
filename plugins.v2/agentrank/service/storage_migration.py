"""AgentRank 新存储 schema 的增量初始化与兼容观测服务。"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List

from ..storage.repository import AgentRankRepository


@dataclass(frozen=True)
class ProfileStorageMigrationResult:
    """描述单个 profile 的旧数据可读性与新增 schema 状态。"""

    profile_id: str
    status: str
    created_keys: List[str] = field(default_factory=list)
    observed: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """返回不包含旧数据载荷的安全迁移摘要。"""
        return {
            "profile_id": self.profile_id,
            "status": self.status,
            "created_keys": list(self.created_keys),
            "observed": dict(self.observed),
            "error": self.error,
        }


@dataclass(frozen=True)
class StorageMigrationReport:
    """汇总本次启动中全部 profile 的增量迁移结果。"""

    status: str
    profiles: List[ProfileStorageMigrationResult] = field(default_factory=list)

    @property
    def failure_count(self) -> int:
        """返回失败 profile 数量。"""
        return sum(result.status == "failed" for result in self.profiles)

    def to_dict(self) -> Dict[str, Any]:
        """返回状态 API 可直接使用的脱敏迁移摘要。"""
        return {
            "status": self.status,
            "profile_count": len(self.profiles),
            "failure_count": self.failure_count,
            "profiles": [result.to_dict() for result in self.profiles],
        }


class AgentRankStorageMigrationService:
    """验证旧对象仍可读，并只创建缺失的新存储 schema。"""

    def __init__(self, repository: AgentRankRepository):
        """绑定 AgentRank 唯一持久化边界。"""
        self._repository = repository

    def _observe_legacy_data(self, profile_id: str) -> Dict[str, Any]:
        """读取旧对象并仅返回存在性和数量，不复制业务载荷。"""
        profile = self._repository.load_profile(profile_id)
        board = self._repository.load_board(profile_id)
        archive = self._repository.load_archive(profile_id)
        preferences = self._repository.load_profile_preferences(profile_id)
        history = self._repository.load_run_history(profile_id)
        return {
            "profile_present": profile is not None,
            "board_present": board is not None,
            "archive_entry_count": len(archive.entries),
            "custom_tag_count": len(preferences.custom_tags),
            "custom_negative_tag_count": len(preferences.custom_negative_tags),
            "archived_tag_count": len(preferences.archived_tags),
            "archived_negative_tag_count": len(
                preferences.archived_negative_tags
            ),
            "run_history_count": len(history),
        }

    def migrate_profiles(self, profile_ids: Iterable[str]) -> StorageMigrationReport:
        """逐 profile 执行可重入迁移，单个失败不阻断其他 profile。"""
        results: List[ProfileStorageMigrationResult] = []
        seen = set()
        for value in profile_ids or ():
            profile_id = str(value or "").strip()
            if not profile_id or profile_id in seen:
                continue
            seen.add(profile_id)
            try:
                observed = self._observe_legacy_data(profile_id)
                created = self._repository.initialize_additive_storage(profile_id)
            except Exception as error:
                results.append(
                    ProfileStorageMigrationResult(
                        profile_id=profile_id,
                        status="failed",
                        error=type(error).__name__,
                    )
                )
                continue
            results.append(
                ProfileStorageMigrationResult(
                    profile_id=profile_id,
                    status="ready",
                    created_keys=created,
                    observed=observed,
                )
            )
        status = "partial_failed" if any(
            result.status == "failed" for result in results
        ) else "ready"
        return StorageMigrationReport(status=status, profiles=results)
