"""Project read-only board history and comparisons before HTTP serialization."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ..model.board import RecommendationBoard
from ..model.feedback import BoardConsumption
from ..model.run import RecommendationRun


class BoardHistoryRepository(Protocol):
    """Expose the four repository reads needed by history projection."""

    def load_board_history(self, profile_id: str) -> Sequence[RecommendationBoard]:
        """Load retained snapshots in newest-first order."""
        ...

    def load_board(self, profile_id: str) -> RecommendationBoard | None:
        """Load the current board for the legacy history fallback."""
        ...

    def load_run_history(self, profile_id: str) -> Sequence[RecommendationRun]:
        """Load the run metadata associated with retained boards."""
        ...

    def load_board_consumptions(self, profile_id: str) -> Sequence[BoardConsumption]:
        """Load consumption facts once for a nonempty requested page."""
        ...


@dataclass(frozen=True)
class BoardHistoryEntry:
    """Represent one board snapshot and its domain summary."""

    board: RecommendationBoard
    run: RecommendationRun | None
    previous_ids: frozenset[str]
    new_count: int
    overlap_count: int
    previous_overlap_rate: float
    return_count: int
    recent_average_overlap_rate: float
    trigger_reason: str
    exposed: bool
    exposure_count: int
    interacted: bool
    legacy_fallback: bool

    def history_state(self, candidate_id: object) -> str:
        """Classify a recommendation using the selected previous board."""
        return (
            "repeat" if str(candidate_id or "").strip() in self.previous_ids else "new"
        )

    def summary(self) -> dict[str, object]:
        """Expose the existing history fields and compatibility aliases."""
        return {
            "new_count": self.new_count,
            "overlap_count": self.overlap_count,
            "previous_overlap_rate": self.previous_overlap_rate,
            "return_count": self.return_count,
            "returning_count": self.return_count,
            "recent_average_overlap_rate": self.recent_average_overlap_rate,
            "trigger_reason": self.trigger_reason,
            "exposed": self.exposed,
            "exposure_count": self.exposure_count,
            "interacted": self.interacted,
            "legacy_fallback": self.legacy_fallback,
        }


@dataclass(frozen=True)
class BoardHistoryPage:
    """Represent a bounded page before board and run serialization."""

    items: tuple[BoardHistoryEntry, ...]
    total: int
    page: int
    page_size: int
    notice: str
    legacy_fallback: bool


def _board_ids(board: RecommendationBoard) -> set[str]:
    return {
        str(item.candidate_id or "").strip()
        for item in board.recommendations
        if str(item.candidate_id or "").strip()
    }


def _overlap_rate(current: set[str], previous: set[str]) -> float:
    return (
        round(len(current & previous) / len(current), 4)
        if current and previous
        else 0.0
    )


class BoardHistoryService:
    """Own fallback and comparisons with bounded consumption reads."""

    def __init__(self, repository: BoardHistoryRepository) -> None:
        """Bind the read-only history repository port."""
        self._repository = repository

    def page(
        self, profile_id: str, page: int = 1, page_size: int = 10
    ) -> BoardHistoryPage:
        """Build one requested page using all retained boards for comparisons."""
        repository = self._repository
        boards = list(repository.load_board_history(profile_id))
        legacy_fallback = False
        notice = ""
        if not boards:
            current = repository.load_board(profile_id)
            if current is not None and current.recommendations:
                boards = [current]
                legacy_fallback = True
                notice = "历史榜单从本次开始记录，当前榜单为上线前的最后一轮。"
            else:
                notice = "榜单生成后，这里会记录每一轮的完整榜单。"
        runs = {
            run.run_id: run
            for run in repository.load_run_history(profile_id)
            if str(run.run_id or "").strip()
        }
        current_page = max(1, int(page or 1))
        current_page_size = max(1, min(int(page_size or 10), 50))
        start = (current_page - 1) * current_page_size
        end = min(start + current_page_size, len(boards))
        ids_by_index = [_board_ids(board) for board in boards]
        ids_by_run = {
            board.run_id: ids_by_index[index]
            for index, board in enumerate(boards)
            if str(board.run_id or "").strip()
        }
        last_occurrence = {
            candidate_id: index
            for index, ids in enumerate(ids_by_index)
            for candidate_id in ids
        }
        consumption_by_board = {}
        if start < end:
            for consumption in repository.load_board_consumptions(profile_id):
                consumption_by_board.setdefault(
                    (consumption.run_id, consumption.board_revision),
                    consumption,
                )
        items = []
        for index in range(start, end):
            board = boards[index]
            current_ids = ids_by_index[index]
            previous_ids = ids_by_run.get(str(board.previous_run_id or "").strip())
            if previous_ids is None:
                previous_ids = (
                    ids_by_index[index + 1] if index + 1 < len(boards) else set()
                )
            recent_rates = [
                _overlap_rate(ids_by_index[recent], ids_by_index[recent + 1])
                for recent in range(index, min(len(boards) - 1, index + 5))
            ]
            run = runs.get(board.run_id)
            metrics = dict(run.metrics or {}) if run is not None else {}
            consumption = consumption_by_board.get((board.run_id, board.revision))
            items.append(
                BoardHistoryEntry(
                    board=board,
                    run=run,
                    previous_ids=frozenset(previous_ids),
                    new_count=len(current_ids - previous_ids),
                    overlap_count=len(current_ids & previous_ids),
                    previous_overlap_rate=_overlap_rate(current_ids, previous_ids),
                    return_count=sum(
                        last_occurrence[candidate_id] > index
                        for candidate_id in current_ids - previous_ids
                    ),
                    recent_average_overlap_rate=(
                        round(sum(recent_rates) / len(recent_rates), 4)
                        if recent_rates
                        else 0.0
                    ),
                    trigger_reason=str(
                        metrics.get("trigger_reason")
                        or ("legacy_snapshot" if legacy_fallback else "unknown"),
                    ),
                    exposed=bool(consumption.exposed) if consumption else False,
                    exposure_count=int(consumption.exposure_count or 0)
                    if consumption
                    else 0,
                    interacted=bool(consumption.interacted) if consumption else False,
                    legacy_fallback=legacy_fallback,
                ),
            )
        return BoardHistoryPage(
            items=tuple(items),
            total=len(boards),
            page=current_page,
            page_size=current_page_size,
            notice=notice,
            legacy_fallback=legacy_fallback,
        )
