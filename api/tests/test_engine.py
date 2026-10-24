"""Behaviour of the pure placement engine."""

from datetime import date, datetime

from app.config import ScoringWeights
from app.scheduler.engine import (
    DoctorDay,
    EngineParams,
    OptionLabel,
    SlotRequest,
    generate_candidates,
    pick_options,
)
from app.scheduler.intervals import Interval

DAY = date(2026, 11, 2)
NOW = datetime(2026, 11, 2, 7, 0)
PARAMS = EngineParams(weights=ScoringWeights())


def h(hour: float) -> int:
    return int(hour * 60)


def flat(_day: date, _slot: Interval) -> float:
    return 0.5


def request(ranges: list[tuple[float, float]], preferred: float, duration: int = 30) -> SlotRequest:
    return SlotRequest(
        duration=duration,
        ranges=tuple(Interval(h(s), h(e)) for s, e in ranges),
        preferred=h(preferred),
        days=(DAY,),
    )


def doctor(doctor_id: int = 1, open_: tuple[float, float] = (9, 17), booked=()) -> DoctorDay:  # type: ignore[no-untyped-def]
    return DoctorDay(
        doctor_id,
        DAY,
        (Interval(h(open_[0]), h(open_[1])),),
        tuple(Interval(h(s), h(e)) for s, e in booked),
    )


def best(req: SlotRequest, days: list[DoctorDay], demand=flat, now: datetime = NOW):  # type: ignore[no-untyped-def]
    return generate_candidates(req, days, demand, now, PARAMS)[0]


def test_candidates_stay_inside_ranges_and_on_grid() -> None:
    found = generate_candidates(request([(10, 12)], 11), [doctor()], flat, NOW, PARAMS)
    assert found
    for c in found:
        assert h(10) <= c.slot.start and c.slot.end <= h(12)
        assert c.slot.start % 15 == 0
        assert c.in_range


def test_never_overlaps_existing_bookings() -> None:
    found = generate_candidates(
        request([(9, 12)], 10), [doctor(booked=[(10, 11)])], flat, NOW, PARAMS
    )
    assert all(not c.slot.overlaps(Interval(h(10), h(11))) for c in found)


def test_prefers_exact_preferred_time_when_nothing_else_differs() -> None:
    assert best(request([(9, 17)], 11), [doctor()]).slot.start == h(11)


def test_avoids_leaving_unbookable_gaps() -> None:
    # Booking 09:00-09:30. Preferred 09:45 would strand 09:30-09:45, which nobody can use.
    choice = best(request([(9, 12)], 9.75), [doctor(open_=(9, 12), booked=[(9, 9.5)])])
    assert choice.slot.start == h(9.5)


def test_wide_range_patients_are_steered_off_peak() -> None:
    def afternoon_peak(_day: date, slot: Interval) -> float:
        return 1.0 if slot.end > h(14) else 0.2

    wide = best(request([(9, 18)], 14.5), [doctor(open_=(9, 18))], demand=afternoon_peak)
    assert wide.slot.end <= h(14)


def test_narrow_range_patients_keep_their_peak_time() -> None:
    def afternoon_peak(_day: date, slot: Interval) -> float:
        return 1.0 if slot.end > h(14) else 0.2

    narrow = best(request([(14, 15.5)], 14.5), [doctor(open_=(9, 18))], demand=afternoon_peak)
    assert narrow.slot.start == h(14.5)


def test_balances_load_across_doctors() -> None:
    busy = doctor(1, booked=[(9, 14)])
    idle = doctor(2)
    choice = best(request([(15, 16)], 15), [busy, idle])
    assert choice.doctor_id == 2


def test_respects_current_time_and_notice() -> None:
    now = datetime(2026, 11, 2, 10, 5)
    found = generate_candidates(request([(9, 17)], 9), [doctor()], flat, now, PARAMS)
    assert min(c.slot.start for c in found) == h(10.5)  # 10:05 + 15 min notice, rounded up


def test_outside_pass_offers_nearby_slots_when_range_is_full() -> None:
    full = doctor(open_=(9, 17), booked=[(12, 14)])
    req = request([(12, 14)], 13)
    assert generate_candidates(req, [full], flat, NOW, PARAMS) == []
    fallback = generate_candidates(req, [full], flat, NOW, PARAMS, allow_outside=True)
    assert fallback and not any(c.in_range for c in fallback)
    assert all(h(10) <= c.slot.start and c.slot.end <= h(16) for c in fallback)


def test_pick_options_gives_distinct_labelled_choices() -> None:
    req = request([(9, 17)], 15)
    found = generate_candidates(req, [doctor(1), doctor(2)], flat, NOW, PARAMS)
    options = pick_options(found, req.preferred, k=3)
    assert len(options) == 3
    assert OptionLabel.RECOMMENDED in options[0].labels
    keys = {o.candidate.key for o in options}
    assert len(keys) == 3  # two doctors at the same time count as one option
    labels = {label for o in options for label in o.labels}
    assert {OptionLabel.CLOSEST, OptionLabel.SOONEST} <= labels
