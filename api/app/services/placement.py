"""Bridges the database and the pure scheduling engine.

Loads doctor capacity and demand history, runs the engine for a stored request and
creates bookings. Booking, waitlist and leave flows all place calls through here,
so every path applies the same rules.
"""

from __future__ import annotations

import secrets
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import (
    OCCUPYING_STATUSES,
    Booking,
    BookingRequest,
    BookingSource,
    BookingStatus,
    DepositStatus,
    Doctor,
    Patient,
    PreferenceMatch,
    TimeOff,
    WorkingHours,
)
from app.scheduler.demand import DemandModel, DemandSample
from app.scheduler.engine import (
    Candidate,
    DoctorDay,
    EngineParams,
    Option,
    SlotRequest,
    generate_candidates,
    pick_options,
)
from app.scheduler.intervals import Interval, subtract
from app.services.policy import DepositTier, deposit_required, strike_score, tier_for

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_code(length: int = 8) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def engine_params(s: Settings = settings) -> EngineParams:
    return EngineParams(
        weights=s.weights,
        grid=s.grid_minutes,
        min_bookable_gap=s.min_bookable_gap,
        min_notice_minutes=s.min_notice_minutes,
        utilization_soft_cap=s.utilization_soft_cap,
        overcap_penalty=s.overcap_penalty,
        flexibility_full_minutes=s.flexibility_full_minutes,
        outside_range_margin=s.outside_range_margin,
    )


# --- capacity -----------------------------------------------------------------------


def open_intervals(
    hours: Iterable[WorkingHours], time_off: Iterable[TimeOff], day: date
) -> list[Interval]:
    weekly = [h.interval for h in hours if h.weekday == day.weekday()]
    return subtract(weekly, [t.interval for t in time_off if t.day == day])


def build_doctor_days(
    session: Session,
    days: Sequence[date],
    now: datetime,
    *,
    doctor_ids: Collection[int] | None = None,
    exclude_booking_ids: Collection[int] = (),
) -> list[DoctorDay]:
    doctor_query = select(Doctor)
    if doctor_ids is not None:
        doctor_query = doctor_query.where(Doctor.id.in_(doctor_ids))
    doctors = session.scalars(doctor_query.order_by(Doctor.id)).all()
    ids = [d.id for d in doctors]

    hours = session.scalars(select(WorkingHours).where(WorkingHours.doctor_id.in_(ids))).all()
    offs = session.scalars(
        select(TimeOff).where(TimeOff.doctor_id.in_(ids), TimeOff.day.in_(days))
    ).all()
    bookings = session.scalars(
        select(Booking).where(
            Booking.doctor_id.in_(ids),
            Booking.day.in_(days),
            Booking.status.in_(OCCUPYING_STATUSES),
        )
    ).all()

    result: list[DoctorDay] = []
    for doctor in doctors:
        doc_hours = [h for h in hours if h.doctor_id == doctor.id]
        doc_offs = [t for t in offs if t.doctor_id == doctor.id]
        for day in days:
            booked = tuple(
                b.interval
                for b in bookings
                if b.doctor_id == doctor.id
                and b.day == day
                and b.id not in exclude_booking_ids
                and b.occupies(now)
            )
            result.append(
                DoctorDay(doctor.id, day, tuple(open_intervals(doc_hours, doc_offs, day)), booked)
            )
    return result


def load_demand(session: Session, now: datetime, s: Settings = settings) -> DemandModel:
    since = now - timedelta(days=s.demand_history_days)
    requests = session.scalars(
        select(BookingRequest).where(BookingRequest.created_at >= since)
    ).all()
    samples = [
        DemandSample(r.requested_day.weekday(), r.interval_ranges, r.preferred_minute)
        for r in requests
    ]
    return DemandModel(samples, grid=s.grid_minutes, prior_strength=s.demand_prior_strength)


# --- patient risk -------------------------------------------------------------------


def patient_strikes(session: Session, patient_id: int, now: datetime) -> float:
    history = session.scalars(
        select(Booking).where(
            Booking.patient_id == patient_id,
            (Booking.status == BookingStatus.NO_SHOW) | Booking.late_cancel.is_(True),
        )
    ).all()
    no_shows = [b.starts_at for b in history if b.status == BookingStatus.NO_SHOW]
    late = [b.cancelled_at for b in history if b.late_cancel and b.cancelled_at is not None]
    return strike_score(no_shows, late, now, settings)


# --- placement ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Placement:
    """Engine output for one request, with the policy context needed to present it."""

    options: list[Option]
    in_range: bool
    candidates: list[Candidate]
    tier: DepositTier
    strikes: float

    def deposit_for(self, candidate: Candidate) -> bool:
        return deposit_required(self.tier, candidate.demand_index >= settings.peak_threshold)


def slot_request(request: BookingRequest, days: Sequence[date] | None = None) -> SlotRequest:
    return SlotRequest(
        duration=request.duration,
        ranges=request.interval_ranges,
        preferred=request.preferred_minute,
        days=tuple(days) if days is not None else request.date_list,
    )


def place(
    session: Session,
    request: BookingRequest,
    now: datetime,
    *,
    days: Sequence[date] | None = None,
    doctor_ids: Collection[int] | None = None,
    exclude_booking_ids: Collection[int] = (),
    allow_outside: bool = True,
) -> Placement:
    """Score every feasible slot for ``request`` and pick the options to show."""
    strikes = patient_strikes(session, request.patient_id, now)
    tier = tier_for(strikes)
    req = slot_request(request, days)
    if tier == DepositTier.RESTRICTED:
        req = SlotRequest(req.duration, req.ranges, req.preferred, (now.date(),))

    doctor_days = build_doctor_days(
        session, req.days, now, doctor_ids=doctor_ids, exclude_booking_ids=exclude_booking_ids
    )
    demand = load_demand(session, now)
    params = engine_params()

    def allowed(c: Candidate) -> bool:
        return tier != DepositTier.RESTRICTED or c.demand_index < settings.peak_threshold

    def scored(outside: bool) -> list[Candidate]:
        found = generate_candidates(
            req, doctor_days, demand.index, now, params, allow_outside=outside
        )
        return [c for c in found if allowed(c)]

    inside = scored(False)
    outside = scored(True) if allow_outside else []
    # Options come from in-range slots when any exist; nearby slots are only a fallback.
    # Both sets are kept so a fallback option the patient picked can still be validated.
    shown = inside or outside
    options = pick_options(shown, req.preferred, settings.options_returned)
    return Placement(options, bool(inside), inside + outside, tier, strikes)


def find_candidate(placement: Placement, doctor_id: int, day: date, start: int) -> Candidate | None:
    for c in placement.candidates:
        if c.doctor_id == doctor_id and c.day == day and c.slot.start == start:
            return c
    return None


def preference_match(candidate: Candidate, preferred: int) -> PreferenceMatch:
    if not candidate.in_range:
        return PreferenceMatch.OUTSIDE
    if abs(candidate.slot.start - preferred) <= settings.preferred_tolerance_minutes:
        return PreferenceMatch.PREFERRED
    return PreferenceMatch.IN_RANGE


def create_booking(
    session: Session,
    request: BookingRequest,
    candidate: Candidate,
    *,
    status: BookingStatus,
    source: BookingSource,
    deposit: DepositStatus,
    now: datetime,
) -> Booking:
    booking = Booking(
        code=new_code(),
        doctor_id=candidate.doctor_id,
        patient_id=request.patient_id,
        request_id=request.id,
        day=candidate.day,
        start_minute=candidate.slot.start,
        end_minute=candidate.slot.end,
        visit_type=request.visit_type,
        status=status,
        source=source,
        match=preference_match(candidate, request.preferred_minute),
        deposit_status=deposit,
        deposit_amount=settings.deposit_amount if deposit != DepositStatus.NONE else 0,
        created_at=now,
        hold_expires_at=now + timedelta(minutes=settings.hold_minutes)
        if status == BookingStatus.HELD
        else None,
        confirmed_at=now if status == BookingStatus.CONFIRMED else None,
    )
    session.add(booking)
    session.flush()
    return booking


def get_or_create_patient(
    session: Session, *, name: str, email: str, phone: str | None, now: datetime
) -> Patient:
    email = email.strip().lower()
    patient = session.scalar(select(Patient).where(Patient.email == email))
    if patient is None:
        patient = Patient(name=name.strip(), email=email, phone=phone, created_at=now)
        session.add(patient)
        session.flush()
    else:
        patient.name = name.strip()
        patient.phone = phone or patient.phone
    return patient
