"""Per-doctor and clinic-wide metrics.

Definitions (also in the README):

* **Utilisation**: booked minutes / open minutes. Booked counts confirmed,
  in-progress, completed and no-show calls, since a no-show still consumed the slot.
* **Realised utilisation**: completed minutes / open minutes.
* **No-show rate**: no-shows / (completed + no-shows).
* **Late-cancel rate**: cancellations within the late window / bookings confirmed.
* **Preference match**: share of placed bookings at the preferred time (within
  tolerance), elsewhere inside the patient's ranges, or outside them.
* **Lead time**: hours from the patient's request to the call start.
* **Dead gap**: free time between bookings shorter than the minimum call length.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import (
    Booking,
    BookingSource,
    BookingStatus,
    DepositStatus,
    Doctor,
    PreferenceMatch,
    TimeOff,
    WorkingHours,
)
from app.scheduler.intervals import Interval, subtract
from app.services.placement import open_intervals

BOOKED = (
    BookingStatus.CONFIRMED,
    BookingStatus.IN_PROGRESS,
    BookingStatus.COMPLETED,
    BookingStatus.NO_SHOW,
)
DAYPARTS: tuple[tuple[str, int, int], ...] = (
    ("morning", 0, 12 * 60),
    ("afternoon", 12 * 60, 17 * 60),
    ("evening", 17 * 60, 24 * 60),
)
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass
class DayStat:
    day: date
    open_minutes: int
    booked_minutes: int
    completed_minutes: int
    dead_gap_minutes: int

    @property
    def utilization(self) -> float | None:
        return self.booked_minutes / self.open_minutes if self.open_minutes else None


@dataclass
class BlockStat:
    weekday: int
    daypart: str
    open_minutes: int = 0
    booked_minutes: int = 0

    @property
    def utilization(self) -> float | None:
        return self.booked_minutes / self.open_minutes if self.open_minutes else None


@dataclass
class DoctorReport:
    doctor_id: int
    name: str
    specialty: str
    days: list[DayStat]
    blocks: list[BlockStat]
    calls_completed: int = 0
    no_shows: int = 0
    confirmed_total: int = 0
    late_cancels: int = 0
    cancellations: int = 0
    match_counts: dict[str, int] = field(default_factory=dict)
    lead_hours: list[float] = field(default_factory=list)
    scheduled_minutes: list[int] = field(default_factory=list)
    actual_minutes: list[int] = field(default_factory=list)
    leave_minutes: int = 0
    waitlist_fills: int = 0
    reassigned: int = 0
    deposits_forfeited: int = 0
    upcoming_open_minutes: int = 0
    upcoming_booked_minutes: int = 0

    # --- derived -------------------------------------------------------------------
    @property
    def open_minutes(self) -> int:
        return sum(d.open_minutes for d in self.days)

    @property
    def booked_minutes(self) -> int:
        return sum(d.booked_minutes for d in self.days)

    @property
    def utilization(self) -> float | None:
        return _ratio(self.booked_minutes, self.open_minutes)

    @property
    def realized_utilization(self) -> float | None:
        return _ratio(sum(d.completed_minutes for d in self.days), self.open_minutes)

    @property
    def upcoming_utilization(self) -> float | None:
        return _ratio(self.upcoming_booked_minutes, self.upcoming_open_minutes)

    @property
    def no_show_rate(self) -> float | None:
        return _ratio(self.no_shows, self.calls_completed + self.no_shows)

    @property
    def late_cancel_rate(self) -> float | None:
        return _ratio(self.late_cancels, self.confirmed_total)

    @property
    def dead_gap_minutes(self) -> int:
        return sum(d.dead_gap_minutes for d in self.days)

    @property
    def days_at_target(self) -> int:
        return sum(
            1
            for d in self.days
            if d.utilization is not None and d.utilization >= settings.utilization_target
        )

    @property
    def working_days(self) -> int:
        return sum(1 for d in self.days if d.open_minutes)

    @property
    def median_lead_hours(self) -> float | None:
        return statistics.median(self.lead_hours) if self.lead_hours else None

    @property
    def within_24h_rate(self) -> float | None:
        return _ratio(sum(1 for h in self.lead_hours if h <= 24), len(self.lead_hours))

    @property
    def avg_scheduled_minutes(self) -> float | None:
        return statistics.fmean(self.scheduled_minutes) if self.scheduled_minutes else None

    @property
    def avg_actual_minutes(self) -> float | None:
        return statistics.fmean(self.actual_minutes) if self.actual_minutes else None

    @property
    def overrun_rate(self) -> float | None:
        pairs = list(zip(self.scheduled_minutes, self.actual_minutes, strict=True))
        return _ratio(sum(1 for s, a in pairs if a > s + 5), len(pairs))

    def match_rate(self, match: PreferenceMatch) -> float | None:
        return _ratio(self.match_counts.get(match.value, 0), sum(self.match_counts.values()))

    def hints(self) -> list[str]:
        """Capacity suggestions: where open hours are persistently under- or over-used."""
        out: list[str] = []
        for b in self.blocks:
            u = b.utilization
            if u is None or b.open_minutes < 4 * 60:
                continue
            label = f"{WEEKDAYS[b.weekday]} {b.daypart}s"
            if u < 0.5:
                out.append(
                    f"{label} run at {u:.0%} booked. Consider moving some of these hours "
                    "to busier blocks."
                )
            elif u > 0.95:
                out.append(f"{label} are {u:.0%} booked. Adding hours here would absorb demand.")
        return out


def _ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def _daypart(minute: int) -> str:
    for name, start, end in DAYPARTS:
        if start <= minute < end:
            return name
    return DAYPARTS[-1][0]


def build_reports(
    session: Session,
    start: date,
    end: date,
    now: datetime,
    doctor_ids: Sequence[int] | None = None,
    upcoming_days: int = 7,
) -> list[DoctorReport]:
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    upcoming = [now.date() + timedelta(days=i) for i in range(1, upcoming_days + 1)]
    span = sorted(set(days) | set(upcoming))

    query = select(Doctor).order_by(Doctor.name)
    if doctor_ids is not None:
        query = query.where(Doctor.id.in_(doctor_ids))
    doctors = session.scalars(query).all()
    ids = [d.id for d in doctors]

    hours = session.scalars(select(WorkingHours).where(WorkingHours.doctor_id.in_(ids))).all()
    offs = session.scalars(
        select(TimeOff).where(TimeOff.doctor_id.in_(ids), TimeOff.day.in_(span))
    ).all()
    bookings = session.scalars(
        select(Booking)
        .where(Booking.doctor_id.in_(ids), Booking.day.in_(span))
        .options(selectinload(Booking.request))
    ).all()

    hours_by: dict[int, list[WorkingHours]] = defaultdict(list)
    offs_by: dict[int, list[TimeOff]] = defaultdict(list)
    bookings_by: dict[tuple[int, date], list[Booking]] = defaultdict(list)
    for h in hours:
        hours_by[h.doctor_id].append(h)
    for t in offs:
        offs_by[t.doctor_id].append(t)
    for b in bookings:
        bookings_by[(b.doctor_id, b.day)].append(b)

    reports: list[DoctorReport] = []
    for doctor in doctors:
        report = DoctorReport(doctor.id, doctor.name, doctor.specialty, days=[], blocks=[])
        blocks = {(wd, name): BlockStat(wd, name) for wd in range(7) for name, _, _ in DAYPARTS}
        for day in days:
            weekly = [h.interval for h in hours_by[doctor.id] if h.weekday == day.weekday()]
            open_time = open_intervals(hours_by[doctor.id], offs_by[doctor.id], day)
            report.leave_minutes += sum(iv.length for iv in weekly) - sum(
                iv.length for iv in open_time
            )
            day_bookings = bookings_by[(doctor.id, day)]
            booked = [b for b in day_bookings if b.status in BOOKED]
            completed = [b for b in booked if b.status == BookingStatus.COMPLETED]
            free = subtract(open_time, [b.interval for b in booked])
            report.days.append(
                DayStat(
                    day,
                    sum(iv.length for iv in open_time),
                    sum(b.interval.length for b in booked),
                    sum(b.interval.length for b in completed),
                    sum(f.length for f in free if f.length < settings.min_bookable_gap),
                )
            )
            _add_blocks(blocks, day.weekday(), open_time, [b.interval for b in booked])
            _add_booking_stats(report, day_bookings)

        for day in upcoming:
            open_time = open_intervals(hours_by[doctor.id], offs_by[doctor.id], day)
            report.upcoming_open_minutes += sum(iv.length for iv in open_time)
            report.upcoming_booked_minutes += sum(
                b.interval.length for b in bookings_by[(doctor.id, day)] if b.status in BOOKED
            )

        report.blocks = [b for b in blocks.values() if b.open_minutes]
        reports.append(report)
    return reports


def _add_blocks(
    blocks: dict[tuple[int, str], BlockStat],
    weekday: int,
    open_time: list[Interval],
    booked: list[Interval],
) -> None:
    for name, start, end in DAYPARTS:
        part = Interval(start, end)
        open_part = subtract(open_time, subtract([Interval(0, 24 * 60)], [part]))
        stat = blocks[(weekday, name)]
        stat.open_minutes += sum(iv.length for iv in open_part)
        stat.booked_minutes += sum(
            min(b.end, part.end) - max(b.start, part.start) for b in booked if b.overlaps(part)
        )


def _add_booking_stats(report: DoctorReport, bookings: list[Booking]) -> None:
    for b in bookings:
        placed = b.confirmed_at is not None or b.source == BookingSource.WAITLIST
        if not placed:
            continue  # expired holds never became bookings
        report.confirmed_total += 1
        report.match_counts[b.match.value] = report.match_counts.get(b.match.value, 0) + 1
        report.lead_hours.append((b.starts_at - b.request.created_at).total_seconds() / 3600)
        if b.source == BookingSource.WAITLIST:
            report.waitlist_fills += 1
        if b.source == BookingSource.REASSIGNED:
            report.reassigned += 1
        if b.status == BookingStatus.COMPLETED:
            report.calls_completed += 1
            if b.started_at and b.ended_at:
                report.scheduled_minutes.append(b.interval.length)
                report.actual_minutes.append(int((b.ended_at - b.started_at).total_seconds() // 60))
        elif b.status == BookingStatus.NO_SHOW:
            report.no_shows += 1
        elif b.status == BookingStatus.CANCELLED:
            report.cancellations += 1
            report.late_cancels += int(b.late_cancel)
        if b.deposit_status == DepositStatus.FORFEITED:
            report.deposits_forfeited += 1


def combine(reports: Sequence[DoctorReport]) -> DoctorReport:
    """Clinic-wide report: the sum of every doctor's report."""
    clinic = DoctorReport(0, "All doctors", "Clinic", days=[], blocks=[])
    days: dict[date, DayStat] = {}
    blocks: dict[tuple[int, str], BlockStat] = {}
    for r in reports:
        for d in r.days:
            agg = days.setdefault(d.day, DayStat(d.day, 0, 0, 0, 0))
            agg.open_minutes += d.open_minutes
            agg.booked_minutes += d.booked_minutes
            agg.completed_minutes += d.completed_minutes
            agg.dead_gap_minutes += d.dead_gap_minutes
        for b in r.blocks:
            agg_b = blocks.setdefault((b.weekday, b.daypart), BlockStat(b.weekday, b.daypart))
            agg_b.open_minutes += b.open_minutes
            agg_b.booked_minutes += b.booked_minutes
        for key, count in r.match_counts.items():
            clinic.match_counts[key] = clinic.match_counts.get(key, 0) + count
        clinic.lead_hours += r.lead_hours
        clinic.scheduled_minutes += r.scheduled_minutes
        clinic.actual_minutes += r.actual_minutes
        for attr in (
            "calls_completed",
            "no_shows",
            "confirmed_total",
            "late_cancels",
            "cancellations",
            "leave_minutes",
            "waitlist_fills",
            "reassigned",
            "deposits_forfeited",
            "upcoming_open_minutes",
            "upcoming_booked_minutes",
        ):
            setattr(clinic, attr, getattr(clinic, attr) + getattr(r, attr))
    clinic.days = [days[k] for k in sorted(days)]
    clinic.blocks = list(blocks.values())
    return clinic
