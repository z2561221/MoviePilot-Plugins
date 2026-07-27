"""推荐忽略、恢复与画像清理领域服务。"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from ..model.archive import ArchiveEntry, ArchiveFeedback
from ..model.board import RecommendationBoard, RecommendationItem
from ..storage.repository import AgentRankRepository


@dataclass
class ArchiveActionResult:
    """表示归档领域动作是否改变了状态。"""

    changed: bool
    action: str
    candidate_id: str = ""


class ArchiveService:
    """维护当前用户榜单和归档，不持有订阅或全局配置依赖。"""

    def __init__(self, repository: AgentRankRepository):
        """绑定唯一的 AgentRank 持久化边界。"""
        self._repository = repository

    @staticmethod
    def _assert_board_owner(profile_id: str, board: RecommendationBoard) -> None:
        """拒绝存储键与榜单载荷 profile_id 不一致的越权数据。"""
        if board.profile_id != profile_id:
            raise PermissionError("board profile_id does not match requested profile_id")

    @staticmethod
    def _assert_archive_owner(profile_id: str, archive: ArchiveFeedback) -> None:
        """拒绝存储键与归档载荷 profile_id 不一致的越权数据。"""
        if archive.profile_id != profile_id:
            raise PermissionError("archive profile_id does not match requested profile_id")

    def ignore(self, profile_id: str, candidate_id: str) -> ArchiveActionResult:
        """从当前榜单移除推荐并保留原排名与完整展示载荷。"""
        with self._repository.board_archive_guard(profile_id):
            return self._ignore_locked(profile_id, candidate_id)

    def _ignore_locked(
        self, profile_id: str, candidate_id: str
    ) -> ArchiveActionResult:
        """在榜单归档事务锁内执行忽略操作。"""
        board = self._repository.load_board(profile_id)
        if board is None:
            return ArchiveActionResult(False, "ignore", candidate_id)
        self._assert_board_owner(profile_id, board)
        archive = self._repository.load_archive(profile_id)
        self._assert_archive_owner(profile_id, archive)
        result = self._apply_ignore_state(profile_id, board, archive, candidate_id)
        if result.changed:
            self._repository.save_board_and_archive(board, archive)
        return result

    def _apply_ignore_state(
        self,
        profile_id: str,
        board: RecommendationBoard,
        archive: ArchiveFeedback,
        candidate_id: str,
    ) -> ArchiveActionResult:
        """在内存中移除并归档条目，由外层事务决定何时保存。"""
        self._assert_board_owner(profile_id, board)
        self._assert_archive_owner(profile_id, archive)
        already_archived = any(
            entry.candidate_id == candidate_id for entry in archive.entries
        )
        item = next(
            (
                recommendation
                for recommendation in board.recommendations
                if recommendation.candidate_id == candidate_id
            ),
            None,
        )
        if item is None:
            return ArchiveActionResult(False, "ignore", candidate_id)
        board.recommendations = [
            recommendation
            for recommendation in board.recommendations
            if recommendation.candidate_id != candidate_id
        ]
        board.revision += 1
        if not already_archived:
            archive.entries.append(
                ArchiveEntry(
                    candidate_id=candidate_id,
                    original_rank=item.rank,
                    archived_at=datetime.now(timezone.utc).isoformat(),
                    recommendation=asdict(item),
                )
            )
        return ArchiveActionResult(True, "ignore", candidate_id)

    def restore(self, profile_id: str, candidate_id: str) -> ArchiveActionResult:
        """撤销忽略并按原排名插回，同时保持榜单最多五条。"""
        board = self._repository.load_board(profile_id)
        if board is None:
            return ArchiveActionResult(False, "restore", candidate_id)
        self._assert_board_owner(profile_id, board)
        archive = self._repository.load_archive(profile_id)
        self._assert_archive_owner(profile_id, archive)
        entry = next(
            (item for item in archive.entries if item.candidate_id == candidate_id), None
        )
        if entry is None:
            return ArchiveActionResult(False, "restore", candidate_id)
        if any(item.candidate_id == candidate_id for item in board.recommendations):
            archive.entries = [
                item for item in archive.entries if item.candidate_id != candidate_id
            ]
            self._repository.save_board_and_archive(board, archive)
            return ArchiveActionResult(True, "restore", candidate_id)
        target_rank = max(1, int(entry.original_rank or 1))
        for recommendation in board.recommendations:
            if recommendation.rank >= target_rank:
                recommendation.rank += 1
        payload = dict(entry.recommendation)
        payload["candidate_id"] = candidate_id
        payload["rank"] = target_rank
        board.recommendations.append(RecommendationItem.from_dict(payload))
        board.recommendations.sort(key=lambda item: (item.rank, item.candidate_id))
        board.recommendations = board.recommendations[:5]
        for rank, recommendation in enumerate(board.recommendations, start=1):
            recommendation.rank = rank
        board.revision += 1
        board.status = (
            "success" if len(board.recommendations) == 5 else "recommendation_incomplete"
        )
        board.message = "已恢复忽略作品并保持当前榜单五条"
        archive.entries = [
            item for item in archive.entries if item.candidate_id != candidate_id
        ]
        self._repository.save_board_and_archive(board, archive)
        return ArchiveActionResult(True, "restore", candidate_id)

    def clear_profile(self, profile_id: str) -> ArchiveActionResult:
        """原子清除当前用户画像和榜单，不触碰其他持久化对象。"""
        changed = bool(
            self._repository.load_profile(profile_id)
            or self._repository.load_board(profile_id)
        )
        if not changed:
            return ArchiveActionResult(False, "clear_profile")
        self._repository.clear_profile_and_board(profile_id)
        return ArchiveActionResult(True, "clear_profile")

    def delete_archive(self, profile_id: str, candidate_id: str) -> ArchiveActionResult:
        """仅删除一条归档反馈，不恢复榜单条目。"""
        archive = self._repository.load_archive(profile_id)
        self._assert_archive_owner(profile_id, archive)
        remaining = [
            entry for entry in archive.entries if entry.candidate_id != candidate_id
        ]
        if len(remaining) == len(archive.entries):
            return ArchiveActionResult(False, "delete_archive", candidate_id)
        archive.entries = remaining
        self._repository.save_archive(archive)
        return ArchiveActionResult(True, "delete_archive", candidate_id)
