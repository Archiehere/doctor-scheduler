from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, BookingStatus
from tests.conftest import MONDAY, FakeClock, add_doctor, book


def test_doctor_metrics_reflect_outcomes(
    client: TestClient, session: Session, fake_clock: FakeClock
) -> None:
    rao = add_doctor(session, "Dr Rao")  # 09:00-13:00 = 240 open minutes
    codes = [
        str(book(client, email=f"p{i}@example.com", preferred=(9 + i) * 60)["code"])
        for i in range(4)
    ]
    bookings = session.scalars(select(Booking).where(Booking.code.in_(codes))).all()
    for b in bookings[:3]:
        b.status = BookingStatus.COMPLETED
        b.started_at = b.starts_at
        b.ended_at = b.starts_at + timedelta(minutes=40)  # 10 min overrun
    bookings[3].status = BookingStatus.NO_SHOW
    session.commit()

    fake_clock.current = fake_clock.current.replace(hour=18)
    data = client.get(
        f"/analytics/doctors/{rao.id}",
        params={"start": MONDAY.isoformat(), "end": MONDAY.isoformat()},
    ).json()
    kpis = data["kpis"]
    assert kpis["utilization"] == pytest.approx(120 / 240)
    assert kpis["realized_utilization"] == pytest.approx(90 / 240)
    assert kpis["no_show_rate"] == pytest.approx(0.25)
    assert kpis["overrun_rate"] == pytest.approx(1.0)
    assert kpis["calls_completed"] == 3
    assert data["daily"][0]["utilization"] == pytest.approx(0.5)


def test_overview_includes_every_doctor(client: TestClient, session: Session) -> None:
    add_doctor(session, "Dr Rao")
    add_doctor(session, "Dr Iyer")
    book(client)
    data = client.get("/analytics/overview").json()
    assert {d["doctor"]["name"] for d in data["doctors"]} == {"Dr Rao", "Dr Iyer"}
    assert data["target"] == 0.8
    assert data["clinic"]["preferred_rate"] == 1.0
