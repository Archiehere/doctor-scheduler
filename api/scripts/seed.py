"""Populate the database with doctors and four weeks of realistic history.

History is not written as rows directly. Synthetic patients are replayed in time
order through the real booking services (request -> hold -> confirm, cancellations,
leave, waitlist, outcomes), so every analytics number comes from the actual
scheduling logic.

    python -m scripts.seed            # reset and seed
    python -m scripts.seed --days 21  # shorter history
"""

from __future__ import annotations

import argparse
import heapq
import itertools
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app import clock
from app.config import VISIT_DURATIONS, VisitType
from app.db import Base, SessionLocal, engine
from app.errors import DomainError
from app.models import Booking, BookingStatus, Doctor, TimeOffKind, WorkingHours
from app.scheduler.intervals import Interval
from app.services import booking as booking_service
from app.services import placement, reflow, waitlist

H = 60

DOCTORS: list[tuple[str, str, list[tuple[int, int, int]]]] = [
    # name, specialty, [(weekday, start, end)]
    (
        "Dr Meera Raghavan",
        "General practice",
        [(wd, 9 * H, 13 * H) for wd in range(5)] + [(wd, 14 * H, 18 * H) for wd in range(5)],
    ),
    ("Dr Arjun Mehta", "General practice", [(wd, 12 * H, 20 * H) for wd in range(5)]),
    (
        "Dr Sana Qureshi",
        "Family medicine",
        [(wd, 8 * H, 12 * H) for wd in range(6)] + [(wd, 13 * H, 16 * H) for wd in range(5)],
    ),
    (
        "Dr Daniel Fernandes",
        "Internal medicine",
        [(wd, 10 * H, 14 * H) for wd in range(1, 6)] + [(wd, 15 * H, 19 * H) for wd in range(1, 6)],
    ),
    (
        "Dr Priya Nair",
        "Paediatrics",
        [(wd, 9 * H, 12 * H) for wd in (0, 2, 4)] + [(wd, 15 * H, 20 * H) for wd in range(5)],
    ),
    (
        "Dr Kabir Anand",
        "Dermatology",
        [(wd, 13 * H, 19 * H) for wd in range(4)] + [(5, 10 * H, 14 * H)],
    ),
]

FIRST = [
    "Aarav",
    "Ishita",
    "Rohan",
    "Ananya",
    "Vikram",
    "Diya",
    "Kunal",
    "Meher",
    "Nikhil",
    "Pooja",
    "Rahul",
    "Sneha",
    "Tara",
    "Varun",
    "Zoya",
    "Aditya",
    "Kavya",
    "Farhan",
    "Lakshmi",
    "Omar",
    "Neha",
    "Siddharth",
    "Ritika",
    "Yash",
    "Aisha",
    "Dev",
    "Mira",
    "Jay",
    "Nisha",
    "Arnav",
]
LAST = [
    "Sharma",
    "Iyer",
    "Khan",
    "Menon",
    "Gupta",
    "Reddy",
    "Das",
    "Kapoor",
    "Joshi",
    "Pillai",
    "Bose",
    "Malhotra",
    "Shetty",
    "Verma",
    "Chopra",
    "Kulkarni",
    "Banerjee",
    "Rao",
]


@dataclass(frozen=True)
class SyntheticPatient:
    name: str
    email: str
    phone: str
    reliability: float  # base probability of showing up


@dataclass(order=True)
class Event:
    at: datetime
    seq: int
    action: Callable[[Session, datetime], None] = field(compare=False)


class Replay:
    def __init__(self, rng: random.Random, now: datetime) -> None:
        self.rng = rng
        self.now = now
        self.queue: list[Event] = []
        self.counter = itertools.count()
        self.stats = {"requests": 0, "booked": 0, "waitlisted": 0, "abandoned": 0}

    def at(self, when: datetime, action: Callable[[Session, datetime], None]) -> None:
        if when <= self.now:
            heapq.heappush(self.queue, Event(when, next(self.counter), action))

    def run(self) -> None:
        with SessionLocal() as session:
            while self.queue:
                event = heapq.heappop(self.queue)
                try:
                    event.action(session, event.at)
                except DomainError:
                    session.rollback()


def make_patients(rng: random.Random, n: int) -> list[SyntheticPatient]:
    people = []
    for i in range(n):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        reliability = rng.choices([0.97, 0.9, 0.7], weights=[70, 22, 8])[0]
        people.append(
            SyntheticPatient(
                name=f"{first} {last}",
                email=f"{first}.{last}.{i}@example.com".lower(),
                phone=f"+91 9{rng.randint(100000000, 999999999)}",
                reliability=reliability,
            )
        )
    return people


def synthetic_availability(rng: random.Random) -> tuple[list[Interval], int]:
    """Most people want afternoons; range width varies from narrow to all-day."""
    centre = rng.choices(
        [10 * H, 12.5 * H, 15 * H, 16.5 * H, 18.5 * H], weights=[18, 14, 30, 22, 16]
    )[0]
    centre = int(centre) + rng.choice([-30, -15, 0, 15, 30])
    width = rng.choices([75, 120, 240, 420, 600], weights=[22, 26, 28, 16, 8])[0]
    start = max(8 * H, min(centre - width // 2, 20 * H - width))
    start -= start % 15
    end = min(start + width, 21 * H)
    preferred = min(max(centre - centre % 15, start), end - 30)
    return [Interval(start, end)], preferred


def seed(days_back: int, seed_value: int) -> None:
    rng = random.Random(seed_value)
    now = clock.now()
    today = now.date()
    started = time.perf_counter()

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        for name, specialty, hours in DOCTORS:
            doctor = Doctor(name=name, specialty=specialty)
            session.add(doctor)
            session.flush()
            session.add_all(
                WorkingHours(doctor_id=doctor.id, weekday=wd, start_minute=s, end_minute=e)
                for wd, s, e in hours
            )
        session.commit()
        doctor_ids = [d.id for d in session.query(Doctor).order_by(Doctor.id)]

    patients = make_patients(rng, 420)
    replay = Replay(rng, now)
    first_day = today - timedelta(days=days_back)
    horizon = today + timedelta(days=7)

    with SessionLocal() as session:
        capacity = _clinic_capacity(session, first_day, horizon, now)

    day = first_day
    while day <= horizon:
        demand_factor = rng.uniform(0.92, 1.12)
        n_requests = int(capacity.get(day, 0) * demand_factor / 38)
        for _ in range(n_requests):
            _schedule_request(replay, rng, rng.choice(patients), day)
        day += timedelta(days=1)

    _schedule_leave(replay, rng, doctor_ids, first_day, today)
    replay.run()

    with SessionLocal() as session:
        bookings = session.query(Booking).count()
        completed = session.query(Booking).filter(Booking.status == BookingStatus.COMPLETED).count()
    elapsed = time.perf_counter() - started
    print(
        f"Seeded {len(DOCTORS)} doctors, {replay.stats['requests']} requests, "
        f"{bookings} bookings ({completed} completed), "
        f"{replay.stats['waitlisted']} waitlisted in {elapsed:.1f}s"
    )


def _clinic_capacity(session: Session, start: date, end: date, now: datetime) -> dict[date, int]:
    """Open doctor-minutes per day across the clinic."""
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    totals: dict[date, int] = {}
    for dd in placement.build_doctor_days(session, days, now):
        totals[dd.day] = totals.get(dd.day, 0) + dd.open_minutes
    return totals


def _schedule_request(
    replay: Replay, rng: random.Random, patient: SyntheticPatient, day: date
) -> None:
    lead_days = rng.choices([0, 1, 2, 3, 5, 7], weights=[30, 28, 16, 12, 8, 6])[0]
    asked_on = day - timedelta(days=lead_days)
    asked_at = datetime.combine(asked_on, datetime.min.time()) + timedelta(
        minutes=rng.randint(7 * H, (12 if lead_days == 0 else 21) * H)
    )
    ranges, preferred = synthetic_availability(rng)
    visit_type = rng.choices([VisitType.FOLLOW_UP, VisitType.NEW_CONSULT], weights=[55, 45])[0]

    def request(session: Session, at: datetime) -> None:
        replay.stats["requests"] += 1
        if all(r.length < VISIT_DURATIONS[visit_type] for r in ranges):
            return
        req, result = booking_service.create_request(
            session,
            name=patient.name,
            email=patient.email,
            phone=patient.phone,
            visit_type=visit_type,
            day=day,
            search_ahead_days=rng.choice([0, 0, 0, 1, 2]),
            ranges=ranges,
            preferred_minute=preferred,
            now=at,
        )
        if not result.in_range or not result.options:
            if rng.random() < 0.6 and day >= at.date():
                waitlist.join(session, req.id, deposit_acknowledged=True, now=at)
                replay.stats["waitlisted"] += 1
            else:
                replay.stats["abandoned"] += 1
            return

        # Most patients take the recommendation; some hold out for their exact time.
        weights = [62, 26, 12][: len(result.options)]
        chosen = rng.choices(result.options, weights=weights)[0].candidate
        held = booking_service.hold(
            session,
            request_id=req.id,
            doctor_id=chosen.doctor_id,
            day=chosen.day,
            start_minute=chosen.slot.start,
            now=at,
        )
        if held.deposit_cents and rng.random() < 0.12:
            replay.stats["abandoned"] += 1
            return  # deposit put them off; the hold simply expires
        booking = booking_service.confirm(session, held.code, deposit_paid=True, now=at)
        replay.stats["booked"] += 1
        _schedule_lifecycle(replay, rng, patient, booking.code, at)

    replay.at(asked_at, request)


def _schedule_lifecycle(
    replay: Replay, rng: random.Random, patient: SyntheticPatient, code: str, booked_at: datetime
) -> None:
    """After booking: maybe cancel, otherwise show up (or not) at call time."""

    def outcome(session: Session, at: datetime) -> None:
        booking = booking_service.get_booking(session, code)
        if booking.status != BookingStatus.CONFIRMED:
            return  # cancelled, moved to reschedule, etc.
        lead_days = (booking.starts_at - booking.request.created_at).days
        show_prob = patient.reliability - 0.015 * min(lead_days, 7)
        if booking.deposit_cents:
            show_prob += (1 - show_prob) * 0.5  # deposits halve the no-show risk
        if rng.random() > show_prob:
            booking_service.record_outcome(
                session,
                booking.id,
                booking_service.OutcomeAction.NO_SHOW,
                booking.starts_at + timedelta(minutes=10),
            )
            return
        start = booking.starts_at + timedelta(minutes=rng.choice([0, 0, 1, 2, 4]))
        booking_service.record_outcome(
            session, booking.id, booking_service.OutcomeAction.START, start
        )
        scheduled = booking.end_minute - booking.start_minute
        actual = max(12, int(rng.gauss(scheduled - 3, 6)))
        booking_service.record_outcome(
            session,
            booking.id,
            booking_service.OutcomeAction.COMPLETE,
            start + timedelta(minutes=actual),
        )

    def maybe_cancel(session: Session, at: datetime) -> None:
        booking = booking_service.get_booking(session, code)
        if booking.status != BookingStatus.CONFIRMED:
            return
        booking_service.cancel(session, code, at)

    def schedule(session: Session, at: datetime) -> None:
        booking = booking_service.get_booking(session, code)
        starts = booking.starts_at
        if rng.random() < 0.07:
            span = max((starts - booked_at).total_seconds(), 60)
            replay.at(booked_at + timedelta(seconds=rng.uniform(0.2, 0.98) * span), maybe_cancel)
        replay.at(starts + timedelta(minutes=1), outcome)

    replay.at(booked_at + timedelta(seconds=1), schedule)


def _schedule_leave(
    replay: Replay, rng: random.Random, doctor_ids: list[int], first_day: date, today: date
) -> None:
    """A few leave days and blocks, announced a couple of days ahead."""
    plans: list[tuple[int, date, TimeOffKind, int | None, int | None, str]] = []
    for _ in range(4):
        d = first_day + timedelta(days=rng.randint(3, max(4, (today - first_day).days)))
        plans.append((rng.choice(doctor_ids), d, TimeOffKind.LEAVE, None, None, "Annual leave"))
    for _ in range(5):
        d = first_day + timedelta(days=rng.randint(2, (today - first_day).days + 6))
        start = rng.choice([10, 11, 15, 16]) * H
        plans.append(
            (rng.choice(doctor_ids), d, TimeOffKind.BLOCK, start, start + 90, "Clinic meeting")
        )
    plans.append(
        (doctor_ids[1], today + timedelta(days=3), TimeOffKind.LEAVE, None, None, "Conference")
    )

    for doctor_id, day, kind, start, end, reason in plans:
        announced = datetime.combine(
            day - timedelta(days=rng.choice([1, 2, 4])), datetime.min.time()
        )
        announced += timedelta(hours=18)

        def add(
            session: Session,
            at: datetime,
            *,
            doctor_id=doctor_id,
            day=day,
            kind=kind,  # type: ignore[no-untyped-def]
            start=start,
            end=end,
            reason=reason,
        ) -> None:
            reflow.add_time_off(
                session,
                doctor_id=doctor_id,
                day=day,
                kind=kind,
                start_minute=start,
                end_minute=end,
                reason=reason,
                now=at,
            )

        replay.at(announced, add)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--days", type=int, default=28, help="days of history to generate")
    parser.add_argument("--seed", type=int, default=7, help="random seed")
    args = parser.parse_args()
    seed(args.days, args.seed)


if __name__ == "__main__":
    main()
