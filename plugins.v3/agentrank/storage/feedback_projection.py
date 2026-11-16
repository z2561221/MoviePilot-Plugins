"""Bound polarity projections and share one verified ledger per profile."""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..model.feedback import FeedbackEvent, FeedbackLedgerIndex


@dataclass(frozen=True)
class _PolaritySnapshot:
    """Keep each run's polarities and full revalidation deadline."""

    states: dict[str, str]
    revalidate_at: float


class FeedbackPolarityCache:
    """Own the LRU while repository profile locks protect ledger reads."""

    def __init__(self, capacity: int = 8, revalidate_seconds: float = 60.0) -> None:
        """Set the projection capacity and full revalidation interval."""
        self._capacity = max(1, int(capacity))
        self._revalidate_seconds = float(revalidate_seconds)
        self._guard = threading.RLock()
        self._entries: OrderedDict[tuple[str, str], _PolaritySnapshot] = OrderedDict()
        self._indices: dict[str, FeedbackLedgerIndex] = {}
        self._closed = False

    def __len__(self) -> int:
        """Count retained board projections."""
        with self._guard:
            return len(self._entries)

    @property
    def retained_ledger_count(self) -> int:
        """Count the single ledger index retained for each cached profile."""
        with self._guard:
            return len(self._indices)

    def close(self) -> None:
        """Release cached data and block late publication after shutdown."""
        with self._guard:
            self._closed = True
            self._entries.clear()
            self._indices.clear()

    @staticmethod
    def _is_append(previous: FeedbackLedgerIndex, current: FeedbackLedgerIndex) -> bool:
        return (
            previous.retained_from_sequence == current.retained_from_sequence
            and previous.next_sequence < current.next_sequence
            and previous.segments[:-1] == current.segments[: len(previous.segments) - 1]
            and all(
                current.idempotency.get(name) == pointer
                for name, pointer in previous.idempotency.items()
            )
        )

    @staticmethod
    def _apply(
        projections: dict[str, dict[str, str]],
        events: Sequence[FeedbackEvent],
    ) -> None:
        for event in events:
            states = projections.get(event.run_id)
            if states is None or not event.candidate_id or event.status != "recorded":
                continue
            if event.kind == "neutral":
                states.pop(event.candidate_id, None)
            elif event.kind in {"like", "dislike"}:
                states[event.candidate_id] = event.kind

    def _drop_profile(self, profile_id: str) -> None:
        for key in list(self._entries):
            if key[0] == profile_id:
                del self._entries[key]
        self._indices.pop(profile_id, None)

    def _trim(self) -> None:
        while len(self._entries) > self._capacity:
            self._entries.popitem(last=False)
        retained_profiles = {profile_id for profile_id, _ in self._entries}
        for profile_id in list(self._indices):
            if profile_id not in retained_profiles:
                del self._indices[profile_id]

    def project(
        self,
        profile_id: str,
        run_id: str,
        index: FeedbackLedgerIndex,
        load_events: Callable[[int], Sequence[FeedbackEvent]],
    ) -> dict[str, str]:
        """Read a projection and advance other cached runs on ledger append."""
        key = (profile_id, run_id)
        now = time.monotonic()
        with self._guard:
            previous = None if self._closed else self._indices.get(profile_id)
            cached = self._entries.get(key)
            fresh = cached is not None and now < cached.revalidate_at
            if fresh and previous == index:
                self._entries.move_to_end(key)
                return dict(cached.states)
            snapshots = {
                item_key: snapshot
                for item_key, snapshot in self._entries.items()
                if item_key[0] == profile_id
            }

        incremental = (
            fresh and previous is not None and self._is_append(previous, index)
        )
        cursor = previous.next_sequence - 1 if incremental else 0
        projections = {
            item_key[1]: dict(snapshot.states) if incremental else {}
            for item_key, snapshot in snapshots.items()
        }
        projections.setdefault(run_id, {})
        events = load_events(cursor)
        self._apply(projections, events)
        states = projections[run_id]
        expected = index.next_sequence - max(cursor + 1, index.retained_from_sequence)
        with self._guard:
            if self._closed:
                return states
            if len(events) != expected:
                # Invalidate the profile together with its shared ledger anchor.
                self._drop_profile(profile_id)
                return states
            self._indices[profile_id] = index
            for item_key, snapshot in snapshots.items():
                # Another profile may evict entries during I/O. Keep them evicted.
                if item_key == key or self._entries.get(item_key) is snapshot:
                    self._entries[item_key] = _PolaritySnapshot(
                        states=projections[item_key[1]],
                        revalidate_at=(
                            snapshot.revalidate_at
                            if incremental
                            else now + self._revalidate_seconds
                        ),
                    )
            self._entries[key] = _PolaritySnapshot(
                states=dict(states),
                revalidate_at=(
                    cached.revalidate_at
                    if incremental
                    else now + self._revalidate_seconds
                ),
            )
            self._entries.move_to_end(key)
            self._trim()
        return states
