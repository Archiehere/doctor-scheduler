"""Doctor availability changes and what happens to bookings they collide with.

When a doctor takes leave, blocks time or shortens their hours, each affected call
is re-placed in this order:

1. the same time with another doctor (the patient's plans do not change),
2. another time inside the patient's original availability ranges,
3. otherwise it is flagged ``needs_reschedule`` and the patient picks a new time.

Freed capacity (time off removed) is offered to the waitlist.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import InvalidRequest, NotFound
from app.models import (
    UPCOMING_STATUSES,
    Booking,
    BookingSource,
    BookingStatus,
    Doctor,
    TimeOff,
    TimeOffKind,
    WorkingHours,
)
from app.scheduler.intervals import MINUTES_PER_DAY, Interval, format_minute, merge
from app.services import placement, waitlist


@dataclass
class ReflowSummary:
    moved_same_time: list[str] = field(default_factory=list)
    moved_new_time: list[str] = field(default_factory=list)
    needs_reschedule: list[str] = field(default_factory=list)

    def extend(self, other: ReflowSummary) -> None:
        self.moved_same_time += other.moved_same_time
        self.moved_new_time += other.moved_new_time
        self.needs_reschedule += other.needs_reschedule


def _doctor(session: Session, doctor_id: int) -> Doctor:
    doctor = session.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFound("Doctor not found")
    return doctor


def add_time_off(
    session: Session,
    *,
    doctor_id: int,
    day: date,
    kind: TimeOffKind,
    start_minute: int | None,
    end_minute: int | None,
    reason: str | None,
    now: datetime,
) -> tuple[TimeOff, ReflowSummary]:
    _doctor(session, doctor_id)
    if day < now.date():
        raise InvalidRequest("Time off cannot be added in the past")
    if kind == TimeOffKind.LEAVE:
        start, end = 0, MINUTES_PER_DAY
    else:
        if start_minute is None or end_minute is None or start_minute >= end_minute:
            raise InvalidRequest("A block needs a start and end time")
        start, end = start_minute, end_minute

    time_off = TimeOff(
        doctor_id=doctor_id,
        day=day,
        start_minute=start,
        end_minute=end,
        kind=kind,
        reason=reason,
        created_at=now,
    )
    session.add(time_off)
    session.flush()
    summary = resolve_conflicts(session, doctor_id, [day], now)
    session.commit()
    return time_off, summary


def remove_time_off(session: Session, time_off_id: int, now: datetime) -> None:
    time_off = session.get(TimeOff, time_off_id)
    if time_off is None:
        raise NotFound("Time off not found")
    day = time_off.day
    session.delete(time_off)
    session.flush()
    if day >= now.date():
        waitlist.fill(session, day, now)
    session.commit()


def replace_working_hours(
    session: Session,
    doctor_id: int,
    hours: Sequence[tuple[int, Interval]],
    now: datetime,
    horizon_days: int = 28,
) -> ReflowSummary:
    _doctor(session, doctor_id)
    for weekday in range(7):
        blocks = [iv for wd, iv in hours if wd == weekday]
        if len(merge(blocks)) != len(blocks):
            raise InvalidRequest("Working hours on the same day must not overlap")

    session.execute(delete(WorkingHours).where(WorkingHours.doctor_id == doctor_id))
    session.add_all(
        WorkingHours(doctor_id=doctor_id, weekday=wd, start_minute=iv.start, end_minute=iv.end)
        for wd, iv in hours
    )
    session.flush()
    days = [now.date() + timedelta(days=i) for i in range(horizon_days)]
    summary = resolve_conflicts(session, doctor_id, days, now)
    for day in days:
        waitlist.fill(session, day, now)
    session.commit()
    return summary


def resolve_conflicts(
    session: Session, doctor_id: int, days: Sequence[date], now: datetime
) -> ReflowSummary:
    """Re-place upcoming bookings that no longer fit the doctor's open time. Caller commits."""
    summary = ReflowSummary()
    doctor_days = {
        dd.day: dd for dd in placement.build_doctor_days(session, days, now, doctor_ids=[doctor_id])
    }
    bookings = session.scalars(
        select(Booking)
        .where(
            Booking.doctor_id == doctor_id,
            Booking.day.in_(days),
            Booking.status.in_(UPCOMING_STATUSES),
        )
        .order_by(Booking.day, Booking.start_minute)
    ).all()

    for booking in bookings:
        if not booking.occupies(now):
            continue
        open_time = doctor_days[booking.day].open
        if any(iv.contains(booking.interval) for iv in open_time):
            continue
        _relocate(session, booking, now, summary)
        session.flush()
    return summary


def _relocate(session: Session, booking: Booking, now: datetime, summary: ReflowSummary) -> None:
    original_doctor = booking.doctor.name
    when = f"{format_minute(booking.start_minute)} on {booking.day:%a %d %b}"

    # 1. Same time, another doctor.
    same_time = placement.place(
        session,
        booking.request,
        now,
        days=[booking.day],
        exclude_booking_ids=[booking.id],
        allow_outside=False,
    )
    peers = [
        c
        for c in same_time.candidates
        if c.slot == booking.interval and c.doctor_id != booking.doctor_id
    ]
    if peers:
        best = min(peers, key=lambda c: c.breakdown.load)
        booking.doctor_id = best.doctor_id
        booking.source = BookingSource.REASSIGNED
        booking.notice = (
            f"{original_doctor} is unavailable, so your call at {when} "
            "was moved to another doctor. The time has not changed."
        )
        summary.moved_same_time.append(booking.code)
        return

    # 2. Another time inside the patient's ranges, same day.
    best_option = next(iter(same_time.options), None)
    if best_option is not None:
        c = best_option.candidate
        booking.doctor_id = c.doctor_id
        booking.start_minute = c.slot.start
        booking.end_minute = c.slot.end
        booking.match = placement.preference_match(c, booking.request.preferred_minute)
        booking.source = BookingSource.REASSIGNED
        booking.notice = (
            f"{original_doctor} became unavailable at {when}. Your call was moved to "
            f"{format_minute(c.slot.start)}, inside the times you said you were free."
        )
        summary.moved_new_time.append(booking.code)
        return

    # 3. Ask the patient.
    booking.status = BookingStatus.NEEDS_RESCHEDULE
    booking.notice = (
        f"{original_doctor} became unavailable at {when} and no other doctor was free "
        "in your time range. Please choose a new time."
    )
    summary.needs_reschedule.append(booking.code)


def list_time_off(session: Session, doctor_id: int, from_day: date) -> list[TimeOff]:
    return list(
        session.scalars(
            select(TimeOff)
            .where(TimeOff.doctor_id == doctor_id, TimeOff.day >= from_day)
            .order_by(TimeOff.day, TimeOff.start_minute)
        ).all()
    )
