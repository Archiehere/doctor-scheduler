"""Half-open minute intervals within a single day, ``[start, end)``."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True, order=True, slots=True)
class Interval:
    start: int
    end: int

    def __post_init__(self) -> None:
        if not 0 <= self.start <= self.end <= MINUTES_PER_DAY:
            raise ValueError(f"invalid interval {self.start}-{self.end}")

    @property
    def length(self) -> int:
        return self.end - self.start

    def overlaps(self, other: Interval) -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: Interval) -> bool:
        return self.start <= other.start and other.end <= self.end


def merge(intervals: Iterable[Interval]) -> list[Interval]:
    """Sort and merge overlapping or touching intervals."""
    merged: list[Interval] = []
    for iv in sorted(intervals):
        if iv.length == 0:
            continue
        if merged and iv.start <= merged[-1].end:
            last = merged[-1]
            merged[-1] = Interval(last.start, max(last.end, iv.end))
        else:
            merged.append(iv)
    return merged


def subtract(base: Iterable[Interval], remove: Iterable[Interval]) -> list[Interval]:
    """Return the parts of ``base`` not covered by ``remove``."""
    holes = merge(remove)
    result: list[Interval] = []
    for iv in merge(base):
        cursor = iv.start
        for hole in holes:
            if hole.end <= cursor or hole.start >= iv.end:
                continue
            if hole.start > cursor:
                result.append(Interval(cursor, hole.start))
            cursor = max(cursor, hole.end)
        if cursor < iv.end:
            result.append(Interval(cursor, iv.end))
    return result


def total(intervals: Iterable[Interval]) -> int:
    return sum(iv.length for iv in merge(intervals))


def align_up(minute: int, grid: int) -> int:
    return -(-minute // grid) * grid


def format_minute(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"
