"""Compare placement strategies on the same synthetic demand, fully in memory.

    python -m scripts.simulate --days 10 --load 1.0

Strategies:
  rounds      the scoring engine; the patient takes the recommended option
  first-fit   the earliest free slot inside the patient's range
  closest     the free slot closest to the patient's preferred time

Requests for each day arrive in random order and are placed one at a time, exactly
like instant booking. Requests that cannot be placed inside the patient's ranges are
counted as unplaced (they would go to the waitlist).
"""

from __future__ import annotations

import argparse
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.config import settings
from app.scheduler.demand import DemandModel, DemandSample
from app.scheduler.engine import (
    Candidate,
    DoctorDay,
    SlotRequest,
    generate_candidates,
    pick_options,
)
from app.scheduler.intervals import Interval
from app.services.placement import engine_params
from scripts.seed import DOCTORS, synthetic_availability

Strategy = Callable[[list[Candidate], SlotRequest], Candidate]


def rounds(found: list[Candidate], req: SlotRequest) -> Candidate:
    return pick_options(found, req.preferred, 1)[0].candidate


def first_fit(found: list[Candidate], _req: SlotRequest) -> Candidate:
    return min(found, key=lambda c: (c.slot.start, c.breakdown.load))


def closest(found: list[Candidate], req: SlotRequest) -> Candidate:
    return min(found, key=lambda c: (abs(c.slot.start - req.preferred), c.breakdown.load))


STRATEGIES: dict[str, Strategy] = {"rounds": rounds, "first-fit": first_fit, "closest": closest}


@dataclass
class Result:
    open_minutes: int = 0
    booked_minutes: int = 0
    requests: int = 0
    placed: int = 0
    preferred: int = 0
    narrow_requests: int = 0
    narrow_placed: int = 0
    dead_gap_minutes: int = 0
    doctor_days: int = 0
    utilizations: list[float] | None = None


def doctor_days_for(day: date) -> list[DoctorDay]:
    result = []
    for i, (_name, _spec, hours) in enumerate(DOCTORS):
        blocks = tuple(Interval(s, e) for wd, s, e in hours if wd == day.weekday())
        result.append(DoctorDay(i, day, blocks))
    return result


def simulate(days: int, load: float, seed: int) -> dict[str, Result]:
    rng = random.Random(seed)
    params = engine_params()
    start = date(2026, 11, 2)
    weekdays = [d for d in (start + timedelta(days=i) for i in range(days * 2)) if d.weekday() < 5]
    weekdays = weekdays[:days]

    # Same request stream for every strategy.
    streams: dict[date, list[SlotRequest]] = {}
    history: list[DemandSample] = []
    for day in weekdays:
        capacity = sum(dd.open_minutes for dd in doctor_days_for(day))
        reqs = []
        for _ in range(int(capacity * load / 37.5)):
            ranges, preferred = synthetic_availability(rng)
            duration = rng.choices([30, 45], weights=[55, 45])[0]
            if ranges[0].length < duration:
                continue
            reqs.append(SlotRequest(duration, tuple(ranges), preferred, (day,)))
            history.append(DemandSample(day.weekday(), ranges, preferred))
        rng.shuffle(reqs)
        streams[day] = reqs
    demand = DemandModel(
        history, grid=settings.grid_minutes, prior_strength=settings.demand_prior_strength
    )

    results: dict[str, Result] = {}
    for name, strategy in STRATEGIES.items():
        res = Result(utilizations=[])
        for day in weekdays:
            now = datetime.combine(day - timedelta(days=1), datetime.min.time())
            state = {dd.doctor_id: dd for dd in doctor_days_for(day)}
            for req in streams[day]:
                res.requests += 1
                narrow = req.flexibility_minutes <= 90
                res.narrow_requests += narrow
                found = generate_candidates(req, list(state.values()), demand.index, now, params)
                if not found:
                    continue
                chosen = strategy(found, req)
                state[chosen.doctor_id] = state[chosen.doctor_id].with_booking(chosen.slot)
                res.placed += 1
                res.narrow_placed += narrow
                res.preferred += (
                    abs(chosen.slot.start - req.preferred) <= settings.preferred_tolerance_minutes
                )
            for dd in state.values():
                if not dd.open_minutes:
                    continue
                res.doctor_days += 1
                res.open_minutes += dd.open_minutes
                res.booked_minutes += dd.booked_minutes
                res.utilizations.append(dd.booked_minutes / dd.open_minutes)  # type: ignore[union-attr]
                res.dead_gap_minutes += sum(
                    f.length for f in dd.free() if f.length < settings.min_bookable_gap
                )
        results[name] = res
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--load", type=float, default=1.0, help="demand as a multiple of capacity")
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()

    results = simulate(args.days, args.load, args.seed)
    header = (
        f"{'strategy':<10} {'utilisation':>11} {'util p10':>9} {'placed':>7} "
        f"{'at pref.':>8} {'narrow placed':>13} {'dead gap/day':>12}"
    )
    print(f"{args.days} weekdays, demand = {args.load:.0%} of capacity\n")
    print(header)
    print("-" * len(header))
    for name, r in results.items():
        utils = sorted(r.utilizations or [0.0])
        p10 = utils[max(0, int(len(utils) * 0.1) - 1)]
        print(
            f"{name:<10} {r.booked_minutes / r.open_minutes:>11.1%} {p10:>9.1%} "
            f"{r.placed / r.requests:>7.1%} {r.preferred / max(r.placed, 1):>8.1%} "
            f"{r.narrow_placed / max(r.narrow_requests, 1):>13.1%} "
            f"{r.dead_gap_minutes / r.doctor_days:>10.1f} m"
        )


if __name__ == "__main__":
    main()
