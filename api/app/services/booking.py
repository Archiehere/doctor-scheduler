"""Patient booking flow: request options -> hold -> confirm, plus cancel,
reschedule and the doctor's outcome actions."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import VISIT_DURATIONS, VisitType, settings
from app.errors import (
    DepositRequired,
    HoldExpired,
    InvalidRequest,
    InvalidTransition,
    NotFound,
    SlotUnavailable,
)
from app.models import (
    Booking,
    BookingRequest,
    BookingSource,
    BookingStatus,
    DepositStatus,
)
from app.scheduler.intervals import Interval, merge
from app.services import placement, waitlist
from app.services.policy import is_late_cancel


def create_request(
    session: Session,
    *,
    name: str,
    email: str,
    phone: str | None,
    visit_type: VisitType,
    day: date,
    search_ahead_days: int,
    ranges: list[Interval],
    preferred_minute: int,
    now: datetime,
) -> tuple[BookingRequest, placement.Placement]:
    if day < now.date():
        raise InvalidRequest("The requested day is in the past")
    merged = merge(ranges)
    duration = VISIT_DURATIONS[visit_type]
    if not merged or all(r.length < duration for r in merged):
        raise InvalidRequest(f"Give at least one range of {duration} minutes or more")
    if not any(r.start <= preferred_minute <= r.end for r in merged):
        raise InvalidRequest("The preferred time must fall inside one of your ranges")

    ahead = min(max(search_ahead_days, 0), settings.max_search_ahead_days)
    patient = placement.get_or_create_patient(session, name=name, email=email, phone=phone, now=now)
    request = BookingRequest(
        patient_id=patient.id,
        visit_type=visit_type,
        duration=duration,
        days=[(day + timedelta(days=i)).isoformat() for i in range(ahead + 1)],
        ranges=[[r.start, r.end] for r in merged],
        preferred_minute=preferred_minute,
        created_at=now,
    )
    session.add(request)
    session.flush()
    result = placement.place(session, request, now)
    session.commit()
    return request, result


def get_request(session: Session, request_id: int) -> BookingRequest:
    request = session.get(BookingRequest, request_id)
    if request is None:
        raise NotFound("Booking request not found")
    return request


def get_booking(session: Session, code: str) -> Booking:
    booking = session.scalar(select(Booking).where(Booking.code == code.upper()))
    if booking is None:
        raise NotFound("Booking not found")
    return booking


def hold(
    session: Session,
    *,
    request_id: int,
    doctor_id: int,
    day: date,
    start_minute: int,
    now: datetime,
) -> Booking:
    """Reserve a chosen option for a few minutes while the patient confirms.

    The slot is re-validated against live capacity inside the write transaction, so
    two patients picking the same option cannot both get it.
    """
    request = get_request(session, request_id)
    result = placement.place(session, request, now, doctor_ids=[doctor_id], days=[day])
    candidate = placement.find_candidate(result, doctor_id, day, start_minute)
    if candidate is None:
        session.rollback()
        raise SlotUnavailable("That time was just taken. Please choose another option.")

    needs_deposit = result.deposit_for(candidate)
    booking = placement.create_booking(
        session,
        request,
        candidate,
        status=BookingStatus.HELD,
        source=BookingSource.DIRECT,
        deposit=DepositStatus.PENDING if needs_deposit else DepositStatus.NONE,
        now=now,
    )
    session.commit()
    return booking


def confirm(session: Session, code: str, *, deposit_paid: bool, now: datetime) -> Booking:
    booking = get_booking(session, code)
    if booking.status == BookingStatus.CONFIRMED:
        return booking
    if booking.status != BookingStatus.HELD:
        raise InvalidTransition(f"A {booking.status.value} booking cannot be confirmed")
    if booking.hold_expires_at is None or booking.hold_expires_at <= now:
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = now
        session.commit()
        raise HoldExpired("The hold on this slot expired. Please pick a time again.")
    if booking.deposit_status == DepositStatus.PENDING:
        if not deposit_paid:
            raise DepositRequired("A refundable deposit is required to confirm this slot.")
        booking.deposit_status = DepositStatus.HELD

    booking.status = BookingStatus.CONFIRMED
    booking.confirmed_at = now
    booking.hold_expires_at = None
    session.commit()
    return booking


def cancel(session: Session, code: str, now: datetime) -> Booking:
    booking = get_booking(session, code)
    if booking.status not in (
        BookingStatus.HELD,
        BookingStatus.CONFIRMED,
        BookingStatus.NEEDS_RESCHEDULE,
    ):
        raise InvalidTransition(f"A {booking.status.value} booking cannot be cancelled")

    was_confirmed = booking.status == BookingStatus.CONFIRMED
    late = was_confirmed and is_late_cancel(booking.starts_at, now, settings)
    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = now
    booking.late_cancel = late
    if booking.deposit_status == DepositStatus.HELD:
        booking.deposit_status = DepositStatus.FORFEITED if late else DepositStatus.REFUNDED
    elif booking.deposit_status == DepositStatus.PENDING:
        booking.deposit_status = DepositStatus.NONE
    session.flush()

    if was_confirmed:
        waitlist.fill(session, booking.day, now)
    session.commit()
    return booking


def reschedule_options(session: Session, code: str, now: datetime) -> placement.Placement:
    booking = get_booking(session, code)
    if booking.status not in (BookingStatus.CONFIRMED, BookingStatus.NEEDS_RESCHEDULE):
        raise InvalidTransition(f"A {booking.status.value} booking cannot be rescheduled")
    return placement.place(
        session,
        booking.request,
        now,
        days=_reschedule_days(booking, now),
        exclude_booking_ids=[booking.id],
    )


def reschedule(
    session: Session, code: str, *, doctor_id: int, day: date, start_minute: int, now: datetime
) -> Booking:
    booking = get_booking(session, code)
    if booking.status not in (BookingStatus.CONFIRMED, BookingStatus.NEEDS_RESCHEDULE):
        raise InvalidTransition(f"A {booking.status.value} booking cannot be rescheduled")
    if booking.status == BookingStatus.CONFIRMED and is_late_cancel(
        booking.starts_at, now, settings
    ):
        raise InvalidTransition("Calls starting within 2 hours cannot be moved")

    result = placement.place(
        session,
        booking.request,
        now,
        days=[day],
        doctor_ids=[doctor_id],
        exclude_booking_ids=[booking.id],
    )
    candidate = placement.find_candidate(result, doctor_id, day, start_minute)
    if candidate is None or day not in _reschedule_days(booking, now):
        session.rollback()
        raise SlotUnavailable("That time is no longer available.")

    old_day = booking.day
    was_confirmed = booking.status == BookingStatus.CONFIRMED
    booking.doctor_id = candidate.doctor_id
    booking.day = candidate.day
    booking.start_minute = candidate.slot.start
    booking.end_minute = candidate.slot.end
    booking.match = placement.preference_match(candidate, booking.request.preferred_minute)
    booking.status = BookingStatus.CONFIRMED
    booking.notice = None
    session.flush()
    if was_confirmed:
        waitlist.fill(session, old_day, now)
    session.commit()
    return booking


def _reschedule_days(booking: Booking, now: datetime) -> list[date]:
    start = max(now.date(), booking.request.requested_day)
    return [start + timedelta(days=i) for i in range(settings.max_search_ahead_days + 1)]


class OutcomeAction(StrEnum):
    START = "start"
    COMPLETE = "complete"
    NO_SHOW = "no_show"


def record_outcome(
    session: Session, booking_id: int, action: OutcomeAction, now: datetime
) -> Booking:
    """Doctor-side status changes. Deposits settle here: refunded when the call
    happens, forfeited on a no-show."""
    booking = session.get(Booking, booking_id)
    if booking is None:
        raise NotFound("Booking not found")

    if action == OutcomeAction.START:
        if booking.status != BookingStatus.CONFIRMED:
            raise InvalidTransition("Only confirmed calls can be started")
        booking.status = BookingStatus.IN_PROGRESS
        booking.started_at = now
    elif action == OutcomeAction.COMPLETE:
        if booking.status not in (BookingStatus.CONFIRMED, BookingStatus.IN_PROGRESS):
            raise InvalidTransition("Only confirmed or in-progress calls can be completed")
        booking.started_at = booking.started_at or booking.starts_at
        booking.ended_at = max(now, booking.started_at)
        booking.status = BookingStatus.COMPLETED
        if booking.deposit_status == DepositStatus.HELD:
            booking.deposit_status = DepositStatus.REFUNDED
    elif action == OutcomeAction.NO_SHOW:
        if booking.status != BookingStatus.CONFIRMED:
            raise InvalidTransition("Only confirmed calls can be marked as no-show")
        if now < booking.starts_at:
            raise InvalidTransition("A call cannot be marked no-show before it starts")
        booking.status = BookingStatus.NO_SHOW
        if booking.deposit_status == DepositStatus.HELD:
            booking.deposit_status = DepositStatus.FORFEITED
    session.commit()
    return booking
