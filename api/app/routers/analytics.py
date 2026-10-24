from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter

from app import schemas
from app.config import settings
from app.errors import InvalidRequest, NotFound
from app.routers import presenters
from app.routers.deps import NowDep, SessionDep
from app.services import analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _window(start: date | None, end: date | None, today: date) -> tuple[date, date]:
    end = end or today
    start = start or end - timedelta(days=27)
    if start > end or (end - start).days > 365:
        raise InvalidRequest("Pick a range of at most one year with start before end")
    return start, end


@router.get("/overview", response_model=schemas.AnalyticsOverview)
def overview(
    session: SessionDep, now: NowDep, start: date | None = None, end: date | None = None
) -> schemas.AnalyticsOverview:
    start, end = _window(start, end, now.date())
    reports = analytics.build_reports(session, start, end, now)
    clinic = analytics.combine(reports)
    return schemas.AnalyticsOverview(
        start=start,
        end=end,
        target=settings.utilization_target,
        clinic=presenters.kpis(clinic),
        daily=presenters.daily(clinic, end),
        doctors=[presenters.kpis(r) for r in reports],
    )


@router.get("/doctors/{doctor_id}", response_model=schemas.DoctorAnalytics)
def doctor(
    doctor_id: int,
    session: SessionDep,
    now: NowDep,
    start: date | None = None,
    end: date | None = None,
) -> schemas.DoctorAnalytics:
    start, end = _window(start, end, now.date())
    reports = analytics.build_reports(session, start, end, now, doctor_ids=[doctor_id])
    if not reports:
        raise NotFound("Doctor not found")
    (report,) = reports
    return schemas.DoctorAnalytics(
        kpis=presenters.kpis(report),
        daily=presenters.daily(report, end),
        blocks=presenters.blocks(report),
        hints=report.hints(),
    )
