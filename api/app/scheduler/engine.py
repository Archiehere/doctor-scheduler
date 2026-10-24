"""Instant slot placement.

Given a patient's availability ranges and preferred time, enumerate every slot on the
15-minute grid that fits a doctor's free time, score each one and return a few
diverse options. The score trades off four goals:

* the patient's preference (closest to the preferred time),
* schedule density (do not leave gaps too short to book),
* demand steering (flexible patients are nudged off peak hours, keeping peak
  capacity for patients who can only make peak hours),
* load balance (spread bookings so every doctor approaches the utilisation target),

plus a small lead-time term so earlier calls win ties.

This module is pure: no database, no clock, no framework. Everything it needs is
passed in, which keeps it fast to test and easy to simulate.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum

from app.config import ScoringWeights

from .intervals import MINUTES_PER_DAY, Interval, align_up, subtract

DemandFn = Callable[[date, Interval], float]


@dataclass(frozen=True, slots=True)
class DoctorDay:
    """A doctor's capacity on one day: open time and what is already booked."""

    doctor_id: int
    day: date
    open: tuple[Interval, ...]
    booked: tuple[Interval, ...] = ()

    @property
    def open_minutes(self) -> int:
        return sum(iv.length for iv in self.open)

    @property
    def booked_minutes(self) -> int:
        return sum(iv.length for iv in self.booked)

    def free(self) -> list[Interval]:
        return subtract(self.open, self.booked)

    def with_booking(self, slot: Interval) -> DoctorDay:
        return DoctorDay(self.doctor_id, self.day, self.open, (*self.booked, slot))


@dataclass(frozen=True, slots=True)
class SlotRequest:
    duration: int
    ranges: tuple[Interval, ...]
    preferred: int
    days: tuple[date, ...]

    @property
    def flexibility_minutes(self) -> int:
        """Slack beyond the call itself: a 4h range for a 30 min call has 210 min of slack."""
        return max(0, sum(r.length for r in self.ranges) - self.duration)


@dataclass(frozen=True, slots=True)
class EngineParams:
    weights: ScoringWeights
    grid: int = 15
    min_bookable_gap: int = 30
    min_notice_minutes: int = 15
    utilization_soft_cap: float = 0.90
    overcap_penalty: float = 6.0
    flexibility_full_minutes: int = 240
    outside_range_margin: int = 120


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """Weighted cost terms. Kept separately so the UI can explain a recommendation."""

    preference: float
    fragmentation: float
    demand: float
    load: float
    lead_time: float
    outside_range: float

    @property
    def total(self) -> float:
        return (
            self.preference
            + self.fragmentation
            + self.demand
            + self.load
            + self.lead_time
            + self.outside_range
        )


@dataclass(frozen=True, slots=True)
class Candidate:
    doctor_id: int
    day: date
    slot: Interval
    in_range: bool
    demand_index: float
    breakdown: ScoreBreakdown

    @property
    def score(self) -> float:
        return self.breakdown.total

    @property
    def key(self) -> tuple[date, int]:
        """What the patient perceives as "the same option": the same day and start time."""
        return (self.day, self.slot.start)


class OptionLabel(StrEnum):
    RECOMMENDED = "recommended"
    CLOSEST = "closest_to_preference"
    SOONEST = "soonest"
    ALTERNATIVE = "alternative"


@dataclass(slots=True)
class Option:
    candidate: Candidate
    labels: list[OptionLabel] = field(default_factory=list)


def _gap_cost(gap: int, min_bookable_gap: int) -> float:
    if gap == 0:
        return 0.0
    if gap < min_bookable_gap:
        return 1.0  # dead time nobody can book
    return 0.15  # still bookable, but splitting free time is slightly worse than packing


def _earliest_start(day: date, now: datetime, params: EngineParams) -> int | None:
    """First bookable minute on ``day`` given the current time, or None if the day is over."""
    today = now.date()
    if day < today:
        return None
    if day > today:
        return 0
    minute = now.hour * 60 + now.minute + params.min_notice_minutes
    start = align_up(minute, params.grid)
    return start if start < MINUTES_PER_DAY else None


def bookable_minutes(doctor_day: DoctorDay, now: datetime, params: EngineParams) -> int:
    """Free minutes a new call could still use: after the notice window, in gaps that fit a call."""
    earliest = _earliest_start(doctor_day.day, now, params)
    if earliest is None:
        return 0
    total = 0
    for gap in doctor_day.free():
        start = align_up(max(gap.start, earliest), params.grid)
        if gap.end - start >= params.min_bookable_gap:
            total += gap.end - start
    return total


def _search_windows(request: SlotRequest, allow_outside: bool, margin: int) -> list[Interval]:
    if not allow_outside:
        return list(request.ranges)
    return [
        Interval(max(0, r.start - margin), min(MINUTES_PER_DAY, r.end + margin))
        for r in request.ranges
    ]


def generate_candidates(
    request: SlotRequest,
    doctor_days: Sequence[DoctorDay],
    demand: DemandFn,
    now: datetime,
    params: EngineParams,
    *,
    allow_outside: bool = False,
) -> list[Candidate]:
    """Every feasible (doctor, start) placement with its score, best first."""
    w = params.weights
    flexibility = min(1.0, request.flexibility_minutes / params.flexibility_full_minutes)
    windows = _search_windows(request, allow_outside, params.outside_range_margin)
    days = set(request.days)
    candidates: list[Candidate] = []

    for dd in doctor_days:
        if dd.day not in days or dd.open_minutes == 0:
            continue
        earliest = _earliest_start(dd.day, now, params)
        if earliest is None:
            continue
        load_after = (dd.booked_minutes + request.duration) / dd.open_minutes
        load_cost = load_after + params.overcap_penalty * max(
            0.0, load_after - params.utilization_soft_cap
        )

        for free in dd.free():
            effective_start = max(free.start, earliest)
            for window in windows:
                lo = align_up(max(effective_start, window.start), params.grid)
                hi = min(free.end, window.end) - request.duration
                for start in range(lo, hi + 1, params.grid):
                    slot = Interval(start, start + request.duration)
                    in_range = any(r.contains(slot) for r in request.ranges)
                    if allow_outside and in_range:
                        continue  # in-range slots come from the normal pass
                    fragmentation = _gap_cost(
                        start - effective_start, params.min_bookable_gap
                    ) + _gap_cost(free.end - slot.end, params.min_bookable_gap)
                    demand_index = demand(dd.day, slot)
                    starts_at = datetime.combine(dd.day, datetime.min.time()) + timedelta(
                        minutes=start
                    )
                    lead_days = max(0.0, (starts_at - now).total_seconds() / 86400)
                    breakdown = ScoreBreakdown(
                        preference=w.preference * abs(start - request.preferred) / 60,
                        fragmentation=w.fragmentation * fragmentation,
                        demand=w.demand * demand_index * flexibility,
                        load=w.load * load_cost,
                        lead_time=w.lead_time * lead_days,
                        outside_range=0.0 if in_range else w.outside_range,
                    )
                    candidates.append(
                        Candidate(dd.doctor_id, dd.day, slot, in_range, demand_index, breakdown)
                    )

    candidates.sort(key=lambda c: (c.score, c.day, c.slot.start, c.doctor_id))
    return candidates


def pick_options(
    candidates: Sequence[Candidate], preferred: int, k: int = 3, min_separation: int = 30
) -> list[Option]:
    """Choose up to ``k`` distinct options from scored candidates.

    The first is always the best score ("recommended"). The next slots go to the
    option closest to the preferred time and the soonest option, so the patient gets
    a real choice; leftover slots are filled with the next best distinct times.
    Several doctors free at the same time collapse into the best-scoring one.
    """
    if not candidates:
        return []

    best_per_time: dict[tuple[date, int], Candidate] = {}
    for c in candidates:  # already sorted best first
        best_per_time.setdefault(c.key, c)
    unique = list(best_per_time.values())

    picks: dict[tuple[date, int], Option] = {}

    def add(candidate: Candidate, label: OptionLabel) -> None:
        if candidate.key in picks:
            picks[candidate.key].labels.append(label)
        elif len(picks) < k:
            picks[candidate.key] = Option(candidate, [label])

    add(unique[0], OptionLabel.RECOMMENDED)
    add(
        min(unique, key=lambda c: (abs(c.slot.start - preferred), c.day, c.score)),
        OptionLabel.CLOSEST,
    )
    add(min(unique, key=lambda c: (c.day, c.slot.start, c.score)), OptionLabel.SOONEST)

    for c in unique:
        if len(picks) >= k:
            break
        far_enough = all(
            c.day != p.candidate.day or abs(c.slot.start - p.candidate.slot.start) >= min_separation
            for p in picks.values()
        )
        if c.key not in picks and far_enough:
            picks[c.key] = Option(c, [OptionLabel.ALTERNATIVE])

    return sorted(picks.values(), key=lambda o: o.candidate.score)
