"""Persistence model.

Times of day are stored as minutes from midnight in clinic-local time alongside a
calendar date. The scheduler reasons in that grid, so storing it directly avoids a
conversion layer and makes the data readable in a SQL shell.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import StrEnum

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import VisitType
from app.db import Base
from app.scheduler.intervals import Interval


class BookingStatus(StrEnum):
    HELD = "held"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"
    NEEDS_RESCHEDULE = "needs_reschedule"


# Statuses that occupy a doctor's time (HELD only while the hold is live).
OCCUPYING_STATUSES = (
    BookingStatus.HELD,
    BookingStatus.CONFIRMED,
    BookingStatus.IN_PROGRESS,
    BookingStatus.COMPLETED,
    BookingStatus.NO_SHOW,
)
UPCOMING_STATUSES = (BookingStatus.HELD, BookingStatus.CONFIRMED)


class DepositStatus(StrEnum):
    NONE = "none"
    PENDING = "pending"
    HELD = "held"
    REFUNDED = "refunded"
    FORFEITED = "forfeited"


class PreferenceMatch(StrEnum):
    PREFERRED = "preferred"
    IN_RANGE = "in_range"
    OUTSIDE = "outside"


class BookingSource(StrEnum):
    DIRECT = "direct"
    WAITLIST = "waitlist"
    REASSIGNED = "reassigned"


class TimeOffKind(StrEnum):
    LEAVE = "leave"
    BLOCK = "block"


class WaitlistStatus(StrEnum):
    WAITING = "waiting"
    FILLED = "filled"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


def _enum(e: type[StrEnum]) -> Enum:
    return Enum(
        e, native_enum=False, validate_strings=True, values_callable=lambda x: [m.value for m in x]
    )


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    specialty: Mapped[str] = mapped_column(String(120))

    working_hours: Mapped[list[WorkingHours]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan", order_by="WorkingHours.start_minute"
    )


class WorkingHours(Base):
    """A recurring weekly block. Several per weekday model breaks (e.g. lunch)."""

    __tablename__ = "working_hours"

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"))
    weekday: Mapped[int] = mapped_column(Integer)  # 0 = Monday
    start_minute: Mapped[int] = mapped_column(Integer)
    end_minute: Mapped[int] = mapped_column(Integer)

    doctor: Mapped[Doctor] = relationship(back_populates="working_hours")

    @property
    def interval(self) -> Interval:
        return Interval(self.start_minute, self.end_minute)


class TimeOff(Base):
    """Leave (whole day) or a block (part of a day) when the doctor is unavailable."""

    __tablename__ = "time_off"
    __table_args__ = (Index("ix_time_off_doctor_day", "doctor_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
    start_minute: Mapped[int] = mapped_column(Integer)
    end_minute: Mapped[int] = mapped_column(Integer)
    kind: Mapped[TimeOffKind] = mapped_column(_enum(TimeOffKind))
    reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    @property
    def interval(self) -> Interval:
        return Interval(self.start_minute, self.end_minute)


class Patient(Base):
    """Identified by email since the MVP has no accounts."""

    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class BookingRequest(Base):
    """What the patient asked for. Kept so bookings can be re-placed within the
    patient's own availability if a doctor takes leave, and to feed the demand model."""

    __tablename__ = "booking_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    visit_type: Mapped[VisitType] = mapped_column(_enum(VisitType))
    duration: Mapped[int] = mapped_column(Integer)
    days: Mapped[list[str]] = mapped_column(JSON)  # ISO dates, first is the requested day
    ranges: Mapped[list[list[int]]] = mapped_column(JSON)  # [[start, end], ...]
    preferred_minute: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    patient: Mapped[Patient] = relationship()

    @property
    def interval_ranges(self) -> tuple[Interval, ...]:
        return tuple(Interval(s, e) for s, e in self.ranges)

    @property
    def date_list(self) -> tuple[date, ...]:
        return tuple(date.fromisoformat(d) for d in self.days)

    @property
    def requested_day(self) -> date:
        return date.fromisoformat(self.days[0])


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (Index("ix_bookings_doctor_day", "doctor_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    request_id: Mapped[int] = mapped_column(ForeignKey("booking_requests.id"))

    day: Mapped[date] = mapped_column(Date)
    start_minute: Mapped[int] = mapped_column(Integer)
    end_minute: Mapped[int] = mapped_column(Integer)
    visit_type: Mapped[VisitType] = mapped_column(_enum(VisitType))

    status: Mapped[BookingStatus] = mapped_column(_enum(BookingStatus), index=True)
    source: Mapped[BookingSource] = mapped_column(_enum(BookingSource))
    match: Mapped[PreferenceMatch] = mapped_column(_enum(PreferenceMatch))
    deposit_status: Mapped[DepositStatus] = mapped_column(_enum(DepositStatus))
    deposit_amount: Mapped[int] = mapped_column(Integer, default=0)
    late_cancel: Mapped[bool] = mapped_column(default=False)
    notice: Mapped[str | None] = mapped_column(String(300))

    created_at: Mapped[datetime] = mapped_column(DateTime)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)

    doctor: Mapped[Doctor] = relationship()
    patient: Mapped[Patient] = relationship()
    request: Mapped[BookingRequest] = relationship()

    @property
    def interval(self) -> Interval:
        return Interval(self.start_minute, self.end_minute)

    @property
    def starts_at(self) -> datetime:
        return datetime.combine(self.day, datetime.min.time()) + timedelta(
            minutes=self.start_minute
        )

    @property
    def ends_at(self) -> datetime:
        return datetime.combine(self.day, datetime.min.time()) + timedelta(minutes=self.end_minute)

    def occupies(self, now: datetime) -> bool:
        if self.status == BookingStatus.HELD:
            return self.hold_expires_at is not None and self.hold_expires_at > now
        return self.status in OCCUPYING_STATUSES


class WaitlistEntry(Base):
    __tablename__ = "waitlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("booking_requests.id"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    code: Mapped[str] = mapped_column(String(12), unique=True)
    status: Mapped[WaitlistStatus] = mapped_column(_enum(WaitlistStatus), index=True)
    deposit_acknowledged: Mapped[bool] = mapped_column(default=False)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    request: Mapped[BookingRequest] = relationship()
    patient: Mapped[Patient] = relationship()
    booking: Mapped[Booking | None] = relationship()
