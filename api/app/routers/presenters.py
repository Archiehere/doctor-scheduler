"""Convert domain objects into API responses."""

from __future__ import annotations

from datetime import date, datetime

from app import schemas
from app.config import settings
from app.models import Booking, BookingStatus, Doctor, PreferenceMatch, TimeOff, WaitlistEntry
from app.scheduler.engine import DoctorDay, Option
from app.services.analytics import DoctorReport
from app.services.placement import Placement
from app.services.policy import is_late_cancel
from app.services.reflow import ReflowSummary


def doctor_summary(doctor: Doctor) -> schemas.DoctorSummary:
    return schemas.DoctorSummary(id=doctor.id, name=doctor.name, specialty=doctor.specialty)


def option(opt: Option, placement: Placement, doctors: dict[int, Doctor]) -> schemas.OptionOut:
    c = opt.candidate
    b = c.breakdown
    return schemas.OptionOut(
        doctor=doctor_summary(doctors[c.doctor_id]),
        day=c.day,
        start_minute=c.slot.start,
        end_minute=c.slot.end,
        labels=[label.value for label in opt.labels],
        in_range=c.in_range,
        peak=c.demand_index >= settings.peak_threshold,
        deposit_required=placement.deposit_for(c),
        score=schemas.ScoreOut(
            total=round(b.total, 3),
            preference=round(b.preference, 3),
            fragmentation=round(b.fragmentation, 3),
            demand=round(b.demand, 3),
            load=round(b.load, 3),
            lead_time=round(b.lead_time, 3),
            outside_range=round(b.outside_range, 3),
        ),
    )


def options(
    request_id: int, placement: Placement, doctors: dict[int, Doctor]
) -> schemas.OptionsOut:
    return schemas.OptionsOut(
        request_id=request_id,
        in_range=placement.in_range,
        options=[option(o, placement, doctors) for o in placement.options],
        policy=schemas.PolicyOut(
            strikes=placement.strikes,
            tier=placement.tier,
            deposit_amount=settings.deposit_amount,
            currency=settings.currency,
        ),
    )


def booking(b: Booking, now: datetime) -> schemas.BookingOut:
    upcoming = b.status in (BookingStatus.HELD, BookingStatus.CONFIRMED)
    return schemas.BookingOut(
        code=b.code,
        status=b.status,
        doctor=doctor_summary(b.doctor),
        patient_name=b.patient.name,
        patient_email=b.patient.email,
        day=b.day,
        start_minute=b.start_minute,
        end_minute=b.end_minute,
        visit_type=b.visit_type,
        match=b.match,
        source=b.source,
        deposit_status=b.deposit_status,
        deposit_amount=b.deposit_amount,
        currency=settings.currency,
        hold_expires_at=b.hold_expires_at,
        notice=b.notice,
        late_cancel=b.late_cancel,
        ranges=[schemas.TimeRange(start=s, end=e) for s, e in b.request.ranges],
        preferred_minute=b.request.preferred_minute,
        can_cancel=(upcoming and b.starts_at > now) or b.status == BookingStatus.NEEDS_RESCHEDULE,
        cancel_is_late=b.status == BookingStatus.CONFIRMED
        and is_late_cancel(b.starts_at, now, settings),
        can_reschedule=b.status == BookingStatus.NEEDS_RESCHEDULE
        or (b.status == BookingStatus.CONFIRMED and not is_late_cancel(b.starts_at, now, settings)),
    )


def waitlist(entry: WaitlistEntry) -> schemas.WaitlistOut:
    return schemas.WaitlistOut(
        code=entry.code,
        status=entry.status,
        days=list(entry.request.date_list),
        ranges=[schemas.TimeRange(start=s, end=e) for s, e in entry.request.ranges],
        preferred_minute=entry.request.preferred_minute,
        booking_code=entry.booking.code if entry.booking else None,
    )


def time_off(t: TimeOff) -> schemas.TimeOffOut:
    return schemas.TimeOffOut.model_validate(t)


def reflow(summary: ReflowSummary) -> schemas.ReflowOut:
    return schemas.ReflowOut(
        moved_same_time=summary.moved_same_time,
        moved_new_time=summary.moved_new_time,
        needs_reschedule=summary.needs_reschedule,
    )


def day_stats(dd: DoctorDay) -> schemas.DayStats:
    free = dd.free()
    dead = sum(f.length for f in free if f.length < settings.min_bookable_gap)
    return schemas.DayStats(
        open_minutes=dd.open_minutes,
        booked_minutes=dd.booked_minutes,
        utilization=dd.booked_minutes / dd.open_minutes if dd.open_minutes else None,
        dead_gap_minutes=dead,
        bookable_minutes=sum(f.length for f in free) - dead,
    )


def kpis(r: DoctorReport) -> schemas.DoctorKpis:
    return schemas.DoctorKpis(
        doctor=schemas.DoctorSummary(id=r.doctor_id, name=r.name, specialty=r.specialty),
        utilization=r.utilization,
        realized_utilization=r.realized_utilization,
        upcoming_utilization=r.upcoming_utilization,
        days_at_target=r.days_at_target,
        working_days=r.working_days,
        calls_completed=r.calls_completed,
        no_shows=r.no_shows,
        no_show_rate=r.no_show_rate,
        late_cancel_rate=r.late_cancel_rate,
        preferred_rate=r.match_rate(PreferenceMatch.PREFERRED),
        in_range_rate=r.match_rate(PreferenceMatch.IN_RANGE),
        outside_rate=r.match_rate(PreferenceMatch.OUTSIDE),
        median_lead_hours=r.median_lead_hours,
        within_24h_rate=r.within_24h_rate,
        avg_scheduled_minutes=r.avg_scheduled_minutes,
        avg_actual_minutes=r.avg_actual_minutes,
        overrun_rate=r.overrun_rate,
        dead_gap_minutes=r.dead_gap_minutes,
        leave_hours=round(r.leave_minutes / 60, 1),
        waitlist_fills=r.waitlist_fills,
        reassigned=r.reassigned,
        deposits_forfeited=r.deposits_forfeited,
    )


def daily(r: DoctorReport, until: date) -> list[schemas.DailyPoint]:
    return [
        schemas.DailyPoint(
            day=d.day,
            open_minutes=d.open_minutes,
            booked_minutes=d.booked_minutes,
            utilization=d.utilization,
            dead_gap_minutes=d.dead_gap_minutes,
        )
        for d in r.days
        if d.day <= until
    ]


def blocks(r: DoctorReport) -> list[schemas.BlockPoint]:
    return [
        schemas.BlockPoint(
            weekday=b.weekday,
            daypart=b.daypart,
            open_minutes=b.open_minutes,
            booked_minutes=b.booked_minutes,
            utilization=b.utilization,
        )
        for b in sorted(r.blocks, key=lambda b: (b.weekday, b.daypart))
    ]


def schedule_booking(b: Booking) -> schemas.ScheduleBooking:
    return schemas.ScheduleBooking(
        id=b.id,
        code=b.code,
        patient_name=b.patient.name,
        start_minute=b.start_minute,
        end_minute=b.end_minute,
        visit_type=b.visit_type,
        status=b.status,
        match=b.match,
        source=b.source,
        deposit_status=b.deposit_status,
        started_at=b.started_at,
        ended_at=b.ended_at,
    )
