"""Doctor portal endpoints: schedule, outcomes, working hours, time off."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Response
from sqlalchemy import select

from app import schemas
from app.errors import NotFound
from app.models import Booking, Doctor, WorkingHours
from app.routers import presenters
from app.routers.deps import NowDep, SessionDep
from app.services import booking as booking_service
from app.services import placement, reflow

router = APIRouter(prefix="/doctors", tags=["doctors"])


def _get_doctor(session: SessionDep, doctor_id: int) -> Doctor:
    doctor = session.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFound("Doctor not found")
    return doctor


@router.get("", response_model=list[schemas.DoctorListItem])
def list_doctors(session: SessionDep, now: NowDep) -> list[schemas.DoctorListItem]:
    doctors = session.scalars(select(Doctor).order_by(Doctor.name)).all()
    today = {dd.doctor_id: dd for dd in placement.build_doctor_days(session, [now.date()], now)}
    return [
        schemas.DoctorListItem(
            id=d.id, name=d.name, specialty=d.specialty, today=presenters.day_stats(today[d.id])
        )
        for d in doctors
    ]


@router.get("/{doctor_id}/schedule", response_model=schemas.ScheduleOut)
def schedule(doctor_id: int, day: date, session: SessionDep, now: NowDep) -> schemas.ScheduleOut:
    doctor = _get_doctor(session, doctor_id)
    (dd,) = placement.build_doctor_days(session, [day], now, doctor_ids=[doctor_id])
    bookings = session.scalars(
        select(Booking)
        .where(Booking.doctor_id == doctor_id, Booking.day == day)
        .order_by(Booking.start_minute)
    ).all()
    visible = [b for b in bookings if b.occupies(now)]
    return schemas.ScheduleOut(
        doctor=presenters.doctor_summary(doctor),
        day=day,
        open=[schemas.TimeRange(start=iv.start, end=iv.end) for iv in dd.open],
        time_off=[
            presenters.time_off(t)
            for t in reflow.list_time_off(session, doctor_id, day)
            if t.day == day
        ],
        bookings=[presenters.schedule_booking(b) for b in visible],
        stats=presenters.day_stats(dd),
    )


@router.post("/bookings/{booking_id}/outcome", response_model=schemas.ScheduleBooking)
def record_outcome(
    booking_id: int, body: schemas.OutcomeIn, session: SessionDep, now: NowDep
) -> schemas.ScheduleBooking:
    booking = booking_service.record_outcome(session, booking_id, body.action, now)
    return presenters.schedule_booking(booking)


@router.get("/{doctor_id}/hours", response_model=list[schemas.WorkingHoursItem])
def get_hours(doctor_id: int, session: SessionDep) -> list[schemas.WorkingHoursItem]:
    _get_doctor(session, doctor_id)
    hours = session.scalars(
        select(WorkingHours)
        .where(WorkingHours.doctor_id == doctor_id)
        .order_by(WorkingHours.weekday, WorkingHours.start_minute)
    ).all()
    return [
        schemas.WorkingHoursItem(weekday=h.weekday, start=h.start_minute, end=h.end_minute)
        for h in hours
    ]


@router.put("/{doctor_id}/hours", response_model=schemas.ReflowOut)
def put_hours(
    doctor_id: int, body: list[schemas.WorkingHoursItem], session: SessionDep, now: NowDep
) -> schemas.ReflowOut:
    summary = reflow.replace_working_hours(
        session,
        doctor_id,
        [(h.weekday, schemas.TimeRange(start=h.start, end=h.end).to_interval()) for h in body],
        now,
    )
    return presenters.reflow(summary)


@router.get("/{doctor_id}/time-off", response_model=list[schemas.TimeOffOut])
def get_time_off(doctor_id: int, session: SessionDep, now: NowDep) -> list[schemas.TimeOffOut]:
    _get_doctor(session, doctor_id)
    return [presenters.time_off(t) for t in reflow.list_time_off(session, doctor_id, now.date())]


@router.post("/{doctor_id}/time-off", response_model=schemas.TimeOffCreated, status_code=201)
def add_time_off(
    doctor_id: int, body: schemas.TimeOffIn, session: SessionDep, now: NowDep
) -> schemas.TimeOffCreated:
    time_off, summary = reflow.add_time_off(
        session,
        doctor_id=doctor_id,
        day=body.day,
        kind=body.kind,
        start_minute=body.start_minute,
        end_minute=body.end_minute,
        reason=body.reason,
        now=now,
    )
    return schemas.TimeOffCreated(
        time_off=presenters.time_off(time_off), reflow=presenters.reflow(summary)
    )


@router.delete("/{doctor_id}/time-off/{time_off_id}", status_code=204)
def delete_time_off(doctor_id: int, time_off_id: int, session: SessionDep, now: NowDep) -> Response:
    _get_doctor(session, doctor_id)
    reflow.remove_time_off(session, time_off_id, now)
    return Response(status_code=204)
