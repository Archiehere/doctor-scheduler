"""Waitlist: patients whose ranges had no free slot are booked automatically when
capacity frees up inside their availability."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import InvalidRequest, NotFound
from app.models import (
    Booking,
    BookingRequest,
    BookingSource,
    BookingStatus,
    DepositStatus,
    WaitlistEntry,
    WaitlistStatus,
)
from app.services import placement
from app.services.policy import DepositTier


def join(
    session: Session, request_id: int, deposit_acknowledged: bool, now: datetime
) -> WaitlistEntry:
    request = session.get(BookingRequest, request_id)
    if request is None:
        raise NotFound("Booking request not found")
    if max(request.date_list) < now.date():
        raise InvalidRequest("All requested days are in the past")

    existing = session.scalar(
        select(WaitlistEntry).where(
            WaitlistEntry.request_id == request_id,
            WaitlistEntry.status == WaitlistStatus.WAITING,
        )
    )
    if existing is not None:
        return existing

    entry = WaitlistEntry(
        request_id=request_id,
        patient_id=request.patient_id,
        code=placement.new_code(),
        status=WaitlistStatus.WAITING,
        deposit_acknowledged=deposit_acknowledged,
        created_at=now,
    )
    session.add(entry)
    session.commit()
    return entry


def get(session: Session, code: str) -> WaitlistEntry:
    entry = session.scalar(select(WaitlistEntry).where(WaitlistEntry.code == code.upper()))
    if entry is None:
        raise NotFound("Waitlist entry not found")
    return entry


def leave(session: Session, code: str) -> WaitlistEntry:
    entry = get(session, code)
    if entry.status == WaitlistStatus.WAITING:
        entry.status = WaitlistStatus.CANCELLED
        session.commit()
    return entry


def fill(session: Session, day: date, now: datetime) -> list[Booking]:
    """Book waiting patients into free capacity on ``day``, first come first served.

    Only in-range slots are used: the patient never confirmed anything outside their
    stated availability, so we do not assume it. Caller commits.
    """
    waiting = session.scalars(
        select(WaitlistEntry)
        .where(WaitlistEntry.status == WaitlistStatus.WAITING)
        .order_by(WaitlistEntry.created_at, WaitlistEntry.id)
    ).all()

    filled: list[Booking] = []
    for entry in waiting:
        request = entry.request
        if max(request.date_list) < now.date():
            entry.status = WaitlistStatus.EXPIRED
            continue
        if day not in request.date_list:
            continue

        result = placement.place(session, request, now, days=[day], allow_outside=False)
        best = next(iter(result.options), None)
        if best is None:
            continue
        candidate = best.candidate
        needs_deposit = result.deposit_for(candidate)
        if needs_deposit and not entry.deposit_acknowledged:
            continue
        if result.tier == DepositTier.RESTRICTED and candidate.day != now.date():
            continue

        booking = placement.create_booking(
            session,
            request,
            candidate,
            status=BookingStatus.CONFIRMED,
            source=BookingSource.WAITLIST,
            deposit=DepositStatus.HELD if needs_deposit else DepositStatus.NONE,
            now=now,
        )
        booking.notice = "Booked automatically from the waitlist when a slot opened up."
        entry.status = WaitlistStatus.FILLED
        entry.booking_id = booking.id
        filled.append(booking)
        session.flush()
    return filled
