"""API request and response models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import VisitType
from app.models import (
    BookingSource,
    BookingStatus,
    DepositStatus,
    PreferenceMatch,
    TimeOffKind,
    WaitlistStatus,
)
from app.scheduler.intervals import MINUTES_PER_DAY, Interval
from app.services.booking import OutcomeAction
from app.services.policy import DepositTier

Minute = Annotated[int, Field(ge=0, le=MINUTES_PER_DAY)]


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimeRange(ApiModel):
    start: Minute
    end: Minute

    @model_validator(mode="after")
    def _ordered(self) -> TimeRange:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self

    def to_interval(self) -> Interval:
        return Interval(self.start, self.end)


# --- booking ----------------------------------------------------------------------


class BookingRequestIn(ApiModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    email: Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)]
    phone: Annotated[str | None, Field(max_length=40)] = None
    visit_type: VisitType
    day: date
    search_ahead_days: Annotated[int, Field(ge=0, le=6)] = 0
    ranges: Annotated[list[TimeRange], Field(min_length=1, max_length=4)]
    preferred_minute: Minute


class DoctorSummary(ApiModel):
    id: int
    name: str
    specialty: str


class ScoreOut(ApiModel):
    total: float
    preference: float
    fragmentation: float
    demand: float
    load: float
    lead_time: float
    outside_range: float


class OptionOut(ApiModel):
    doctor: DoctorSummary
    day: date
    start_minute: int
    end_minute: int
    labels: list[str]
    in_range: bool
    peak: bool
    deposit_required: bool
    score: ScoreOut


class PolicyOut(ApiModel):
    strikes: float
    tier: DepositTier
    deposit_cents: int


class OptionsOut(ApiModel):
    request_id: int
    in_range: bool
    options: list[OptionOut]
    policy: PolicyOut


class HoldIn(ApiModel):
    request_id: int
    doctor_id: int
    day: date
    start_minute: Minute


class ConfirmIn(ApiModel):
    deposit_paid: bool = False


class SlotChoiceIn(ApiModel):
    doctor_id: int
    day: date
    start_minute: Minute


class BookingOut(ApiModel):
    code: str
    status: BookingStatus
    doctor: DoctorSummary
    patient_name: str
    patient_email: str
    day: date
    start_minute: int
    end_minute: int
    visit_type: VisitType
    match: PreferenceMatch
    source: BookingSource
    deposit_status: DepositStatus
    deposit_cents: int
    hold_expires_at: datetime | None
    notice: str | None
    late_cancel: bool
    ranges: list[TimeRange]
    preferred_minute: int
    can_cancel: bool
    cancel_is_late: bool
    can_reschedule: bool


class WaitlistIn(ApiModel):
    request_id: int
    deposit_acknowledged: bool = False


class WaitlistOut(ApiModel):
    code: str
    status: WaitlistStatus
    days: list[date]
    ranges: list[TimeRange]
    preferred_minute: int
    booking_code: str | None


class DemandPoint(ApiModel):
    minute: int
    index: float


class DemandOut(ApiModel):
    day: date
    peak_threshold: float
    points: list[DemandPoint]


# --- doctors ----------------------------------------------------------------------


class WorkingHoursItem(ApiModel):
    weekday: Annotated[int, Field(ge=0, le=6)]
    start: Minute
    end: Minute

    @model_validator(mode="after")
    def _ordered(self) -> WorkingHoursItem:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class TimeOffIn(ApiModel):
    day: date
    kind: TimeOffKind
    start_minute: Minute | None = None
    end_minute: Minute | None = None
    reason: Annotated[str | None, Field(max_length=200)] = None


class TimeOffOut(ApiModel):
    id: int
    day: date
    kind: TimeOffKind
    start_minute: int
    end_minute: int
    reason: str | None


class ReflowOut(ApiModel):
    moved_same_time: list[str]
    moved_new_time: list[str]
    needs_reschedule: list[str]


class TimeOffCreated(ApiModel):
    time_off: TimeOffOut
    reflow: ReflowOut


class ScheduleBooking(ApiModel):
    id: int
    code: str
    patient_name: str
    start_minute: int
    end_minute: int
    visit_type: VisitType
    status: BookingStatus
    match: PreferenceMatch
    source: BookingSource
    deposit_status: DepositStatus
    started_at: datetime | None
    ended_at: datetime | None


class DayStats(ApiModel):
    open_minutes: int
    booked_minutes: int
    utilization: float | None
    dead_gap_minutes: int
    bookable_minutes: int


class ScheduleOut(ApiModel):
    doctor: DoctorSummary
    day: date
    open: list[TimeRange]
    time_off: list[TimeOffOut]
    bookings: list[ScheduleBooking]
    stats: DayStats


class OutcomeIn(ApiModel):
    action: OutcomeAction


class DoctorListItem(DoctorSummary):
    today: DayStats


# --- analytics --------------------------------------------------------------------


class DoctorKpis(ApiModel):
    doctor: DoctorSummary
    utilization: float | None
    realized_utilization: float | None
    upcoming_utilization: float | None
    days_at_target: int
    working_days: int
    calls_completed: int
    no_shows: int
    no_show_rate: float | None
    late_cancel_rate: float | None
    preferred_rate: float | None
    in_range_rate: float | None
    outside_rate: float | None
    median_lead_hours: float | None
    within_24h_rate: float | None
    avg_scheduled_minutes: float | None
    avg_actual_minutes: float | None
    overrun_rate: float | None
    dead_gap_minutes: int
    leave_hours: float
    waitlist_fills: int
    reassigned: int
    deposits_forfeited: int


class DailyPoint(ApiModel):
    day: date
    open_minutes: int
    booked_minutes: int
    utilization: float | None
    dead_gap_minutes: int


class BlockPoint(ApiModel):
    weekday: int
    daypart: str
    open_minutes: int
    booked_minutes: int
    utilization: float | None


class DoctorAnalytics(ApiModel):
    kpis: DoctorKpis
    daily: list[DailyPoint]
    blocks: list[BlockPoint]
    hints: list[str]


class AnalyticsOverview(ApiModel):
    start: date
    end: date
    target: float
    clinic: DoctorKpis
    daily: list[DailyPoint]
    doctors: list[DoctorKpis]
