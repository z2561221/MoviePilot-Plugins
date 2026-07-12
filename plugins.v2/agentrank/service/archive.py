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
    def _assert_board_owner(username: str, board: RecommendationBoard) -> None:
        """拒绝存储键与榜单载荷用户名不一致的越权数据。"""
        if board.username != username:
            raise PermissionError("board username does not match requested username")

    @staticmethod
    def _assert_archive_owner(username: str, archive: ArchiveFeedback) -> None:
        """拒绝存储键与归档载荷用户名不一致的越权数据。"""
        if archive.username != username:
            raise PermissionError("archive username does not match requested username")

    def ignore(self, username: str, candidate_id: str) -> ArchiveActionResult:
        """从当前榜单移除推荐并保留原排名与完整展示载荷。"""
        board = self._repository.load_board(username)
        if board is None:
            return ArchiveActionResult(False, "ignore", candidate_id)
        self._assert_board_owner(username, board)
        archive = self._repository.load_archive(username)
        self._assert_archive_owner(username, archive)
        if any(entry.candidate_id == candidate_id for entry in archive.entries):
            return ArchiveActionResult(False, "ignore", candidate_id)
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
        archive.entries.append(
            ArchiveEntry(
                candidate_id=candidate_id,
                original_rank=item.rank,
                archived_at=datetime.now(timezone.utc).isoformat(),
                recommendation=asdict(item),
            )
        )
        self._repository.save_board_and_archive(board, archive)
        return ArchiveActionResult(True, "ignore", candidate_id)

    def restore(self, username: str, candidate_id: str) -> ArchiveActionResult:
        """撤销负反馈，原排名空闲时复位，否则追加榜单末尾。"""
        board = self._repository.load_board(username)
        if board is None:
            return ArchiveActionResult(False, "restore", candidate_id)
        self._assert_board_owner(username, board)
        archive = self._repository.load_archive(username)
        self._assert_archive_owner(username, archive)
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
        occupied_ranks = {item.rank for item in board.recommendations}
        target_rank = entry.original_rank
        if target_rank in occupied_ranks:
            target_rank = max(occupied_ranks, default=0) + 1
        payload = dict(entry.recommendation)
        payload["candidate_id"] = candidate_id
        payload["rank"] = target_rank
        board.recommendations.append(RecommendationItem.from_dict(payload))
        board.recommendations.sort(key=lambda item: (item.rank, item.candidate_id))
        archive.entries = [
            item for item in archive.entries if item.candidate_id != candidate_id
        ]
        self._repository.save_board_and_archive(board, archive)
        return ArchiveActionResult(True, "restore", candidate_id)

    def clear_profile(self, username: str) -> ArchiveActionResult:
        """原子清除当前用户画像和榜单，不触碰其他持久化对象。"""
        self._repository.clear_profile_and_board(username)
        return ArchiveActionResult(True, "clear_profile")
