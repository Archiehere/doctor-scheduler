"""Patient-facing endpoints: find a slot, hold, confirm, manage, waitlist."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app import schemas
from app.config import settings
from app.routers import presenters
from app.routers.deps import NowDep, SessionDep, doctors_by_id
from app.scheduler.engine import bookable_minutes
from app.services import booking as booking_service
from app.services import placement, waitlist
from app.services.calendar import booking_ics

router = APIRouter(tags=["patients"])


@router.post("/booking-requests", response_model=schemas.OptionsOut)
def request_options(
    body: schemas.BookingRequestIn, session: SessionDep, now: NowDep
) -> schemas.OptionsOut:
    """Score every free slot inside the patient's ranges and return the best few."""
    request, result = booking_service.create_request(
        session,
        name=body.name,
        email=body.email,
        phone=body.phone,
        visit_type=body.visit_type,
        day=body.day,
        search_ahead_days=body.search_ahead_days,
        ranges=[r.to_interval() for r in body.ranges],
        preferred_minute=body.preferred_minute,
        now=now,
    )
    return presenters.options(request.id, result, doctors_by_id(session))


@router.post("/bookings", response_model=schemas.BookingOut, status_code=201)
def hold_slot(body: schemas.HoldIn, session: SessionDep, now: NowDep) -> schemas.BookingOut:
    booking = booking_service.hold(
        session,
        request_id=body.request_id,
        doctor_id=body.doctor_id,
        day=body.day,
        start_minute=body.start_minute,
        now=now,
    )
    return presenters.booking(booking, now)


@router.get("/bookings/{code}", response_model=schemas.BookingOut)
def get_booking(code: str, session: SessionDep, now: NowDep) -> schemas.BookingOut:
    return presenters.booking(booking_service.get_booking(session, code), now)


@router.post("/bookings/{code}/confirm", response_model=schemas.BookingOut)
def confirm_booking(
    code: str, body: schemas.ConfirmIn, session: SessionDep, now: NowDep
) -> schemas.BookingOut:
    booking = booking_service.confirm(session, code, deposit_paid=body.deposit_paid, now=now)
    return presenters.booking(booking, now)


@router.post("/bookings/{code}/cancel", response_model=schemas.BookingOut)
def cancel_booking(code: str, session: SessionDep, now: NowDep) -> schemas.BookingOut:
    return presenters.booking(booking_service.cancel(session, code, now), now)


@router.get("/bookings/{code}/reschedule-options", response_model=schemas.OptionsOut)
def reschedule_options(code: str, session: SessionDep, now: NowDep) -> schemas.OptionsOut:
    booking = booking_service.get_booking(session, code)
    result = booking_service.reschedule_options(session, code, now)
    return presenters.options(booking.request_id, result, doctors_by_id(session))


@router.post("/bookings/{code}/reschedule", response_model=schemas.BookingOut)
def reschedule_booking(
    code: str, body: schemas.SlotChoiceIn, session: SessionDep, now: NowDep
) -> schemas.BookingOut:
    booking = booking_service.reschedule(
        session,
        code,
        doctor_id=body.doctor_id,
        day=body.day,
        start_minute=body.start_minute,
        now=now,
    )
    return presenters.booking(booking, now)


@router.get("/bookings/{code}/calendar.ics")
def booking_calendar(code: str, session: SessionDep) -> Response:
    booking = booking_service.get_booking(session, code)
    return Response(
        content=booking_ics(booking),
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="call-{booking.code}.ics"'},
    )


@router.post("/waitlist", response_model=schemas.WaitlistOut, status_code=201)
def join_waitlist(
    body: schemas.WaitlistIn, session: SessionDep, now: NowDep
) -> schemas.WaitlistOut:
    entry = waitlist.join(session, body.request_id, body.deposit_acknowledged, now)
    return presenters.waitlist(entry)


@router.get("/waitlist/{code}", response_model=schemas.WaitlistOut)
def get_waitlist(code: str, session: SessionDep) -> schemas.WaitlistOut:
    return presenters.waitlist(waitlist.get(session, code))


@router.post("/waitlist/{code}/leave", response_model=schemas.WaitlistOut)
def leave_waitlist(code: str, session: SessionDep) -> schemas.WaitlistOut:
    return presenters.waitlist(waitlist.leave(session, code))


@router.get("/calendar", response_model=list[schemas.CalendarDay])
def calendar(
    session: SessionDep,
    now: NowDep,
    days: Annotated[int, Query(ge=1, le=settings.booking_horizon_days)] = 14,
) -> list[schemas.CalendarDay]:
    """Open and still-bookable minutes per day, so the day picker can skip closed or full days."""
    dates = [now.date() + timedelta(days=i) for i in range(days)]
    doctor_days = placement.build_doctor_days(session, dates, now)
    params = placement.engine_params()
    return [
        schemas.CalendarDay(
            day=day,
            open_minutes=sum(dd.open_minutes for dd in doctor_days if dd.day == day),
            bookable_minutes=sum(
                bookable_minutes(dd, now, params) for dd in doctor_days if dd.day == day
            ),
        )
        for day in dates
    ]


@router.get("/demand", response_model=schemas.DemandOut)
def demand_profile(
    day: date, session: SessionDep, now: NowDep, start: int = 7 * 60, end: int = 21 * 60
) -> schemas.DemandOut:
    """Forecast demand across a day, used to shade busy hours in the booking UI."""
    model = placement.load_demand(session, now)
    return schemas.DemandOut(
        day=day,
        peak_threshold=settings.peak_threshold,
        points=[
            schemas.DemandPoint(minute=m, index=round(i, 3))
            for m, i in model.profile(day, start, end)
        ],
    )
