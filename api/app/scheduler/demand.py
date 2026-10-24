"""Demand forecast per weekday and 15-minute cell.

The index answers "how contested is this slot?" on a 0..1 scale. It blends a prior
(afternoons are popular) with what patients actually asked for recently. With few
requests the prior dominates; as history grows it takes over.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

from .intervals import MINUTES_PER_DAY, Interval


def prior_curve(minute: int) -> float:
    """Typical demand shape for consumer telehealth: low mornings, peak late afternoon."""
    hour = minute / 60
    if hour < 8:
        return 0.15
    if hour < 10:
        return 0.40
    if hour < 12:
        return 0.50
    if hour < 14:
        return 0.70
    if hour < 18:
        return 1.00
    if hour < 20:
        return 0.80
    return 0.30


@dataclass(frozen=True, slots=True)
class DemandSample:
    """One past booking request: the weekday it was for, its ranges and preferred time."""

    weekday: int
    ranges: Sequence[Interval]
    preferred: int


class DemandModel:
    def __init__(
        self,
        samples: Iterable[DemandSample],
        *,
        grid: int = 15,
        prior_strength: float = 20.0,
    ) -> None:
        self.grid = grid
        cells = MINUTES_PER_DAY // grid
        counts = [[0.0] * cells for _ in range(7)]
        requests = [0] * 7

        for sample in samples:
            requests[sample.weekday] += 1
            covered = [c for r in sample.ranges for c in range(r.start // grid, r.end // grid)]
            if covered:
                # Half the weight spread over the stated ranges, half on the preferred time.
                spread = 0.5 / len(covered)
                for c in covered:
                    counts[sample.weekday][c] += spread
            pref_cell = min(sample.preferred // grid, cells - 1)
            for offset, share in ((-1, 0.125), (0, 0.25), (1, 0.125)):
                c = pref_cell + offset
                if 0 <= c < cells:
                    counts[sample.weekday][c] += share

        prior = [prior_curve(c * grid) for c in range(cells)]
        self._index: list[list[float]] = []
        for weekday in range(7):
            peak = max(counts[weekday]) or 1.0
            alpha = requests[weekday] / (requests[weekday] + prior_strength)
            self._index.append(
                [(1 - alpha) * prior[c] + alpha * (counts[weekday][c] / peak) for c in range(cells)]
            )

    def cell(self, weekday: int, minute: int) -> float:
        return self._index[weekday][minute // self.grid]

    def index(self, day: date, slot: Interval) -> float:
        """Average demand index across the cells a slot covers."""
        row = self._index[day.weekday()]
        cells = range(
            slot.start // self.grid, max(slot.end // self.grid, slot.start // self.grid + 1)
        )
        return sum(row[c] for c in cells) / len(cells)

    def profile(self, day: date, start: int, end: int) -> list[tuple[int, float]]:
        """(minute, index) pairs for drawing the demand shading in the booking UI."""
        row = self._index[day.weekday()]
        return [(m, row[m // self.grid]) for m in range(start, end, self.grid)]
